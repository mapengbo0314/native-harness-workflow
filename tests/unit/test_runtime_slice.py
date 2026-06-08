"""Unit tests for harness.init.runtime_slice (D4/D5).

Covers:
1. RUNTIME_FILE_MAP is the single source of truth — no duplication with
   classification.RUNTIME_SOURCE_MAP.
2. rewrite_imports correctly strips harness sub-package prefixes for all three
   namespaces (runtime / init / adapters), both ``from`` and ``import`` forms.
3. emit_platform_adapter returns the correct template for each known platform;
   resolves unknown platforms to "generic"; contains no ``harness.*`` imports.
4. reproduce_runtime_file returns the right content for every file kind:
   - mapped Python sources: import-rewritten content of the real source file.
   - platform_adapter.py (emitted): output of emit_platform_adapter.
   - __init__.py (emitted): empty string.
   - platform_profiles.json (verbatim): matches the file in the package.
5. reproduce_runtime_file raises KeyError for unknown names.
6. Dedupe assertion: classification.RUNTIME_SOURCE_MAP equals the prefixed
   form of RUNTIME_FILE_MAP (so a single edit cannot drift).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.init.runtime_slice import (
    RUNTIME_FILE_MAP,
    emit_platform_adapter,
    reproduce_runtime_file,
    rewrite_imports,
)

# Package root: src/harness/
PACKAGE_ROOT = Path(__file__).parent.parent.parent / "src" / "harness"

PLATFORMS = ["claude", "gemini", "codex", "cursor", "generic"]


# ---------------------------------------------------------------------------
# 1. Dedupe: classification.RUNTIME_SOURCE_MAP is derived from RUNTIME_FILE_MAP
# ---------------------------------------------------------------------------

class TestDedupeRuntimeSourceMap:
    def test_classification_map_equals_derived_form(self):
        """RUNTIME_SOURCE_MAP must equal {f"src/{k}": v for k, v in RUNTIME_FILE_MAP.items()}.

        If this fails, someone edited one map without the other — the single
        source of truth (D5) has been broken.
        """
        from harness.update.classification import RUNTIME_SOURCE_MAP

        expected = {f"src/{name}": source_rel for name, source_rel in RUNTIME_FILE_MAP.items()}
        assert RUNTIME_SOURCE_MAP == expected, (
            "classification.RUNTIME_SOURCE_MAP diverged from RUNTIME_FILE_MAP. "
            "Edit only RUNTIME_FILE_MAP in runtime_slice.py."
        )

    def test_runtime_file_map_contains_all_expected_keys(self):
        """Verify the map contains the full set of files known to classification."""
        expected_names = {
            "dispatcher.py",
            "llm_client.py",
            "context_builder.py",
            "langfuse_compat.py",
            "langfuse_instrumentation.py",
            "discovery_engine.py",
            "runtime_adapter.py",
            "profile.py",
            "platform_profiles.json",
            "platform_adapter.py",
            "__init__.py",
            # domain runtime slice — MCP server needs model + server
            "model.py",
            "server.py",
        }
        assert set(RUNTIME_FILE_MAP.keys()) == expected_names

    def test_emitted_files_have_none_source(self):
        """platform_adapter.py and __init__.py must map to None (emitted)."""
        assert RUNTIME_FILE_MAP["platform_adapter.py"] is None
        assert RUNTIME_FILE_MAP["__init__.py"] is None

    def test_all_non_emitted_sources_exist_on_disk(self):
        """Every non-None source_rel must point to a real file in the package."""
        for name, source_rel in RUNTIME_FILE_MAP.items():
            if source_rel is not None:
                src = PACKAGE_ROOT / source_rel
                assert src.exists(), (
                    f"RUNTIME_FILE_MAP[{name!r}] = {source_rel!r} "
                    f"but {src} does not exist"
                )


# ---------------------------------------------------------------------------
# 2. rewrite_imports
# ---------------------------------------------------------------------------

class TestRewriteImports:
    def test_from_harness_runtime(self):
        text = "from harness.runtime.dispatcher import Dispatcher"
        assert rewrite_imports(text) == "from dispatcher import Dispatcher"

    def test_from_harness_init(self):
        text = "from harness.init.discovery_engine import detect_tech_stack"
        assert rewrite_imports(text) == "from discovery_engine import detect_tech_stack"

    def test_from_harness_adapters(self):
        # "harness.adapters." is stripped wholesale; leaves just the module name
        text = "from harness.adapters.runtime_adapter import get_adapter"
        assert rewrite_imports(text) == "from runtime_adapter import get_adapter"

    def test_import_harness_runtime(self):
        text = "import harness.runtime.dispatcher as d"
        assert rewrite_imports(text) == "import dispatcher as d"

    def test_import_harness_init(self):
        text = "import harness.init.discovery_engine"
        assert rewrite_imports(text) == "import discovery_engine"

    def test_import_harness_adapters(self):
        # "harness.adapters." is stripped wholesale; leaves just the module name
        text = "import harness.adapters.profile as p"
        assert rewrite_imports(text) == "import profile as p"

    def test_from_harness_domain(self):
        text = "from harness.domain.model import OpsManifest"
        assert rewrite_imports(text) == "from model import OpsManifest"

    def test_non_harness_imports_unchanged(self):
        text = "from pathlib import Path\nimport json\nimport os"
        assert rewrite_imports(text) == text

    def test_multiple_lines_rewrites_all(self):
        text = (
            "from harness.runtime.dispatcher import Dispatcher\n"
            "from harness.adapters.runtime_adapter import get_adapter\n"
            "import json\n"
        )
        result = rewrite_imports(text)
        assert "harness." not in result
        assert "from dispatcher import Dispatcher" in result
        assert "from runtime_adapter import get_adapter" in result
        assert "import json" in result

    def test_idempotent_on_already_flat_text(self):
        text = "from dispatcher import Dispatcher\nimport json\n"
        assert rewrite_imports(text) == text

    def test_preserves_non_import_harness_references(self):
        """References to 'harness' that are not import statements must be kept."""
        text = '# This uses harness.runtime internals\nVAR = "harness.runtime.dispatcher"\n'
        assert rewrite_imports(text) == text


# ---------------------------------------------------------------------------
# 3. emit_platform_adapter
# ---------------------------------------------------------------------------

class TestEmitPlatformAdapter:
    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_known_platform_baked_in(self, platform):
        content = emit_platform_adapter(platform)
        assert f'return _get_adapter("{platform}")' in content

    def test_unknown_platform_falls_back_to_generic(self):
        content = emit_platform_adapter("unknown_xyz")
        assert 'return _get_adapter("generic")' in content
        assert "unknown_xyz" not in content

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_no_harness_imports_in_emitted_file(self, platform):
        content = emit_platform_adapter(platform)
        for line in content.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "harness." not in stripped, (
                    f"harness.* import in emitted platform_adapter.py for {platform!r}: {line!r}"
                )

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_imports_from_runtime_adapter(self, platform):
        content = emit_platform_adapter(platform)
        assert "from runtime_adapter import get_adapter as _get_adapter" in content

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_defines_no_arg_get_adapter(self, platform):
        content = emit_platform_adapter(platform)
        assert "def get_adapter():" in content

    def test_different_platforms_produce_different_content(self):
        contents = {p: emit_platform_adapter(p) for p in PLATFORMS}
        # Each platform must produce unique content (different baked-in id)
        unique = set(contents.values())
        assert len(unique) == len(PLATFORMS), (
            "Two platforms produced identical platform_adapter.py content"
        )


# ---------------------------------------------------------------------------
# 4. reproduce_runtime_file — per-kind assertions
# ---------------------------------------------------------------------------

class TestReproduceRuntimeFilePython:
    """Mapped Python sources must have harness.* imports rewritten."""

    @pytest.mark.parametrize("name,source_rel", [
        (name, source_rel)
        for name, source_rel in RUNTIME_FILE_MAP.items()
        if source_rel is not None and name.endswith(".py")
    ])
    def test_no_harness_imports_after_rewrite(self, name, source_rel):
        text = reproduce_runtime_file(name, platform="claude", package_root=PACKAGE_ROOT)
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "harness.runtime." not in stripped, (
                    f"{name}: unrewritten harness.runtime import: {line!r}"
                )
                assert "harness.init." not in stripped, (
                    f"{name}: unrewritten harness.init import: {line!r}"
                )
                assert "harness.adapters." not in stripped, (
                    f"{name}: unrewritten harness.adapters import: {line!r}"
                )

    @pytest.mark.parametrize("name,source_rel", [
        (name, source_rel)
        for name, source_rel in RUNTIME_FILE_MAP.items()
        if source_rel is not None and name.endswith(".py")
    ])
    def test_rewritten_content_matches_manual_rewrite(self, name, source_rel):
        """reproduce_runtime_file must equal read-then-rewrite of the source file."""
        raw = (PACKAGE_ROOT / source_rel).read_text(encoding="utf-8")
        expected = rewrite_imports(raw)
        actual = reproduce_runtime_file(name, platform="claude", package_root=PACKAGE_ROOT)
        assert actual == expected


class TestReproduceRuntimeFilePlatformAdapter:
    """platform_adapter.py is emitted — must match emit_platform_adapter output."""

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_matches_emit_platform_adapter(self, platform):
        reproduced = reproduce_runtime_file(
            "platform_adapter.py", platform=platform, package_root=PACKAGE_ROOT
        )
        expected = emit_platform_adapter(platform)
        assert reproduced == expected

    @pytest.mark.parametrize("platform", PLATFORMS)
    def test_no_harness_imports(self, platform):
        content = reproduce_runtime_file(
            "platform_adapter.py", platform=platform, package_root=PACKAGE_ROOT
        )
        for line in content.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "harness." not in stripped


class TestReproduceRuntimeFileInit:
    """__init__.py is emitted empty."""

    def test_init_py_is_empty(self):
        result = reproduce_runtime_file(
            "__init__.py", platform="claude", package_root=PACKAGE_ROOT
        )
        assert result == ""


class TestReproduceRuntimeFileJson:
    """platform_profiles.json is reproduced verbatim."""

    def test_matches_package_file(self):
        reproduced = reproduce_runtime_file(
            "platform_profiles.json", platform="claude", package_root=PACKAGE_ROOT
        )
        expected = (PACKAGE_ROOT / "adapters" / "platform_profiles.json").read_text(
            encoding="utf-8"
        )
        assert reproduced == expected

    def test_is_valid_json(self):
        import json
        content = reproduce_runtime_file(
            "platform_profiles.json", platform="claude", package_root=PACKAGE_ROOT
        )
        data = json.loads(content)
        assert isinstance(data, dict)
        assert len(data) > 0


class TestReproduceRuntimeFileErrors:
    """Unknown names must raise KeyError."""

    def test_unknown_name_raises_key_error(self):
        with pytest.raises(KeyError, match="unknown_module.py"):
            reproduce_runtime_file(
                "unknown_module.py", platform="claude", package_root=PACKAGE_ROOT
            )

    def test_src_prefixed_name_raises_key_error(self):
        """Keys don't include the 'src/' prefix — that's classification's job."""
        with pytest.raises(KeyError):
            reproduce_runtime_file(
                "src/dispatcher.py", platform="claude", package_root=PACKAGE_ROOT
            )
