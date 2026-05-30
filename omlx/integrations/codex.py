"""Codex (OpenAI Codex CLI) integration."""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from omlx.integrations.base import Integration
from omlx.utils.install import get_cli_prefix


class CodexIntegration(Integration):
    """Codex integration that configures ~/.codex/config.toml for oMLX."""

    CONFIG_PATH = Path.home() / ".codex" / "config.toml"

    def __init__(self):
        super().__init__(
            name="codex",
            display_name="Codex",
            type="config_file",
            install_check="codex",
            install_hint="npm install -g @openai/codex",
        )

    def get_command(
        self, port: int, api_key: str, model: str, host: str = "127.0.0.1"
    ) -> str:
        return (
            f"{get_cli_prefix()} "
            f"launch codex --model {model or 'select-a-model'}"
        )

    @staticmethod
    def _resolve_compaction_defaults() -> tuple[int, int]:
        """Return (context_window, auto_compact_token_limit) for codex defaults.

        Pulls the configured context window from oMLX settings. The compaction
        threshold is 75% of that — leaves Metal-heap headroom for prefill
        activations during the compact call itself.
        """
        ctx_window = 128000
        try:
            from omlx.settings import GlobalSettings
            settings = GlobalSettings.load()
            if settings.sampling.max_context_window:
                ctx_window = int(settings.sampling.max_context_window)
        except Exception:
            pass
        compact_limit = max(8000, int(ctx_window * 0.75))
        return ctx_window, compact_limit

    def configure(self, port: int, api_key: str, model: str, host: str = "127.0.0.1") -> None:
        config_path = self.CONFIG_PATH
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
            "model": f'"{model or "select-a-model"}"',
            "model_provider": '"omlx"',
        }

        # If it is a reasoning model, add reasoning effort
        is_reasoning = bool(re.search(r'\b(thinking|o1|o3|r1)\b', (model or "").lower()))
        if is_reasoning:
            top_level_overrides["model_reasoning_effort"] = '"high"'

        # Top-level defaults: inserted IF MISSING, never overwritten. These align
        # codex's auto-compaction with oMLX's advertised context window. Without
        # them, codex falls back to its own model-name heuristic (often double the
        # real ceiling) and never triggers auto-compact → "Prompt too long" errors.
        ctx_window, compact_limit = self._resolve_compaction_defaults()
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
                in_omlx_section = (stripped == "[model_providers.omlx]")
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

            # Inside oMLX provider section: drop the 3 managed keys, preserve everything else
            # (user-set timeouts, retries, custom headers, comments, blank lines, …)
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
        new_lines.append(f'base_url = "http://{host}:{port}/v1"')
        new_lines.append('env_key = "OMLX_API_KEY"')
        new_lines.extend(preserved_omlx_lines)

        config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print(f"Config updated: {config_path}")

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

    def launch(
        self,
        port: int,
        api_key: str,
        model: str,
        host: str = "127.0.0.1",
        extra_args: list[str] | None = None,
        **kwargs,
    ) -> None:
        self.configure(port, api_key, model, host=host)

        env = self._scrubbed_env()
        env["OMLX_API_KEY"] = api_key or "omlx"

        profile: str | None = None
        if model:
            try:
                profile = self._find_profile_for_model(
                    self.CONFIG_PATH.read_text(encoding="utf-8"), model
                )
            except OSError:
                pass

        args = ["codex"]
        if profile:
            args.extend(["-p", profile])
            print(f"Using codex profile '{profile}' for model '{model}'")
        elif model:
            args.extend(["-m", model])
        args.extend(extra_args or [])

        os.execvpe("codex", args, env)
