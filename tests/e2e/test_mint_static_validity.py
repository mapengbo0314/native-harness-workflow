"""
S1-T7 — L3 static validity & hygiene.

Asserts that every artifact produced by a fresh mint is well-formed,
clean, and platform-coherent.  Parametrized over ["claude", "gemini"].

Checks
------
1. JSON manifests parse cleanly (every *.json under the plugin root).
2. SKILL.md frontmatter — every SKILL.md has YAML frontmatter with
   non-empty `name` and `description`.
3. Agent .md frontmatter — every agent *.md has YAML frontmatter with
   non-empty `name` and `description`.
4. Hook scripts compile — every hooks/*.py passes py_compile.compile.
5. Runtime slice standalone invariant — no file under src/ contains a
   `harness.` package import (import harness / from harness).
6. Hygiene — ZERO __pycache__ directories and ZERO *.pyc files anywhere
   under the plugin root.  A fresh mint previously shipped stale
   cpython-311 bytecode under src/ (and hooks/) created during the
   _validate_claude_plugin() step; a fix was applied to cli.py.
7. Tool-mapping translation (claude only) — minted skill/agent text must
   NOT contain the un-translated source tokens that the Claude adapter's
   get_tool_mappings() says should have been replaced.  Gemini's mappings
   are identity (no-op), so no assertion is needed there.

Real bugs caught
----------------
BUG-3  Fresh mint shipped stale cpython-311 bytecode under src/__pycache__/
       and hooks/__pycache__/ — created by _validate_claude_plugin() calling
       exec_module(dispatcher_module), which transitively compiled hook
       scripts.  Fix: added a pycache cleanup sweep at the end of
       _validate_claude_plugin() in src/harness/init/cli.py.
"""

from __future__ import annotations

import json
import py_compile
import tempfile
from pathlib import Path

import pytest
import yaml

from tests.e2e._mint_helpers import mint_platform

# ---------------------------------------------------------------------------
# Session-scoped fixtures — mint once per platform per test session
# (mirrors the pattern in test_mint_and_verify_matrix.py)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _claude_root_validity(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("validity_claude")
    return mint_platform(tmp, "claude")


@pytest.fixture(scope="session")
def _gemini_root_validity(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("validity_gemini")
    return mint_platform(tmp, "gemini")


@pytest.fixture(
    params=["claude", "gemini"],
    scope="session",
)
def validity_plugin_root(request, _claude_root_validity, _gemini_root_validity) -> tuple[str, Path]:
    """Yields (platform, plugin_root) for parametrized validity tests."""
    if request.param == "claude":
        return "claude", _claude_root_validity
    return "gemini", _gemini_root_validity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> dict | None:
    """
    Tolerant YAML frontmatter parser.

    Splits on '---' delimiters and attempts yaml.safe_load on the first
    block.  Returns the parsed dict, or None if no frontmatter is found
    or parsing fails.
    """
    stripped = content.lstrip()
    if not stripped.startswith("---"):
        return None
    parts = stripped.split("---", 2)
    # parts[0] == '' (before first ---), parts[1] == fm body, parts[2] == rest
    if len(parts) < 3:
        return None
    try:
        result = yaml.safe_load(parts[1])
        return result if isinstance(result, dict) else None
    except yaml.YAMLError:
        return None


# ---------------------------------------------------------------------------
# Check 1: JSON manifests parse
# ---------------------------------------------------------------------------


class TestJsonManifestsParse:
    """Every *.json file under the plugin root must parse without error."""

    def test_all_json_manifests_parse(self, validity_plugin_root: tuple[str, Path]) -> None:
        platform, root = validity_plugin_root
        failed: list[str] = []
        for json_file in sorted(root.rglob("*.json")):
            try:
                json.loads(json_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                failed.append(f"  {json_file.relative_to(root)}: {exc}")

        assert not failed, (
            f"{platform}: JSON manifests that fail to parse ({len(failed)}):\n"
            + "\n".join(failed)
        )


# ---------------------------------------------------------------------------
# Check 2 + 3: SKILL.md and agent .md frontmatter
# ---------------------------------------------------------------------------


class TestFrontmatterValidity:
    """Every SKILL.md and agent *.md must have YAML frontmatter with name + description."""

    def test_skill_md_frontmatter(self, validity_plugin_root: tuple[str, Path]) -> None:
        platform, root = validity_plugin_root
        skills_dir = root / "skills"
        assert skills_dir.is_dir(), f"{platform}: skills/ directory missing"

        failures: list[str] = []
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue  # SKILL.md existence is asserted elsewhere (L1/L2)
            content = skill_md.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)

            if fm is None:
                failures.append(f"  {skill_dir.name}/SKILL.md: no valid YAML frontmatter found")
                continue
            name = fm.get("name", "")
            desc = fm.get("description", "")
            if not name:
                failures.append(f"  {skill_dir.name}/SKILL.md: 'name' key missing or empty")
            if not desc:
                failures.append(f"  {skill_dir.name}/SKILL.md: 'description' key missing or empty")

        assert not failures, (
            f"{platform}: SKILL.md frontmatter failures ({len(failures)}):\n"
            + "\n".join(failures)
        )

    def test_agent_md_frontmatter(self, validity_plugin_root: tuple[str, Path]) -> None:
        platform, root = validity_plugin_root
        agents_dir = root / "agents"
        assert agents_dir.is_dir(), f"{platform}: agents/ directory missing"

        failures: list[str] = []
        for agent_md in sorted(agents_dir.glob("*.md")):
            content = agent_md.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)

            if fm is None:
                failures.append(f"  {agent_md.name}: no valid YAML frontmatter found")
                continue
            name = fm.get("name", "")
            desc = fm.get("description", "")
            if not name:
                failures.append(f"  {agent_md.name}: 'name' key missing or empty")
            if not desc:
                failures.append(f"  {agent_md.name}: 'description' key missing or empty")

        assert not failures, (
            f"{platform}: agent .md frontmatter failures ({len(failures)}):\n"
            + "\n".join(failures)
        )


# ---------------------------------------------------------------------------
# Check 4: Hook scripts compile
# ---------------------------------------------------------------------------


class TestHookScriptsCompile:
    """Every *.py under hooks/ must pass py_compile.compile(doraise=True)."""

    def test_hook_scripts_compile(self, validity_plugin_root: tuple[str, Path]) -> None:
        platform, root = validity_plugin_root
        hooks_dir = root / "hooks"
        assert hooks_dir.is_dir(), f"{platform}: hooks/ directory missing"

        failures: list[str] = []
        with tempfile.TemporaryDirectory() as tmp_cache:
            for hook_py in sorted(hooks_dir.glob("*.py")):
                # Redirect the bytecode output to a throwaway directory so that
                # py_compile does not write __pycache__/*.pyc into the plugin's
                # hooks/ directory, which would pollute the hygiene check below.
                cfile = str(Path(tmp_cache) / (hook_py.stem + ".pyc"))
                try:
                    py_compile.compile(str(hook_py), cfile=cfile, doraise=True)
                except py_compile.PyCompileError as exc:
                    failures.append(f"  hooks/{hook_py.name}: {exc}")

        assert not failures, (
            f"{platform}: hook scripts that fail to compile ({len(failures)}):\n"
            + "\n".join(failures)
        )


# ---------------------------------------------------------------------------
# Check 5: Runtime slice standalone invariant — no harness.* imports
# ---------------------------------------------------------------------------


class TestRuntimeSliceNoHarnessImports:
    """
    The copied runtime slice under src/ must be self-contained.

    No file may import from the `harness` package (i.e. contain
    'import harness' or 'from harness').  The minting engine rewrites
    these to flat local imports so the plugin runs without the harness
    package installed in the user's environment.
    """

    def test_src_has_no_harness_imports(self, validity_plugin_root: tuple[str, Path]) -> None:
        platform, root = validity_plugin_root
        src_dir = root / "src"
        assert src_dir.is_dir(), f"{platform}: src/ directory missing"

        violations: list[str] = []
        for py_file in sorted(src_dir.glob("*.py")):
            content = py_file.read_text(encoding="utf-8")
            for lineno, line in enumerate(content.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("import harness") or stripped.startswith("from harness"):
                    violations.append(
                        f"  src/{py_file.name}:{lineno}: {stripped!r}"
                    )

        assert not violations, (
            f"{platform}: runtime slice contains harness.* imports — "
            f"standalone invariant violated ({len(violations)} violations):\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# Check 6: Hygiene — zero __pycache__ / *.pyc
# ---------------------------------------------------------------------------


class TestHygiene:
    """
    No __pycache__ directories and no *.pyc files may appear anywhere
    under the plugin root after a fresh mint.

    This catches the BUG-3 regression: a fresh mint shipped stale
    cpython-311 bytecode created during the _validate_claude_plugin()
    validation step.  The fix (cleanup sweep in cli.py) was applied as
    part of S1-T7.
    """

    def test_no_pycache_dirs(self, validity_plugin_root: tuple[str, Path]) -> None:
        platform, root = validity_plugin_root
        pycache_dirs = list(root.rglob("__pycache__"))

        assert not pycache_dirs, (
            f"{platform}: __pycache__ directories found under plugin root "
            f"({len(pycache_dirs)} found — bytecode must not be shipped):\n"
            + "\n".join(f"  {p.relative_to(root)}" for p in pycache_dirs)
        )

    def test_no_pyc_files(self, validity_plugin_root: tuple[str, Path]) -> None:
        platform, root = validity_plugin_root
        pyc_files = list(root.rglob("*.pyc"))

        assert not pyc_files, (
            f"{platform}: *.pyc files found under plugin root "
            f"({len(pyc_files)} found — bytecode must not be shipped):\n"
            + "\n".join(f"  {p.relative_to(root)}" for p in pyc_files)
        )


# ---------------------------------------------------------------------------
# Check 7: Tool-mapping translation (claude only)
# ---------------------------------------------------------------------------


class TestToolMappingTranslation:
    """
    Claude: minted skill/agent text must not contain un-translated source tokens.

    The Claude adapter's get_tool_mappings() returns a dict mapping
    source tokens (e.g. 'read_file', 'run_shell_command') to their
    platform-specific translations (e.g. 'Read', 'Bash').  After minting,
    the translated forms should appear — the source forms must not.

    Scope: only tokens where the mapping actually changes the value
    (source != destination).  List-bullet variants ('- read_file') and
    bare-word variants ('read_file') are checked independently as the
    adapter registers both forms.

    Gemini: the adapter's mappings are identity (no-op), so no translation
    assertion is made.
    """

    def test_claude_tool_tokens_translated(self, _claude_root_validity: Path) -> None:
        """claude: un-translated source tokens must not appear in skill/agent text."""
        from harness.adapters.claude import ClaudeAdapter

        adapter = ClaudeAdapter()
        mappings = adapter.get_tool_mappings()
        # Only tokens where translation actually changes the string
        transforming: dict[str, str] = {
            src: dst for src, dst in mappings.items() if src != dst
        }

        if not transforming:
            pytest.skip("Claude adapter has no transforming tool mappings — nothing to check")

        root = _claude_root_validity
        md_files: list[Path] = (
            list((root / "skills").rglob("SKILL.md"))
            + list((root / "agents").glob("*.md"))
        )

        violations: list[str] = []
        for md_file in sorted(md_files):
            content = md_file.read_text(encoding="utf-8")
            # Strip frontmatter from the check to avoid false positives on
            # 'tools:' lists that intentionally preserve original names.
            fm_parts = content.split("---", 2)
            body = fm_parts[2] if len(fm_parts) >= 3 else content

            for src_token, dst_token in transforming.items():
                if src_token in body:
                    violations.append(
                        f"  {md_file.relative_to(root)}: "
                        f"contains untranslated {src_token!r} "
                        f"(expected {dst_token!r})"
                    )

        assert not violations, (
            f"claude: un-translated tool tokens found in minted skill/agent text "
            f"({len(violations)} violations):\n"
            + "\n".join(violations)
        )

    def test_gemini_tool_mappings_are_identity(self, _gemini_root_validity: Path) -> None:
        """gemini: adapter tool mappings must be identity (no translation needed)."""
        from harness.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter()
        mappings = adapter.get_tool_mappings()
        transforming = {src: dst for src, dst in mappings.items() if src != dst}

        assert not transforming, (
            f"gemini: get_tool_mappings() returned non-identity entries "
            f"(expected all mappings to be no-ops, but these transform:\n"
            + "\n".join(f"  {s!r} → {d!r}" for s, d in transforming.items())
        )
