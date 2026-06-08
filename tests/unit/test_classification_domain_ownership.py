"""Regression: the update machinery must never clobber the user-owned domain
manifest. domain.json (and any reference docs) live inside the plugin but are
authored/compiled content — classify() must return None for them so
`harness-wf update` leaves them alone. The deployed runtime modules
(src/model.py, src/server.py), by contrast, ARE harness-managed."""
from __future__ import annotations

from harness.update.classification import classify


def test_domain_manifest_is_not_harness_owned():
    assert classify("domain/domain.json") is None


def test_domain_reference_docs_are_not_harness_owned():
    assert classify("domain/reference/prd.md") is None


def test_deployed_domain_runtime_modules_are_managed():
    # model.py + server.py are deployed runtime slice → harness-managed (not None).
    assert classify("src/model.py") is not None
    assert classify("src/server.py") is not None
