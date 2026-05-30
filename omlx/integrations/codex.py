"""Codex (OpenAI Codex CLI) integration."""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from omlx.integrations.base import Integration, IntegrationContext
from omlx.utils.install import get_cli_command_prefix

CODEX_CONFIG_PATH = Path.home() / ".codex" / "config.toml"


def write_codex_config(config_path: Path, ctx: IntegrationContext) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing_content = ""
    if config_path.exists():
        # Create backup
        timestamp = int(time.time())
        backup = config_path.with_suffix(f".{timestamp}.bak")
        try:
            shutil.copy2(config_path, backup)
            existing_content = config_path.read_text(encoding="utf-8")
            print(f"Backup: {backup}")
        except OSError as e:
            print(f"Warning: could not create backup or read config: {e}")

    # Parse existing config lines to preserve other settings
    lines = existing_content.splitlines()
    new_lines = []
    in_any_section = False
    in_omlx_section = False

    # Keys to override at the top level (always rewrite)
    top_level_overrides = {
        "model": f'"{ctx.model or "select-a-model"}"',
        "model_provider": '"omlx"',
    }

    # If it is a reasoning model, add reasoning effort
    is_reasoning = (
        bool(ctx.reasoning)
        if ctx.reasoning is not None
        else bool(re.search(r"\b(thinking|o1|o3|r1)\b", ctx.model.lower()))
    )
    if is_reasoning:
        top_level_overrides["model_reasoning_effort"] = '"high"'

    # Top-level defaults: inserted IF MISSING, never overwritten. These align
    # codex's auto-compaction with oMLX's advertised context window. Without
    # them, codex falls back to its own model-name heuristic (often double the
    # real ceiling) and never triggers auto-compact → "Prompt too long" errors.
    # The compaction threshold is 75% of the window — leaves Metal-heap
    # headroom for prefill activations during the compact call itself.
    ctx_window = int(ctx.context_window) if ctx.context_window else 128000
    compact_limit = max(8000, int(ctx_window * 0.75))
    top_level_defaults = {
        "model_context_window": str(ctx_window),
        "model_auto_compact_token_limit": str(compact_limit),
    }

    # Keys managed by oMLX that should be removed when not applicable
    managed_keys = {"model_reasoning_effort"} - set(top_level_overrides.keys())

    seen_keys = set()
    preserved_omlx_lines: list[str] = []
    managed_provider_keys = {"name", "base_url", "env_key"}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_any_section = True
            in_omlx_section = stripped == "[model_providers.omlx]"
            if in_omlx_section:
                continue  # drop header; we re-append managed keys below

        # Handle top-level keys
        if not in_any_section and "=" in stripped:
            key = stripped.split("=")[0].strip()
            if key in top_level_overrides:
                new_lines.append(f"{key} = {top_level_overrides[key]}")
                seen_keys.add(key)
                continue
            if key in managed_keys:
                continue
            if key in top_level_defaults:
                # Respect existing user-set value; just mark as seen.
                seen_keys.add(key)
                new_lines.append(line)
                continue

        # Inside oMLX provider section: drop the 3 managed keys, preserve
        # everything else (user-set timeouts, retries, headers, comments, …)
        if in_omlx_section:
            if "=" in stripped:
                key = stripped.split("=")[0].strip()
                if key in managed_provider_keys:
                    continue
            preserved_omlx_lines.append(line)
            continue

        new_lines.append(line)

    # Add missing top-level keys (overrides first so they land above defaults)
    for key, val in {**top_level_defaults, **top_level_overrides}.items():
        if key not in seen_keys:
            new_lines.insert(0, f"{key} = {val}")

    # Append refreshed oMLX provider section: managed keys + preserved user fields
    new_lines.append("\n[model_providers.omlx]")
    new_lines.append('name = "oMLX"')
    new_lines.append(f'base_url = "{ctx.openai_base_url}"')
    new_lines.append('env_key = "OMLX_API_KEY"')
    new_lines.extend(preserved_omlx_lines)

    config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Config updated: {config_path}")


class CodexIntegration(Integration):
    """Codex integration that configures ~/.codex/config.toml for oMLX."""

    CONFIG_PATH = CODEX_CONFIG_PATH

    def __init__(self):
        super().__init__(
            name="codex",
            display_name="Codex",
            type="config_file",
            install_check="codex",
            install_hint="npm install -g @openai/codex",
        )

    def get_command(self, ctx: IntegrationContext) -> str:
        return (
            f"{get_cli_command_prefix()} "
            f"launch codex --model {ctx.model or 'select-a-model'}"
        )

    def configure(self, ctx: IntegrationContext) -> None:
        write_codex_config(self.CONFIG_PATH, ctx)

    @staticmethod
    def _find_profile_for_model(content: str, model: str) -> str | None:
        """Return the first ``[profiles.<name>]`` block whose ``model`` key
        equals ``model``, or None.

        Lets users park per-model overrides — ``model_context_window``,
        ``model_auto_compact_token_limit``, ``model_reasoning_effort`` — in
        profile blocks; ``launch`` then invokes codex with ``-p <name>`` so
        the profile's values win over the top-level defaults.
        """
        if not content or not model:
            return None
        current: str | None = None
        for raw in content.splitlines():
            s = raw.strip()
            m = re.match(r'^\[profiles\.([^\]]+)\]$', s)
            if m:
                name = m.group(1).strip()
                if (name.startswith('"') and name.endswith('"')) or (
                    name.startswith("'") and name.endswith("'")
                ):
                    name = name[1:-1]
                current = name
                continue
            if s.startswith('[') and s.endswith(']'):
                current = None
                continue
            if current and '=' in s:
                key, _, val = s.partition('=')
                if key.strip() == 'model':
                    v = val.strip().strip('"').strip("'")
                    if v == model:
                        return current
        return None

    def launch(self, ctx: IntegrationContext) -> None:
        self.configure(ctx)

        env = self._scrubbed_env()
        env["OMLX_API_KEY"] = ctx.auth_token

        # Prefer a user-defined profile whose model matches, so per-model
        # overrides (context window, compaction, reasoning effort) win over
        # the top-level defaults write_codex_config just wrote.
        profile: str | None = None
        if ctx.model:
            try:
                profile = self._find_profile_for_model(
                    self.CONFIG_PATH.read_text(encoding="utf-8"), ctx.model
                )
            except OSError:
                pass

        args = ["codex"]
        if profile:
            args.extend(["-p", profile])
            print(f"Using codex profile '{profile}' for model '{ctx.model}'")
        elif ctx.model:
            args.extend(["-m", ctx.model])
        args.extend(ctx.extra_args)

        os.execvpe("codex", args, env)
