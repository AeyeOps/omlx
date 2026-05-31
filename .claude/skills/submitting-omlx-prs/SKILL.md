---
name: submitting-omlx-prs
description: Prepares and opens upstream pull requests from the AeyeOps/omlx fork to the jundot/omlx repository so they land with the highest chance of acceptance. Use when opening, scoping, sizing, splitting, branching, commit-naming, body-writing, testing, or reviewing any omlx upstream contribution from this fork — including deciding whether a change is one concern, drafting the conventional-commit headline and PR body, satisfying the macOS Python 3.11/3.12/3.13 CI gate, or responding to maintainer review.
---

# Submitting omlx upstream PRs

Use this when you are about to open (or are iterating on) a PR from the `omlx` fork to upstream `jundot/omlx`. It distills what actually gets merged versus closed-without-merge. Read the pre-flight checklist first; it is the gate.

## How the maintainer actually merges

Internalize this — it explains every other rule:

- The maintainer reads bodies and diffs closely, reproduces the bug, and often lands a good change by **cherry-picking the single useful hunk with your authorship preserved, then closing the PR.** A "closed" PR frequently means your fix shipped — just lifted out of a larger or messier diff. Optimize every PR to be **liftable in one commit**.
- They prefer **automatic, zero-config behavior** over a knob the operator must reason about, and a **smaller competing diff** over a larger one that does the same thing.
- They are wary of anything that **adds ongoing support burden** (global runtime monkey-patches, manual tunables, workflow changes).

So: one concern, small, self-contained, with the proof attached. That shape is what survives.

## Pre-flight checklist (all must pass before you push)

- [ ] **Branch off current `origin/main`.** Cut the feature branch FROM up-to-date upstream main, named `<type>/<short-desc>` (e.g. `fix/oq-eager-sanitize`). Branching off a local main that is ahead of upstream makes GitHub compute the cross-fork diff as *all* your in-flight commits — the single most common cause of an accidental fat PR.
- [ ] **One concern only.** This PR fixes exactly one cohesive thing. If you developed two fixes together, they are still two PRs. Bundling is the most common reason a PR gets trimmed to one hunk and closed.
- [ ] **Substantive diff is small** — well under ~100 LOC where possible. If the feature is genuinely large, explicitly defer adjacent work to follow-up PRs and say so in the body.
- [ ] **Conventional Commit headline** with the smallest accurate omlx scope: `fix(oq): ...`, `feat(cache): ...`, `refactor(engine): ...`. No `Update oq.py`-style headlines.
- [ ] **SPDX header on every NEW source file:** `# SPDX-License-Identifier: Apache-2.0`. Do not add it to files that already have it; do not strip it.
- [ ] **Tests added** for new code, named `tests/test_<module>.py`, exercising the branches you changed. Prefer a regression test that fails on old code and passes on new.
- [ ] **CI gate is green locally:** `pytest -m "not slow and not integration"` passes. The merge gate runs this on macOS across Python 3.11, 3.12, 3.13.
- [ ] **The diff is the surgical change you intended** — not a degenerate artifact (a full-file deletion, an auto-formatter reflow, accidental whitespace churn).
- [ ] **No self-flagging** as untested, AI-assisted, or outside your expertise. Present evidence instead.

## What gets merged

- **Single, cohesive concern.** One bug, one feature, or one tightly-themed set that closes a linked issue. Lands on its own merits.
- **An isolable, minimal hunk.** A small, self-contained, one-concern diff is trivially cherry-pickable; a fat or entangled one is not. Optimize for "liftable in one commit" so the change survives even if the PR is restructured.
- **Correct root-cause fix, not a symptom mask.** Fix the actual upstream cause (wrong scope, wrong sanitize path, dropped parameter) and name the exact bug so the maintainer can verify without re-deriving. Route a flag to the correct code path rather than adding a late guard.
- **Automatic and zero-config beats a tunable.** When the goal can be met by auto-tuning (watermark- or EWMA-driven throttling, tiered safety presets) instead of a flag the operator must set, the automatic version is preferred — even over a working manual knob. If a knob is unavoidable, default it to current behavior and justify why auto won't do.
- **A body with a real narrative:** symptom → root cause → fix → trade-offs → operator-visible change. Maintainers read bodies and reward correct framing.
- **A matching test**, ideally a fail-then-pass regression test that removes reviewer doubt.
- **Concrete verification evidence:** copy-pasteable repro/test commands, hard repro data (socket/handle counts, before/after tensor counts, crash frames), benchmark tables with sample counts, or UI screenshots. Let the reviewer reproduce rather than trust.
- **Changes kept off hot paths.** Add instrumentation and new behavior through a clean abstraction (snapshot/poll differencing, explicit dispatch, no-op gating for unaffected models). Bounding blast radius earns trust on larger diffs.
- **Fail-loud design.** Raise an identifiable error on a broken invariant rather than silently falling back to a degraded path that looks like the real thing.
- **New auto-behavior that preserves the existing explicit path** untouched, with an opt-out flag defaulting to current behavior.
- **Disciplined signature changes.** When you change a function signature, switch existing callers to keyword arguments in the same pass; reference only fields that exist on the target dataclass and enum/whitelist values that match real upstream identifiers.
- **Point-by-point review responses.** Reply to every review point with a concrete fix and request re-review. Fix broken default-on paths before merge rather than shipping a feature disabled.
- **Tracking upstream API drift.** If a dependency's interface changes mid-review, rework onto the new interface and re-signal readiness; drive an exposed upstream bug to merge and pin a clean version so an interim monkey-patch can be dropped.

## What gets rejected (and the do-instead)

- **Bundling unrelated changes.** A bugfix plus speculative hardening, two independent fixes, a behavior fix plus UX polish — the maintainer cherry-picks the one good hunk with co-author credit and closes the rest. **Do:** split into one-concern PRs so the whole thing merges, not just a slice.
- **A manual knob where auto-tuning would serve the average user.** A per-model tunable that users must reason about (and can set unsafely) is declined in favor of an automatic, self-bounding policy. **Do:** make it adaptive; if a knob is unavoidable, default to current behavior and keep it off the average user's path.
- **Adding another global runtime monkey-patch.** Wraps of library internals (model load, glob, sanitize) are a fragile support burden that must coexist with the existing patch stack — even a correct one is often declined. A patch installed *after* the code it means to fix already ran does nothing. **Do:** prefer a self-guarding, narrowly-scoped patch installed in the correct pre-load hook; better, fix it in the dependency upstream and pin a clean version. Rely on the model's own type-based dispatch instead of `hasattr`-style re-routing.
- **Clean code that doesn't move the metric that matters (design-fit).** A well-written change is declined when it optimizes the wrong layer — shrinking a cold/secondary footprint while the binding constraint is active unified memory, or adding calibration samples a downstream step subsamples away. **Do:** confirm your change actually moves the constraint the project cares about, and lead the body with that number.
- **Symptom patching.** A fix that clears one warning but breaks a sibling path under a different config (e.g. an all-NaN result when an optional input is absent) reads as incomplete. **Do:** fix the root cause and cover every config the change touches.
- **A ballooning or degenerate diff.** A full-file deletion is unmergeable on its face; an auto-formatter reflow inside a feature PR inflates the diff and draws rebuke even when the feature merges. **Do:** confirm the final diff is your intended surgical change; keep formatting passes in their own PR.
- **A stale or accidentally-fat branch.** Branching off a local main that is ahead of upstream makes the cross-fork diff include all your in-flight commits; a branch many commits behind invites a re-land over a merge. **Do:** rebase on current upstream `main` before opening and after any peer reports a failing test; verify the diff shows only your change.
- **Dead-code "fixes."** A branch that only fires when settings are `None` while every caller passes populated settings changes nothing. **Do:** confirm real callers reach the branch you modified before claiming a fix.
- **Guessed framework or library semantics.** Glob-shaped CORS origins that the framework matches literally; whitelist values that don't match real parser names; invented config fields that silently drop entries. **Do:** verify literal-vs-regex matching, real enum/identifier values, and real upstream parser names against the source.
- **Hardening an internal boundary the maintainer already controls.** Adds risk and review surface without value. **Do:** target real external-input boundaries.
- **Losing to a smaller competing fix, or redundant work.** When two PRs address the same issue, the minimal diff that preserves existing invariants (a whitelist kept closed rather than opened to arbitrary input) tends to win; a change already on main is closed as redundant. **Do:** open early, prefer the smallest change that holds the invariant, and sync on current main first to confirm it isn't already landed or in flight.
- **Unverified claims.** A checked-off Test Plan asserting results the changed branch cannot produce — or self-flagging the work as untested/AI-assisted/out-of-depth — destroys trust faster than any bug. **Do:** ship a branch-covering `tests/test_<module>.py`, validate across affected configs, and claim only what you actually verified.

## Writing the PR body

No template exists, but the maintainer reads the body. Keep it tight and structured around:

- **Symptom** — what the user/operator observes that is wrong.
- **Root cause** — the exact bug, named precisely (scoping, wrong sanitize path, dropped parameter, thread/lifetime hazard), so the reviewer can verify without re-deriving.
- **Fix** — what you changed and why it addresses the cause, not the symptom.
- **Trade-offs** — anything given up, blast radius, what is deferred to a follow-up.
- **Operator-visible change** — new CLI flag, new config key, changed default. Call these out explicitly.
- **Verification** — the repro command(s) and hard evidence (counts, traces, a benchmark table with sample counts, screenshots). If a change is template/i18n-only and tests do not apply, say so.

Do not pad with a false Test Plan. Claim only what the code delivers.

## Commit and branch hygiene

- **Conventional Commits**, smallest accurate scope. Real omlx scopes: `scheduler`, `engine`, `tool_calling`, `cache`, `server`, `oq`, `dflash`, `app`, `i18n`, `mcp`, `cli`. Prefixes: `fix(scope):`, `feat(scope):`, `deps:`, `docs:`, `chore:`, `refactor:`. If a change fits no scope, omit it (e.g. `docs:`). Do not invent prefixes or scopes.
- **Branch naming:** `<type>/<short-desc>`, cut from current upstream `main`.
- **Cross-repo fork PR model:** head = your fork branch, base = `jundot/omlx:main`. Recent merges come from forks; no prior issue is required for small fixes.

Generic command shape (replace placeholders; no personal paths):

```
git fetch upstream
git checkout -b fix/<short-desc> upstream/main
# ... make the one-concern change + test ...
git push <your-fork-remote> fix/<short-desc>
gh pr create --repo jundot/omlx \
  --base main \
  --head <your-fork-owner>:fix/<short-desc> \
  --title "fix(<scope>): <one-line summary>" \
  --body-file <your-body-file>
```

## Before you push

Run the exact local gate that mirrors CI:

```
pip install -e ".[mcp]"
pip install pytest pytest-asyncio
pytest -m "not slow and not integration"
```

There is NO linter/formatter gate, NO DCO/sign-off, NO coverage gate — green tests on the matrix is the bar. Markers: `@pytest.mark.slow` (needs model files), `@pytest.mark.integration` (needs a running server); both are excluded from the merge gate.

**Honesty rule:** if you cannot run the suite (no Apple Silicon, no model files, no server), say so plainly in the PR body and state exactly what you did verify. Never claim tests pass without evidence — a Test Plan asserting results you did not produce is the fastest way to lose the maintainer's trust.
