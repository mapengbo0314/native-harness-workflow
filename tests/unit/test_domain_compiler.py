"""Unit tests for harness.domain.compiler — gather reference docs, distill the
fixed business fields via an injected LLM fn, merge into domain.json. No real
LLM is called."""
from __future__ import annotations

import json

from harness.domain import compiler as comp
from harness.domain.model import OpsManifest


def _seed_docs(ref_dir):
    (ref_dir / "sub").mkdir(parents=True)
    (ref_dir / "README.md").write_text("# scaffold readme — should be skipped\n")
    (ref_dir / "prd.md").write_text("# PRD\nSell invoicing to SMBs.\n")
    (ref_dir / "sub" / "goals.txt").write_text("Correctness over speed.\n")
    (ref_dir / "diagram.png").write_text("binary-ish")


def test_read_reference_docs_gathers_and_skips(tmp_path):
    ref = tmp_path / "ref"
    _seed_docs(ref)
    text = comp.read_reference_docs(ref)
    assert "Sell invoicing to SMBs." in text
    assert "Correctness over speed." in text
    assert "scaffold readme" not in text   # README skipped
    assert "diagram.png" not in text       # non-doc skipped


def test_read_reference_docs_empty_when_absent(tmp_path):
    assert comp.read_reference_docs(tmp_path / "nope") == ""


def test_compile_business_parses_and_filters():
    raw = ('prose...\n{"direction": "Win SMB invoicing", "priorities": ["integrity"], '
           '"constraints": [], "non_goals": "", "junk": "x"}')
    out = comp.compile_business("docs", query_llm_fn=lambda _p: raw)
    assert out == {"direction": "Win SMB invoicing", "priorities": ["integrity"]}


def test_compile_business_empty_docs_skips_llm():
    def boom(_p):
        raise AssertionError("LLM must not be called for empty docs")
    assert comp.compile_business("   ", query_llm_fn=boom) == {}


def test_compile_business_bad_json():
    assert comp.compile_business("docs", query_llm_fn=lambda _p: "not json") == {}


def test_run_domain_compile_merges_and_preserves(tmp_path):
    ref = tmp_path / "ref"
    _seed_docs(ref)
    mp = tmp_path / "domain.json"
    mp.write_text(json.dumps({"schema_version": 1, "stack": ["python"], "deploy": {"command": "./d"}}))
    fake = lambda _p: '{"direction": "Win SMB invoicing", "priorities": ["integrity"]}'
    comp.run_domain_compile(tmp_path, manifest_path=mp, reference_dir=ref,
                            query_llm_fn=fake, output_fn=lambda *_: None)
    m = OpsManifest.load(mp)
    assert m.business == {"direction": "Win SMB invoicing", "priorities": ["integrity"]}
    assert m.stack == ("python",)            # preserved
    assert m.deploy == {"command": "./d"}    # preserved


def test_run_domain_compile_no_docs_is_noop(tmp_path):
    mp = tmp_path / "domain.json"
    mp.write_text(json.dumps({"schema_version": 1, "stack": ["go"]}))
    msgs = []
    def boom(_p):
        raise AssertionError("LLM must not be called without docs")
    comp.run_domain_compile(tmp_path, manifest_path=mp, reference_dir=tmp_path / "ref",
                            query_llm_fn=boom, output_fn=msgs.append)
    assert OpsManifest.load(mp).business == {}
    assert any("reference" in m.lower() for m in msgs)


def test_run_domain_compile_creates_manifest_if_absent(tmp_path):
    ref = tmp_path / "ref"
    _seed_docs(ref)
    mp = tmp_path / "domain" / "domain.json"
    comp.run_domain_compile(tmp_path, manifest_path=mp, reference_dir=ref,
                            query_llm_fn=lambda _p: '{"direction": "X"}', output_fn=lambda *_: None)
    assert OpsManifest.load(mp).business == {"direction": "X"}
