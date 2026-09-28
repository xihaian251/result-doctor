"""§15 frozen TorchSSL acceptance: checkpoint selection, split facts, and the ± wording."""

from __future__ import annotations

import os

import pytest

from result_doctor.loaders import load_torchssl_bundle
from result_doctor.rules import evaluate

ARCHIVE = os.environ.get("RD_TORCHSSL_ARCHIVE", r"F:\MLResearch\experiment-doctor\acceptance1-torchssl")

CELLS = ("fixmatch_cifar10_250/BestAcc", "flexmatch_cifar10_250/BestAcc")
TRIPLETS = {
    "fixmatch_cifar10_250/BestAcc": [95.16, 95.07, 95.18],
    "flexmatch_cifar10_250/BestAcc": [95.12, 94.91, 95.02],
}


@pytest.fixture(scope="module")
def vectors():
    if not os.path.isdir(ARCHIVE):
        pytest.skip(f"frozen TorchSSL archive not present at {ARCHIVE}")
    bundle = load_torchssl_bundle(ARCHIVE)
    return bundle, {(f.rule_id, f.target): f for f in evaluate(bundle)}


def test_reported_cells_reproduce_exactly(vectors) -> None:
    _, table = vectors
    for cell in CELLS:
        m = table[("RD001", cell)].measurements
        assert table[("RD001", cell)].status.value == "PASS"
        assert m["n_members"] == 3
        assert [round(v, 4) for v in m["member_values"]] == TRIPLETS[cell]
    got = {table[("RD001", c)].measurements["rendered_center"] for c in CELLS}
    assert got == {"95.14", "95.02"}


def test_only_ddof_0_reproduces_the_published_intervals(vectors) -> None:
    _, table = vectors
    for cell, spread in zip(CELLS, ("0.05", "0.09")):
        fams = table[("RD005", cell)].measurements["formula_family_renderings"]
        assert fams["std_ddof0"] == spread
        assert fams["std_ddof1"] != spread
        assert fams["sem_ddof0"] != spread
        assert table[("RD005", cell)].measurements["families_matching_published_spread"] == ["std_ddof0"]


def test_the_standard_error_wording_conflicts_with_the_reproducing_family(vectors) -> None:
    """FM6: README.md:58 says "standard errors"; only a plain std reproduces the cells."""
    _, table = vectors
    for cell in CELLS:
        f = table[("RD005", cell)]
        assert f.status.value == "FAIL"
        assert "standard error" in str(f.measurements["spread_label"])
        assert "plain standard deviation" in f.reason


def test_checkpoint_selection_is_recovered_field_by_field(vectors) -> None:
    bundle, table = vectors
    events = [se for se in bundle.selection_events.values()]
    assert len(events) == 6
    assert {se.kind.value for se in events} == {"checkpoint"}
    for se in events:
        f = table[("RD003", f"selection:{se.selection_id}")]
        assert f.status.value == "PASS"
        assert set(f.measurements["criterion_grades"].values()) == {"DIRECT"}
        assert f.measurements["n_candidates"] == len(se.candidate_values) == 378
    crit = events[0].criterion
    assert crit.split.value == "test"
    assert crit.metric.value == "eval/top-1-acc"
    assert crit.direction.value == "maximize"


def test_the_test_split_fact_carries_no_leakage_inference(vectors) -> None:
    """The split is a recorded fact; the rule text must not turn it into a verdict."""
    bundle, table = vectors
    se = next(s for s in bundle.selection_events.values())
    assert se.criterion.split.grade.value == "DIRECT"
    for f in table.values():
        text = (f.reason + str(f.measurements)).lower()
        assert "leak" not in text and "violat" not in text and "invalid" not in text


def test_the_ema_copy_and_bn_buffers_are_part_of_the_selected_weights_fact(vectors) -> None:
    se = next(s for s in vectors[0].selection_events.values())
    assert "ema" in se.criterion.metric.note.lower()
    assert "bn running buffers" in se.effect_on_report.lower()


def test_membership_gate_is_recorded_in_the_member_rule(vectors) -> None:
    bundle = vectors[0]
    for agg in bundle.aggregations.values():
        assert "1048000 iteration" in agg.member_rule.expression
        assert agg.member_rule.grade.value == "DIRECT"


def test_checkpoint_universe_is_recovered_while_the_search_universe_is_unrecoverable(vectors) -> None:
    bundle, table = vectors
    recovered = [cid for cid, cs in bundle.candidate_sets.items() if cs.kind.value == "checkpoint"]
    assert len(recovered) == 6
    assert all(bundle.candidate_sets[c].universe_status.value == "RECOVERED" for c in recovered)
    open_set = bundle.candidate_sets["candidates:hyperparameter/torchssl"]
    assert open_set.universe_status.value == "UNRECOVERABLE"
    assert len(open_set.unobservable_sources) == 4
    f = table[("RD004", "candidates:candidates:hyperparameter/torchssl")]
    assert f.status.value == "INCONCLUSIVE"
    assert f.status.value != "NOT_APPLICABLE"
    assert "affirmatively unrecoverable" in f.reason


def test_no_search_product_never_becomes_a_singleton_candidate_set(vectors) -> None:
    cs = vectors[0].candidate_sets["candidates:hyperparameter/torchssl"]
    assert cs.surviving_size.value >= 2
    assert cs.declared_size.value == 3
    assert cs.promotion_evidence.grade.value == "UNKNOWN"


def test_generated_column_is_flagged_without_blaming_the_published_cells(vectors) -> None:
    """FM11: average_log.py writes rolling Top-1 means into the Top5_20/50 columns."""
    _, table = vectors
    victim = "generated/fixmatch_cifar10_250/Top5_20"
    f = table[("RD006", f"reported:{victim}")]
    assert f.status.value == "FAIL"
    assert f.measurements["declared_vs_observed_conflicts"] == ["t:top5_column_fill"]
    for rule in ("RD001", "RD005"):
        assert table[(rule, victim)].status.value == "NOT_APPLICABLE"
    for cell in CELLS:
        assert table[("RD006", f"reported:{cell}")].status.value == "PASS"


def test_cells_printed_in_one_product_cannot_be_cross_checked(vectors) -> None:
    _, table = vectors
    for cell in CELLS:
        f = table[("RD008", f"quantity:{cell}")]
        assert f.status.value == "INCONCLUSIVE"
        assert f.measurements["n_loci"] == 1


def test_no_presentation_marks_means_not_applicable(vectors) -> None:
    bundle, table = vectors
    for cid, cs in bundle.comparison_sets.items():
        assert cs.presentation_rule is None
        assert table[("RD007", f"comparison:{cid}")].status.value == "NOT_APPLICABLE"


def test_deterministic_and_reproducible(vectors) -> None:
    from result_doctor.status import canonical_json

    bundle, _ = vectors
    assert canonical_json(evaluate(bundle)) == canonical_json(evaluate(load_torchssl_bundle(ARCHIVE)))
