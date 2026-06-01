# Harness In-Place Update & Release Discipline — Design

- **Date:** 2026-06-01
- **Status:** Approved (5-part HITL via harness-brainstorming-plans; adversarial review skipped by user)
- **Author:** Pengbo Ma (with Claude)
- **Prerequisite landed:** PR #26 — stamps `harness_version` + `built_at` into `.harness-meta.json` (the manifest seed).

---

## Section 0 — Problem Understanding

**Who this is for:** the maintainer of the `harness-wf` tool, and every project where the harness has been minted into a `.claude/` directory.

**The pain today.** Improving any part of the harness (dispatcher fix, hook tweak, new skill) can only reach an existing project by **re-minting the entire workspace**. That re-run does a full atomic swap: back up all of `.claude/`, regenerate everything, smart-merge it back, re-validate the plugin, reinstall hooks, rebuild CodeGraph. A one-line fix triggers all of it. Slow, heavy, and — most importantly — **risky**, because it touches everything.

**The ownership danger.** `.claude/` is not all harness. Next to harness files live things the harness must **never** touch: `settings.json` permissions, the user's own custom skills/commands, hand-written docs, and live runtime state (`state/`, `logs/`). Today's all-or-nothing re-mint has no concept of ownership. The `harness-wr` → `harness-wf` rename drift (which turned PR #26 into a manual conflict exercise) is a concrete symptom.

**What is wanted.** Treat the deployed harness like an installable package that updates **itself in place**: `harness-wf update --all` refreshes exactly the files the harness owns, leaves everything else untouched, and when an incoming version genuinely collides with a user edit, **stops and lets the CLI walk the user through resolving it** rather than silently picking a winner. Underneath, a real release discipline (versioned releases, a clear "what changed" story) so a deployed harness can always tell whether it is stale and against what.

**Definition of done.** Updating a deployed harness becomes a scoped, predictable, two-step act (upgrade the tool, then `harness-wf update`) that provably cannot modify a non-harness file, surfaces conflicts for human decision, and is backed by versioned releases the maintainer controls.

---

## Section 1 — Technical Plan

Three pieces plus a discipline change. Most file-moving machinery already exists; it needs to be **scoped** and **exposed**.

**Piece 1 — The ownership manifest (bill of materials).** Grow `.harness-meta.json` (PR #26 seed) into a complete list of every file the harness placed. Per file, record a content hash (what we shipped) and an ownership class: `generated` (overwrite freely — dispatcher, hooks) vs `customizable` (skills, agents, mandate docs). This file is both the **leash** (update only ever touches listed files, so `settings.json` and custom work are structurally invisible) and the **memory** (the recorded hash is the reference point that tells *who* changed a file).

**Piece 2 — The `update` command (in-place refresher).** `harness-wf update --project-path . [--all | --runtime | --skills | ...]`. Reads the manifest; per owned file does a **three-way compare**: *what we last shipped* (manifest hash) vs *what's on disk* vs *what the installed tool wants to ship* (bundled template). Sorts each file into: already-current / safe-to-apply / you-edited-keep / **both-changed-conflict**. Generated files refresh; customizable-only-we-changed refresh; both-changed stop the line → interactive CLI resolution. **No** init heavy machinery: no full backup, no atomic swap, no CodeGraph rebuild.

**Piece 3 — Release discipline (two planes).** Source of "what the tool wants to ship" = the installed `harness-wf` package's bundled templates. Two independent version planes:
- **Tool plane** — `harness-wf` package, versioned by `pyproject.toml`, upgraded with the package manager.
- **Deployed plane** — `.claude/harness-wf-plugin/`, versioned by `.harness-meta.json`, upgraded by `harness-wf update`.

"Holding releases on our end" = formalize the tool plane: tag releases (`v0.2.0`), keep a changelog, SemVer **with intent** (patch = safe runtime fix, minor = additive skills/agents, major = manifest/contract break shipping a migration). Deployed harness compares its stamped version to the installed tool's version to know if it is stale.

**Ecosystem fit.** Mirrors `cruft` (records template origin in a dotfile, 3-way-merges on update) and Debian `dpkg` (fingerprints shipped configs, prompts on conflict). The manifest is also the natural home for the "ship clean — no `__pycache__`/`.venv` pollution" hygiene rule: anything off the manifest does not exist to `update`.

---

## Section 2 — Alternatives Considered & Ruled Out

- **A. Faster re-mint.** Rejected: the problem is the missing ownership boundary, not speed. Faster-but-blind is still blind.
- **B. Blindly overwrite the whole `harness-wf-plugin/`.** Rejected: the live tree holds `state/`, `logs/`, `.venv/`, `.deepeval/` inside the plugin dir; a blind overwrite destroys runtime state. "Mostly ours" is exactly what a manifest handles.
- **C. Two-way merge only (no recorded fingerprint).** Rejected: without a record of what we shipped, a merge cannot tell "you edited" from "we changed" — it guesses, and guessing clobbers. Recording the shipped hash is the cheap upgrade from guessing to knowing. (Most important reason the manifest exists.)
- **D. Auto-merge conflicts silently.** Rejected by explicit user choice: conflicts must be reported and resolved via CLI. Silent 3-way merges on prose produce plausible-but-wrong results.
- **E. Distribute via Claude's native plugin marketplace.** Rejected as primary: covers only plugin files, not the minting tool or non-plugin pieces (root `AGENTS.md`, `rules/`, pointers), and lacks ownership-aware conflict handling. May remain a secondary convenience.
- **F. Full package manager + remote registry now.** Rejected as premature (YAGNI): minimal viable release plane is git tags + SemVer + changelog, optionally install via git ref. PyPI is a later step that only changes the install URL, not the design.
- **G. Store a full pristine copy of every shipped file as the merge base.** Rejected: heavy and unnecessary — the incoming template serves as "theirs," and the hash is enough to detect "did you touch this." 3-way *detection* without 3-way *storage*.

---

## Section 3 — Detailed Implementation Plan

**Scope:** two slices. **Slice 1** (manifest + `update`) is the subsystem. **Slice 2** (release discipline) is ~90% process. Build Slice 1 first; Slice 2 can land in parallel.

### New module layout
```
src/harness/update/
  __init__.py
  manifest.py        # write + read the ownership manifest; hashing; classification
  classification.py  # declarative path-glob -> ownership-class rules + exclusions
  updater.py         # 3-way comparison engine; per-class dispatch; orchestrates a run
  conflict.py        # interactive CLI conflict resolver (keep/overwrite/diff/merge); headless
```

### Files to CREATE

| File | Responsibility | Rationale |
|---|---|---|
| `src/harness/update/__init__.py` | Package marker | Isolate update logic from `init/`. |
| `src/harness/update/classification.py` | One declarative dict: glob → `generated`\|`customizable`, plus `EXCLUDE` set (`state/`, `logs/`, `.venv/`, `.deepeval/`, `__pycache__/`, `*.pyc`, `harness.db`, `uv.lock`). | Ownership boundary as data, auditable in one place. |
| `src/harness/update/manifest.py` | `write_manifest(plugin_dir, harness_dir, platform)` walks the final tree, hashes + classifies each owned file, extends `.harness-meta.json` with `owned`. `read_manifest(path)` loads it. | Bill of materials; recorded hash = merge base. |
| `src/harness/update/updater.py` | `plan_update(...)` → per-file verdict from 3-hash compare; `apply_update(...)` executes, routes conflicts, re-stamps manifest. | Verdict logic separated from side effects → unit-testable truth table. |
| `src/harness/update/conflict.py` | `resolve(path, base, ours, theirs, headless)` → `[K]eep/[O]verwrite/[D]iff/[M]erge-in-$EDITOR`; headless auto-keeps-yours + records conflict. | User decision #1; generalizes existing `handle_code_conflicts`. |
| `tests/unit/test_classification.py` | Known path → right class; pollution excluded; unknown/user path NOT owned. | Locks ownership boundary; proves `settings.json`/user skills invisible. |
| `tests/unit/test_manifest.py` | Round-trip write→read; stable hashes; excluded files never in `owned`; version from `pyproject.toml`. | Manifest complete + clean. |
| `tests/unit/test_updater.py` | Parametrized 4-bucket truth table (3-hash cases), verdict-only, no disk. | Core correctness, data-driven. |
| `tests/unit/test_conflict.py` | Each resolver choice returns right content; headless auto-keeps + records. | Human-in-the-loop + headless safety. |
| `tests/integration/test_update_command.py` | E2E: mint → edit a generated file, a clean customizable file, a conflicting customizable file → `update` → assert refresh, edits preserved, conflict reported, **hand-placed `.claude/settings.json` + a custom skill byte-identical afterward.** | Acceptance test for feature + ownership constraint. |
| `CHANGELOG.md` (root) | Keep-a-Changelog format. | Slice 2: `update --check` surfaces "what changed". |
| `docs/RELEASING.md` | tag → SemVer-intent → (git-ref or PyPI) flow. | Slice 2: repeatable release process. |

### Files to MODIFY

| File | Change | Rationale |
|---|---|---|
| `src/harness/init/cli.py` | Add `update` to `command` choices; arg branch (`--all`/`--runtime`/`--skills`/`--agents`/`--check`); call `manifest.write_manifest(...)` as final init step after atomic swap. | Expose command; ensure every mint ships a complete manifest. |
| `src/harness/init/plugin_generator.py` | `generate_plugin_manifest` keeps version/built_at; defer full `owned` inventory to `manifest.write_manifest` post-swap. | Full file list only knowable after mint completes; PR #26 seed stays. |
| `tests/unit/test_version_stamp.py` (new, small) | Assert `.harness-meta.json` version == `pyproject.toml` version. | Lock the two planes together. |
| `pyproject.toml` | Confirm `src/harness/update/**` auto-included; zero new deps (`hashlib`/`difflib`/`tomllib` stdlib). | Keep runtime slice shippable. |

### TDD task sequence (RED→GREEN→commit each)

**Slice 1 — manifest + engine**
1. `test_classification.py` → `classification.py` (rules dict).
2. `test_manifest.py` → `manifest.py` write/read.
3. Wire `write_manifest` into `cli.py` init final step; extend an init integration test to assert `owned` present + pollution excluded.
4. `test_updater.py` → `updater.plan_update` (verdict, no disk).
5. `test_conflict.py` → `conflict.resolve` (incl. headless).
6. `updater.apply_update` wiring conflicts → `conflict.py`; re-stamp manifest.
7. Add `update` subcommand to `cli.py`; `test_update_command.py` E2E incl. settings.json/custom-skill untouched assertions.

**Slice 2 — release discipline**
8. `test_version_stamp.py` → lock plane alignment.
9. Author `CHANGELOG.md` + `docs/RELEASING.md`; tag `v0.2.0` once Slice 1 lands.

---

## Section 4 — Adversarial Review

Skipped during the HITL process (2026-06-01). An external adversarial pass was run afterward; only the findings that are **true correctness/safety blockers** are recorded below. Environmental/line-ending noise and "user edited a file they shouldn't have" cases were judged out of scope.

### ⚠️ Critical Blockers — MUST resolve before implementing Slice 1

1. **Comparison must be render-aware (else every file false-flags as changed).**
   `minting_engine.py` transforms every file at mint time — Jinja rendering, `.claude`→`target_dir_name`, tool mappings, `@include` inlining. So the on-disk artifact is NOT the raw template. Hashing/diffing the raw template against the rendered on-disk file will mark **everything** as changed and the engine produces garbage verdicts. The manifest hash must be computed over the *rendered* artifact, and the incoming comparison must **re-render the template with the same mint context** before hashing or diffing. This is load-bearing — the feature does not function without it.

2. **A true 3-way merge needs the base TEXT, which the hash-only design cannot reconstruct.**
   The `[M]erge` (and any real conflict resolution) requires Base + Ours + Theirs. The manifest hash detects divergence but cannot regenerate the base text, so as specified `[M]` collapses to an error-prone 2-way merge. The base is recoverable — it equals "the template that shipped at the deployed version" — but ONLY if old template versions are retrievable (the `cruft` model: store a version ref, recover base on demand). This couples to Slice 2 (versioned, retrievable releases). Decision required: either (a) recover base via versioned templates, or (b) honestly downgrade `[M]` to a 2-way merge and drop the 3-way claim. Do not ship the 3-way claim without (a).

3. **The apply phase must be transactional (no partial-state corruption).**
   Removing the atomic swap was over-broad. A sequential file-by-file apply that dies mid-run (exception, or abort during an interactive prompt) strands `.claude/` across versions with the manifest out of sync with disk. Required mitigation: stage all resolved writes, apply them as a single file-set commit, and **re-stamp the manifest last**. Scope atomicity to the resolved owned-file set — do not reintroduce the full-dir backup/swap.

4. **Headless must fail closed, not "auto-keep-yours and proceed."**
   Generated files overwrite while customizable files auto-keep; in headless mode this can ship a generated hook updated against a stale customizable agent it has a contract with — a silent runtime break that reports success. Required: in headless mode a conflict (or a cross-MAJOR version step) **aborts the run, applies nothing, exits non-zero**, and prints the conflict list. Never silently complete a partial update across a contract boundary.
