"""§15.1 executable vectors: each fixture must return exactly its pre-written statuses."""

from __future__ import annotations

import pytest
from synthetic_fixtures import EXPECTED, FIXTURES

from result_doctor.rules import RULE_IDS, evaluate
from result_doctor.status import RuleStatus


def _vector(bundle):
    return {(f.rule_id, f.target): f.status.value for f in evaluate(bundle)}


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_status_vector_is_exact(name: str) -> None:
    """No extra finding and no missing one: the vector must match key for key."""
    got = _vector(FIXTURES[name]())
    assert got == EXPECTED[name]


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_covers_every_rule(name: str) -> None:
    got = _vector(FIXTURES[name]())
    assert {r for r, _ in got} == set(RULE_IDS)


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_no_finding_lacks_evidence_or_reason(name: str) -> None:
    for f in evaluate(FIXTURES[name]()):
        assert f.question and f.rule_name
        assert f.reason, f
        assert isinstance(f.status, RuleStatus)


def test_s4_failure_is_not_masked_by_a_passing_recomputation() -> None:
    got = _vector(FIXTURES["S4"]())
    assert got[("RD001", "s4/A")] == "PASS"
    assert got[("RD003", "selection:sel:s4")] == "FAIL"


def test_s5_never_reports_the_surviving_count_as_the_universe_size() -> None:
    findings = {(f.rule_id, f.target): f for f in evaluate(FIXTURES["S5"]())}
    grid = findings[("RD004", "candidates:candidates:s5/grid")]
    assert "universe_size" not in grid.measurements
    assert grid.measurements["surviving_size"] == 3
    assert grid.measurements["declared_size"] == 24
    assert grid.measurements["universe_status"] == "PARTIAL"
    assert grid.status.value == "INCONCLUSIVE"


def test_s3_records_the_reproducing_family_even_when_it_refuses_to_judge() -> None:
    findings = {(f.rule_id, f.target): f for f in evaluate(FIXTURES["S3"]())}
    a = findings[("RD005", "s3/A")]
    assert a.status.value == "INCONCLUSIVE"
    assert a.measurements["families_matching_published_spread"] == ["k_sem_ddof0_k3"]
