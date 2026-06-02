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

### Reworked Resolutions — Fixes 1 & 2 (supersede the original chat proposals)

A code-grounded review (verified against `minting_engine.py`, `plugin_generator.py`) showed the original fixes for Blockers 1 & 2 fail because (a) the on-disk render is **not** reproducible from `{harness_dir_name, platform, project_slug}` — it also depends on ghost-injected `CONTEXT.md` invariants (`implementer.md`), `selected_agents`, and the injected ingestion key; and (b) `agents.json`/`rules.json`/orchestrator config **embed the rendered `.md` source** (`export_*_config`, `"source": f.read()`), so overwriting the `generated` JSON from the new template silently reverts a user `.md` edit and desyncs the dispatcher (which reads the JSON). The rework below replaces both fixes.

**R1 — Detect with a two-hash split; never compare in rendered space.** Stop trying to re-render the incoming template to match the deployed file. Record **two** fingerprints per owned file and answer two independent questions in the space where each is deterministic:
- `source_hash` — hash of the **raw upstream source** (the template file, or the runtime module for `copy_runtime_modules` artifacts) at ship time. *"Did WE change it?"* = new-package source_hash ≠ manifest source_hash. Pure template-space; rendering never enters.
- `rendered_hash` — normalized (LF, trailing-WS-stripped) hash of the **on-disk bytes** at ship time. *"Did the USER edit it?"* = current-disk hash ≠ manifest rendered_hash. Both sides are rendered, so ghost-injection/selected_agents/key content **cancels** — no false positives.

Verdict truth table:

| we_changed | user_edited | verdict |
|---|---|---|
| no | no | current (skip) |
| yes | no | apply |
| no | yes | keep-yours |
| yes | yes | CONFLICT |

This eliminates Blocker 1's false-positive storm without storing render context for *detection*. Re-rendering is needed only to **produce** an updated file on `apply`/`theirs`, via a per-file `producer` (below) — and a render/rewrite failure there must be **surfaced, not swallowed** (current pipeline silently `except: pass` on render — that must not carry into update).

**R2 — A third ownership class `derived`, to kill the `.json`↔`.md` desync.** Classes become:
- `generated` — overwrite from upstream (runtime code, hooks).
- `customizable` — 3-way merge (`.md` mandate/skill/agent files).
- `derived` — **regenerate from the post-merge `customizable` sources, never compared or overwritten from a template.** `agents.json`, `rules.json`, orchestrator config are `derived`: after the `.md` files are merged/applied, re-run `export_*_config` over the final on-disk `.md` set so the JSON the dispatcher reads always matches the merged source. Manifest records `derived_from: [<source .md relpaths>]`.

**R3 — Per-file `producer` tag drives reproduction.** Detection is uniform (two hashes); production is not. Tag each owned file:
- `template` — Jinja + `.claude`→dir + tool_mappings + `@include`; reproducible from stored `render_context {harness_dir_name, platform}` (tool_mappings/subagent syntax derive from the platform profile; `selected_agents` recorded too — currently `[]` on the Claude path but must be captured if populated).
- `runtime_copy` — `copy_runtime_modules` regex import-rewrite / string-emit (`dispatcher.py`, `runtime_adapter.py`, emitted `platform_adapter.py`, …). NOT Jinja — update re-runs the rewrite, not the renderer.
- `export` — the `derived` JSON projections (see R2).
- `verbatim` — copied unchanged.

**R4 — Split `implementer.md` at the ghost-injection marker.** The harness owns `implementer.md` only **up to** the exact line `### STRICT INVARIANTS (Ghost Injection)` (`minting_engine.py:210`); everything after is project-owned and never touched. Base/theirs cover only the harness portion (now reproducible), the invariants tail is preserved verbatim. This is the only special-case needed to make the customizable agent set reproducible.

**R5 — Exclude `.env.telemetry-harness` from the manifest.** It carries the real ingestion key; it is post-mint config, not something `update` should refresh. Add it to the `EXCLUDE` set alongside `state/`, `logs/`, `.venv/`, `.deepeval/`, `__pycache__/`, `*.pyc`, `harness.db`, `uv.lock`.

**R6 — Real 3-way merge via `git merge-file`, not `merge_markdown`.** Keep the gzipped **base sidecar** for `customizable` files only — that part of the original Fix 2 was correct and removes the dependency on retrievable old releases. But the merge engine must be a true diff3: shell out to `git merge-file -p <ours> <base> <theirs>` (verified available; operates on loose files, no repo needed), which emits standard conflict markers and a conflict exit code. The existing `merge_markdown` is a lossy section-*union* with no conflict detection (the "plausible-but-wrong" behavior Alt-D rejected) and must NOT be used for conflict resolution; it may remain only for purely-additive, non-conflicting cases.

**R7 — Source-driven file discovery (resolves the "new file" leash contradiction).** Because detection is keyed off upstream `source_hash`, the plan iterates the **new package's** producer-paths, not only the existing manifest. A producer-path present upstream but absent from the manifest = a **new** owned file to deliver; a manifest entry whose upstream source no longer exists = a **removed** file (emit an explicit remove verdict; for `customizable`, treat as a conflict class needing human/headless-stop). The "leash" is therefore "files matching harness producer-paths," which both delivers new harness files and still cannot touch anything outside the producer mapping (user files remain invisible).

**Revised manifest schema (supersedes Section 3's sketch):**
```
.harness-meta.json
  harness_version, built_at                 # PR #26
  render_context: { harness_dir_name, platform, selected_agents }
  owned: { <relpath>: {
      class: generated|customizable|derived,
      producer: template|runtime_copy|export|verbatim,
      source_path: <package-relative upstream path | null for derived>,
      source_hash, rendered_hash,
      derived_from: [..]            # derived only
      owned_until_marker: "..."     # split files only (implementer.md)
  } }
.harness-meta/base/<relpath>.gz             # customizable files only
EXCLUDE += .env.telemetry-harness
```

### Reworked Resolutions — Fixes 3 & 4 (close the SOUND-WITH-GAPS items)

**R8 — Transactional apply via a write-ahead journal + startup recovery.** Per-file `os.replace` is atomic per file but not per file-*set*; a crash mid-commit half-applies. Make the multi-file commit effectively atomic with a strict five-phase flow:
1. **Plan** — pure, no writes.
2. **Resolve** — collect ALL conflict decisions up front, before any disk write. Catch `EOFError`/`KeyboardInterrupt` here (piped/CI stdin) and route to a clean abort — nothing is staged yet, so disk is pristine.
3. **Stage** — write every final output into `.claude/.harness_update_tmp/`. Crucially, `derived` JSON is regenerated from the **staged** merged `.md` (not the live tree), so the staging set is internally consistent before anything is committed.
4. **Journal + Commit** — write `.harness-update-journal.json` listing every planned `(target, staged, backup)` triple; then `os.replace` each staged file into place, moving each original into `.harness_update_tmp/backup/`; then stamp the new manifest; then delete the journal.
5. **Cleanup** — remove the staging dir.

   **Recovery:** at the *start* of every `update` (and `init`), if a journal exists, a prior run died mid-commit → restore every original from `backup/`, delete the journal, discard staging, and only then proceed. Either the journal is gone (commit fully succeeded) or recovery restores the exact pre-update state. The `.md` and its `derived` JSON are always in the same journaled batch, so the dispatcher's JSON view can never be left mismatched.

**R9 — Replace the contract-group map with version-step semantics (it was going to rot anyway).** The review's worry was a hand-authored "contract group" list drifting out of date. The R1–R8 reworks dissolve most of the need for it:
- The `.md`↔`.json`↔dispatcher contract is now **structural** — `derived` JSON is always regenerated from the merged `.md` (R2), so it can never desync; it is not a conflict group at all.
- All `generated`/`runtime_copy` files come from **one** package version and commit atomically (R8), so they are mutually consistent by construction — no partial-apply risk among them.
- The only residual cross-class contract risk is a new `generated` runtime file paired with a `customizable` file the user **kept** on conflict. The clean signal for "that pairing might now be incompatible" is the **SemVer-MAJOR** boundary (MAJOR = contract break, per the release discipline). So gate on the version step, not on an enumerated map:
  - **Same MAJOR:** generated overwrite freely; customizable conflicts resolve individually; a kept-old customizable file is guaranteed contract-compatible. No grouping needed.
  - **Across a MAJOR:** refuse a piecemeal update; require the release's **migration** step or a full re-mint. Headless aborts (exit non-zero); interactive explains the major upgrade needs migration and applies nothing.

**R10 — Define `requires_human` precisely, incl. missing/old version.** Headless / `--check` fail-closed triggers when ANY of:
- a `CONFLICT` verdict exists; or
- a `customizable` **remove** verdict exists (upstream dropped a file the user may depend on — generated removes are safe to apply, customizable removes need a human); or
- deployed→incoming crosses a **MAJOR**; or
- `harness_version` is **absent or unparseable** (do NOT assume `0.0.0`); or
- the **manifest is absent** entirely (a pre-manifest mint — not update-capable; instruct full re-mint, or offer an `--adopt` mode that best-effort synthesizes a manifest by hashing the current tree as base).

On any trigger in headless: print the reasons + file list, apply nothing, exit non-zero. Apply automatically only when the plan is fully clean within the same MAJOR.

**R11 — `--force` cannot reintroduce a partial-contract state.** `--force` redefines conflicts to "take theirs (overwrite)" but still (a) commits through the atomic journal (R8), so it is all-or-nothing, and (b) still refuses to cross a MAJOR without an explicit `--force-major` *and* a present migration. Because derived JSON is regenerated and generated files are single-version, a forced run cannot produce the silent generated-new/customizable-stale mismatch Blocker 4 described.

**Manifest/CLI additions for R8–R11:**
```
.claude/harness-wf-plugin/.harness-update-journal.json   # transient; present only mid-commit
.claude/.harness_update_tmp/backup/<relpath>             # originals, for rollback
update flags: --check (dry-run) · --force · --force-major · --adopt · --non-interactive
```

All four blockers are now resolved at design level; remaining work is execution per the Section 3 TDD sequence (extended with journal-recovery and version-gate tests).

### Phase B — Locked Decisions (2026-06-01)

User decisions for the producer-reproduction phase:

- **D1 — Refactor + characterization (not duplicate).** `mint_workspace` and `copy_runtime_modules` will be refactored to *call* the new pure functions (`render_template`, per-file runtime reproduction), so there is a single source of truth and no drift. Mandatory: pin current output **byte-for-byte** with characterization tests *before* refactoring.
- **D2 — Replicate current render quirks exactly.** Reproduce the naive `.claude`→dir `str.replace`, the word-boundary regex pass in `assemble_layout`, and the silent `try/except: pass` Jinja-failure behavior faithfully, so `rendered_hash` matches existing deployments. The quirks are filed as separate bugs to fix later under a versioned MAJOR (which ships a migration), never silently.
- **D6 — Whole-harness scope via an explicit OWNED-ROOTS allow-list.** `update` does NOT walk all of `.claude/`. It enumerates only known harness roots; user-custom files are never even looked at. Ownership stays a *positive* allow-list (classification) AND is gated by manifest membership — two independent gates. Conflict resolution outside the plugin is identical (base sidecar + `git merge-file` keyed by relpath).
- **D4 — Emitted files made reproducible.** `platform_adapter.py` is re-emitted from `platform` and hashed (upgrades verdict from `unknown` to real).
- **D5 — Single source of truth for the runtime file list.** Dedupe `copy_runtime_modules.core_files` and `classification.RUNTIME_SOURCE_MAP` into one shared mapping both import.
- **D7 — Derived JSON regenerated from ALL `.md` in scope** (matches current mint behavior, incl. user-added agents). **D8 — `derived_from` hardcoded** (only 2–3 projections).

**Verified OWNED-ROOTS inventory** (sources confirmed against `templates/boilerplate/`):
```
harness-wf-plugin/                  # the plugin (full subtree, per classification)
rules/                              # customizable .md  -> feeds rules.json
AGENTS.md                           # customizable
agent.json, skills.json            # generated/derived projections (verify derivation)
orchestrator.md                    # customizable, IF present -> feeds orchestrator.json
.claude-plugin/marketplace.json    # generated
```
**Explicitly NOT owned** (user territory — never enumerated): `docs/` (holds the user's own design/progress docs, including this file), `settings.json`, `settings.local.json`, and anything without a harness producer-path.

**Two follow-ups before B3:** (1) confirm whether `agent.json`/`skills.json` are static templates or derived projections; (2) restrict R7 new-file *delivery* outside the plugin to the explicit owned-roots only — never invent a new path in user territory.

### Phase B — Decisions, round 2 (2026-06-01)

- **Distribution = PyPI from the start.** `harness-wf` publishes to PyPI; consumers `uv tool install harness-wf` and upgrade with `uv tool upgrade`. "theirs" at update time = the installed package version; base = local sidecar (no registry fetch needed for base). `docs/RELEASING.md` updated to PyPI-primary. **Source of truth = this repo's `main` + SemVer git tags**; `pyproject.toml` version → stamped into `.harness-meta.json` → the per-deployment pin.
- **`agent.json`, `skills.json`, AND `rules/` are used only by the harness** (no Claude-native or docs consumer). `skills.json`'s sole reference is a *pointer string* in `dispatcher.py:243`; the dispatcher reads `rules.json` (`dispatcher.py:142`), not `rules/*.md`; the `../rules/` `@includes` are inlined at mint *before* `assemble_layout`. **Decision (B0): relocate `agent.json`, `skills.json`, and `rules/` INTO the plugin** (`harness-wf-plugin/`), then classify the JSON as **generated/overwrite-freely** and `rules/*.md` as **customizable**. **`AGENTS.md` stays at `.claude/` level** — `CLAUDE.md` points to it (`minting_engine.py:265`); moving it would break the entry-surface pointer.
  - **Implication — this is a file relocation = a migration-worthy (MAJOR) change**, like `wr→wf`. It must ship a migration that removes the old `.claude/`-root copies (`agent.json`, `skills.json`, `rules/`) and writes the new in-plugin ones; existing deployments otherwise orphan the old files. (The migration runner fully matters once apply/Phase C exists; the mint-layout change can land first.)
  - **Implication — `dispatcher.py:243`** builds `"{platform}/skills.json"` (e.g. `.claude/skills.json`); it must become plugin-relative (`${CLAUDE_PLUGIN_ROOT}/skills.json`). **`export_rules_config`** must read `plugin/rules/` instead of `harness_dir/rules/` (one-line path change). Add dispatcher + export tests.
- **Edge files:** **`docs/` is excluded entirely** (user territory — holds the user's design/progress docs). **`orchestrator.md` is owned only when present**, never required (absent in the dogfood repo).
- **D3 — Characterization vehicle = lightweight render fixture + one e2e backstop.** Pin B1's render output via unit-level fixtures (known templates → fixed context → exact-output assertions; fast, no npx/codegraph in CI), with one full headless mint as a periodic backstop. **Sequencing: B0 → re-baseline → B1** (B0 changes mint output intentionally, so characterize the post-B0 layout).

Revised owned-roots inventory (after B0):
```
harness-wf-plugin/                  # plugin — now also contains agent.json, skills.json, rules/
AGENTS.md                           # customizable — STAYS external (CLAUDE.md pointer)
.claude-plugin/marketplace.json    # generated
orchestrator.md                    # customizable, IF present (absent here)
# NOT owned: docs/, settings.json, settings.local.json, anything w/o a producer-path
```
