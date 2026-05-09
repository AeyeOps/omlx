# CLAUDE.md — AeyeOps/omlx fork of jundot/omlx

This is an **AeyeOps fork** of [`jundot/omlx`](https://github.com/jundot/omlx). All contributions in this repo are intended to flow back upstream as PRs. Match upstream conventions exactly so PRs land cleanly.

## Upstream relationship

- Upstream: `jundot/omlx` (Apache-2.0). Author is the primary maintainer; treat the project as theirs, not ours.
- Default branch upstream: `main`. There is no `dev` / `staging` branch — feature branches go straight to `main` via PR.
- Fork remote in this repo: `aeyeops` → `https://github.com/AeyeOps/omlx.git`. Upstream remote: `origin` → `jundot/omlx`. (Inverted from the GitHub default — kept this way intentionally so `git pull` tracks upstream.)

## Contribution rules (from upstream `docs/CONTRIBUTING.md`)

1. **Branch from `main`** — `git checkout -b <type>/<short-description>`.
2. **Conventional Commits** matching their merge style: `fix(scope): …`, `feat(scope): …`, `deps: …`. Scope examples already merged: `scheduler`, `engine`, `tool_calling`, `oq`, `dflash`, `app`, `i18n`. Use the smallest accurate scope.
3. **One PR, one concern.** Don't bundle unrelated changes. Two upstreamable fixes → two PRs even if developed together.
4. **SPDX header** on any new source file: `# SPDX-License-Identifier: Apache-2.0`. Don't add it to files that already had it; don't strip it.
5. **Tests required** for new code. File-naming convention: source `omlx/<module>.py` → test `tests/test_<module>.py`. Markers in use:
   - `@pytest.mark.slow` — needs model files; skip during dev.
   - `@pytest.mark.integration` — needs a running server.
   - The dev-loop command is `pytest -m "not slow"`. Run this before every push.
6. **PR target = `main`.** Open against `jundot/omlx:main` from `AeyeOps/omlx:<branch>`. Cross-repo PR (the standard fork model). 100% of recent merged PRs come from forks; there is no path that avoids forking.
7. **Describe what changed and why.** No template, but maintainer reads PR bodies — explain the symptom, the fix, the trade-offs, and any operator-visible behavior change (e.g. a new required CLI flag).

## Don'ts

- Don't push code/feature commits directly to `aeyeops/main`. The fork's `main` exists to track upstream so we can rebase clean feature branches off it. To sync: `git fetch origin && git checkout main && git merge --ff-only origin/main && git push aeyeops main`.
  - **Exception:** fork-only metadata files (this `CLAUDE.md`, fork-specific READMEs) live on `aeyeops/main` and never go upstream. They are committed directly to `main`. They must NEVER appear in feature branches we PR upstream — when starting a feature branch, branch from `origin/main` not from `aeyeops/main`, or `git restore --source=origin/main -- CLAUDE.md && git rm CLAUDE.md` before the first feature commit.
- Don't open issue + PR pairs for small fixes — recent merge history shows maintainer accepts standalone PRs without prior issue.
- Don't `--force-push` to a branch that already has an open PR comment thread without warning the maintainer.
- Don't skip hooks or sign-off. There is no DCO requirement, but commits should still be unsigned-off-only if local config says so — match repo convention.
- Don't bundle a workaround monkey-patch with a real fix. If the fix is a stop-gap (e.g. our ChunkedKVCache batch=1 patch), call it out in the PR body and offer to follow up with the proper version.

## How Claude should behave when working in this repo

- **Pause before push.** External-visible actions (push, open PR, comment on issue) require explicit user confirmation each time. Don't autopush even after green tests.
- **Pause before destructive ops** on the fork (`gh repo delete`, force-push to main, branch deletion). Token currently lacks `delete_repo` scope; that's fine, treat it as a guardrail.
- **Match maintainer cadence.** Recent merged PRs are typically <100 LOC. If a change wants to grow, split it.
- **Verify upstream is current** before opening a PR: `git fetch origin && git log --oneline aeyeops/<branch> ^origin/main` should show only the intended commits. If `origin/main` has moved, rebase the branch.
- **Run `pytest -m "not slow"`** in the project venv before any push. If the local environment can't run the suite (no mlx_lm install), say so explicitly in the PR body — don't claim "tests pass" without evidence.
- **Don't fabricate maintainer preferences.** What's documented in `docs/CONTRIBUTING.md` and visible in merged PR style is authoritative; everything else is the user's call.

## Current in-flight branches

| Branch | Purpose | Upstream PR target |
|---|---|---|
| `fix-chunkedkvcache-llama4-batch1` | `omlx/scheduler.py` monkey-patches `ChunkedKVCache.{merge,filter,extract,size,extend}` so Llama-4 (Scout/Maverick) chat completions stop 500'ing in `_merge_caches`. Requires `--max-concurrent-requests 1`. | `jundot/omlx:main` |
| `feat-tool-calling-llama3-json-format` | Adds Llama-3-style `{"name","parameters"}` JSON content extractor to `parse_tool_calls`, gated on the request's `tools` list. Includes 6 unit tests in `tests/test_tool_calling.py`. | `jundot/omlx:main` |

Both off `main`, single conventional-commit each. Pushed to `aeyeops` when explicitly approved by user.

## Project layout (from upstream README, mirror exactly)

```
omlx/
├── omlx/                  # Main package
│   ├── api/               # API models + adapters (openai, anthropic, tool_calling)
│   ├── cache/             # KV cache management (paged / prefix / SSD)
│   ├── engine/            # Inference engines (simple / batched / vlm / embedding)
│   ├── mcp/               # Model Context Protocol integration
│   ├── models/            # Model wrappers
│   ├── utils/             # Utilities
│   ├── server.py          # FastAPI server
│   ├── scheduler.py       # Request scheduler (runs mlx_lm BatchGenerator)
│   ├── engine_core.py     # Core async inference engine
│   ├── paged_cache.py     # Block-based KV cache + LRU eviction
│   └── cli.py             # `omlx serve …` entry point
├── packaging/             # macOS menubar app (PyObjC)
├── tests/                 # pytest suite
└── docs/                  # CONTRIBUTING, architecture
```

## Useful commands

```bash
# Sync fork main with upstream
git fetch origin
git checkout main && git merge --ff-only origin/main && git push aeyeops main

# Start a feature
git checkout main
git checkout -b fix/<scope>-<short>

# Dev install + fast tests
pip install -e ".[dev]"
pytest -m "not slow"

# After commit, before push: rebase if upstream moved
git fetch origin && git rebase origin/main

# Push & PR (only on user OK)
git push -u aeyeops <branch>
gh pr create --repo jundot/omlx --base main --head AeyeOps:<branch> \
  --title "<conventional commit subject>" --body "$(cat <<'EOF'
…
EOF
)"
```
