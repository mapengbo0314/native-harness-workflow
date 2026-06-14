"""Contract test: dispatch_agent's result schema must match the keys the
prompt_classifier hook reads (review 2026-06-12, C2).

The hook reads result['intent_branch'], result['intent_justification'] and
result['routing_decision'].{phase,target_agent,missing_documents,auth_msg}.
Silent key drift here blanks the SYSTEM STATE block, so we pin it.
"""
from __future__ import annotations

from unittest.mock import patch

from harness.runtime.dispatcher import OrchestratorDispatcher


def _dispatcher(tmp_path) -> OrchestratorDispatcher:
    config_dir = tmp_path / "harness-wf-plugin" / "config"
    config_dir.mkdir(parents=True)
    return OrchestratorDispatcher(str(config_dir))


def test_dispatch_agent_propagates_intent_justification(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    with patch.object(
        dispatcher,
        "classify_intent",
        return_value={"branch": "C", "justification": "read-only request"},
    ):
        result = dispatcher.dispatch_agent(
            "orchestrator",
            {"prompt": "what does this file do", "project_root": str(tmp_path)},
        )

    assert result["intent_branch"] == "C"
    # C2: justification must survive into the dispatch result, not be dropped.
    assert result["intent_justification"] == "read-only request"


def test_dispatch_agent_routing_decision_exposes_classifier_keys(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    with patch.object(
        dispatcher,
        "classify_intent",
        return_value={"branch": "C", "justification": "x"},
    ):
        result = dispatcher.dispatch_agent(
            "orchestrator",
            {"prompt": "explain", "project_root": str(tmp_path)},
        )

    routing_decision = result["routing_decision"]
    for key in ("phase", "target_agent", "auth_msg", "missing_documents"):
        assert key in routing_decision, f"routing_decision missing {key!r}"
    # The hook must never have to read the old 'artifacts_missing' name.
    assert "artifacts_missing" not in routing_decision
