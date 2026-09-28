"""§14 frozen GMMVI acceptance: chains A, B and C against the frozen archive."""

from __future__ import annotations

import os

import pytest

from result_doctor.compute import center, dispersion, render
from result_doctor.loaders import load_gmmvi_bundle
from result_doctor.rules import evaluate
from result_doctor.schema import SpreadForm, SpreadKind

ARCHIVE = os.environ.get("RD_GMMVI_ARCHIVE", r"F:\MLResearch\experiment-doctor\phase0-gmmvi")


@pytest.fixture(scope="module")
def vectors():
    if not os.path.isdir(ARCHIVE):
        pytest.skip(f"frozen GMMVI archive not present at {ARCHIVE}")
    bundle = load_gmmvi_bundle(ARCHIVE)
    return bundle, {(f.rule_id, f.target): f for f in evaluate(bundle)}


def _v(vectors, rule, target):
    return vectors[1][(rule, target)]


# ------------------------------------------------------------------ chain A: closed
def test_chain_a_reproduces_the_paper_cell_digit_for_digit(vectors) -> None:
    f = _v(vectors, "RD001", "TALOS/sepyfux/entropy/Table 8")
    m = f.measurements
    assert f.status.value == "PASS"
    assert m["n_members"] == 4
    assert (m["reported_center"], m["reported_dispersion"]) == ("-25.03", "5.46")
    assert (m["rendered_center"], m["rendered_dispersion"]) == ("-25.03", "5.46")


def test_chain_a_whole_talos_row_reproduces(vectors) -> None:
    """Phase 0 §5.1: 9 methods x 2 metrics on Table 8, all matching."""
    bundle, table = vectors
    talos = [r for r in bundle.reported_results if r.startswith("TALOS/") and r.endswith("/Table 8")]
    assert len(talos) == 18
    assert all(table[("RD001", r)].status.value == "PASS" for r in talos)


def test_chain_a_wrong_spread_semantics_do_not_masquerade_as_correct(vectors) -> None:
    """The locked counterexamples: only the 3*SE family with ddof=0 reproduces +/-5.46."""
    f = _v(vectors, "RD005", "TALOS/sepyfux/entropy/Table 8")
    fams = f.measurements["formula_family_renderings"]
    assert f.measurements["families_matching_published_spread"] == ["k_sem_ddof0_k3"]
    assert fams["k_sem_ddof1_k3"] == "6.31"
    assert fams["std_ddof0"] == "3.64"
    assert fams["sem_ddof0"] == "1.82"
    assert f.status.value == "PASS"


def test_chain_a_wrong_membership_does_not_masquerade_as_correct(vectors) -> None:
    """The second locked counterexample: the 6 `.bad` seeds as members print -45.32 +/-42.91.

    Phase 0 §5.1 froze that pair, and the bundle must be able to produce it on demand
    without ever preferring it over the declared 4-seed membership.
    """
    bundle, _ = vectors
    agg = bundle.aggregations["agg:TALOS/sepyfux/entropy"]
    assert len(bundle.included(agg)) == 4 and len(bundle.members_of(agg)) == 10
    values = [float(m.observed_value.value) for m in bundle.members_of(agg)]
    form = SpreadForm(SpreadKind.K_SEM, k=3.0, ddof=0, n=len(values))
    assert render(center(values, agg.center), "fixed") == "-45.32"
    assert render(dispersion(values, form), "fixed") == "42.91"
    published = _v(vectors, "RD001", "TALOS/sepyfux/entropy/Table 8").measurements
    assert [published["rendered_center"], published["rendered_dispersion"]] == ["-25.03", "5.46"]


def test_chain_a_exclusions_are_recorded_but_their_criterion_is_not_recomputable(vectors) -> None:
    f = _v(vectors, "RD002", "aggregation:agg:TALOS/sepyfux/entropy")
    m = f.measurements
    assert (m["n_members"], m["n_included"], m["n_exclusions"]) == (10, 4, 6)
    assert m["n_exclusions_unbound_to_members"] == 0
    assert m["exclusion_criterion_recomputable"] is False
    assert f.status.value == "INCONCLUSIVE"


def test_chain_a_including_the_discarded_runs_would_change_the_cell(vectors) -> None:
    """The 6 .bad members are in the bundle; RD001 uses only the included ones."""
    bundle, table = vectors
    agg = bundle.aggregations["agg:TALOS/sepyfux/entropy"]
    assert len(bundle.included(agg)) == 4
    assert len(agg.member_ids) == 10
    assert table[("RD001", "TALOS/sepyfux/entropy/Table 8")].measurements["member_values"] == [
        -29.456942,
        -21.497114,
        -27.786345,
        -21.37039,
    ]


def test_chain_a_member_identity_stays_unknown(vectors) -> None:
    bundle = vectors[0]
    agg = bundle.aggregations["agg:TALOS/sepyfux/entropy"]
    members = bundle.included(agg)
    assert len(members) == 4
    assert all(not m.run_ref.external_id.is_known for m in members)


# ------------------------------------------------------------------ chain B: broken
def test_chain_b_reports_a_localized_break_not_a_paper_error(vectors) -> None:
    f = _v(vectors, "RD001", "BreastCancer/samtron/-elbo/Table 8")
    m = f.measurements
    assert f.status.value == "INCONCLUSIVE"
    assert (m["rendered_center"], m["rendered_dispersion"]) == ("78.01", "0.01")
    assert (m["reported_center"], m["reported_dispersion"]) == ("78.00", "0.02")
    assert "identity" in f.reason


def test_chain_b_names_the_surviving_artifact_as_the_wrong_one(vectors) -> None:
    f = _v(vectors, "RD008", "artifact:extracted/evaluations/results/BC_EVAL/samtron_bc")
    assert f.status.value == "FAIL"
    assert f.measurements["missing"] == ["MMD:"]
    assert f.measurements["producer_grade"] == "UNKNOWN"
    assert "not the artifact that produced the cell" in f.reason


def test_chain_b_spread_family_is_the_only_bc_claim_that_survives(vectors) -> None:
    """Three of six families print 0.02 under `%.2f`; only the center fails to reproduce.

    Phase 0 §5.2 said "ddof=0 gives 78.01 +/- 0.01": 0.015126 rounds to 0.02, not 0.01,
    so the published +/- is reproduced and the break is entirely in the center.
    """
    f = _v(vectors, "RD005", "BreastCancer/samtron/-elbo/Table 8")
    fams = f.measurements["formula_family_renderings"]
    assert fams["std_ddof0"] == "0.02" and fams["std_ddof1"] == "0.02"
    assert fams["k_sem_ddof0_k3"] == "0.01"
    assert f.measurements["families_matching_published_spread"] == ["k_sem_ddof1_k3", "std_ddof0", "std_ddof1"]


def test_chain_c_three_way_split_of_the_98_search_groups(vectors) -> None:
    bundle, table = vectors
    events = [t for (r, t) in table if r == "RD003" and t.startswith("selection:sel:hyperopt/")]
    assert len(events) == len(bundle.selection_events) == 98
    exact = [t for t in events if table[("RD003", t)].measurements.get("gap") == 0.0]
    failed = [t for t in events if table[("RD003", t)].status.value == "FAIL"]
    near = [
        t
        for t in events
        if table[("RD003", t)].measurements.get("gap_within_declared_precision")
        and table[("RD003", t)].measurements.get("gap", 0) > 0
    ]
    unbound = [t for t in events if "promoted_ref_unrecorded" in table[("RD003", t)].measurements]
    assert (len(exact), len(failed), len(near), len(unbound)) == (91, 4, 1, 2)
    assert len(exact) + len(failed) + len(near) == 98 - len(unbound)


def test_chain_c_a_deviation_beyond_the_declared_precision_fails(vectors) -> None:
    f = _v(vectors, "RD003", "selection:sel:hyperopt/GMM100/sepyrux_gmm100")
    m = f.measurements
    assert f.status.value == "FAIL"
    assert (m["champion_value"], m["promoted_value"]) == (0.675964, 1.138794)
    assert m["gap_within_declared_precision"] is False
    assert "not the champion" in f.reason


def test_chain_c_a_fourth_decimal_near_tie_is_not_a_deviation(vectors) -> None:
    f = _v(vectors, "RD003", "selection:sel:hyperopt/GC/samtrux_gc")
    assert f.measurements["gap"] == 0.000916
    assert f.measurements["n_deviations"] == 0
    assert f.measurements["gap_within_declared_precision"] is True


def test_chain_c_unbound_promotion_stays_inconclusive(vectors) -> None:
    for target in ("selection:sel:hyperopt/TALOS/zamtrux_talos", "selection:sel:hyperopt/WINE/zamtrux_WINE"):
        f = _v(vectors, "RD003", target)
        assert f.status.value == "INCONCLUSIVE"
        assert f.measurements["promoted_ref_unrecorded"] is True
        assert "cannot be bound" in f.reason


def test_chain_c_promotion_is_never_written_to_disk(vectors) -> None:
    bundle = vectors[0]
    events = [se for se in bundle.selection_events.values() if se.kind.value == "hyperparameter"]
    assert len(events) == 98
    assert all(se.is_recorded.value is False for se in events)
    sets = [cs for cid, cs in bundle.candidate_sets.items() if cid.startswith("candidates:hyperopt/")]
    assert len(sets) == 98
    assert all(cs.promotion_evidence.value is False for cs in sets)


# ------------------------------------------------------------------ grids and FM9
def test_grid_generations_are_censused_and_neither_merged_nor_separated(vectors) -> None:
    bundle, table = vectors
    adopted = bundle.candidate_sets["candidates:exp3-adopted-grid"]
    discarded = bundle.candidate_sets["candidates:exp3-discarded-grid"]
    assert (adopted.declared_size.value, discarded.declared_size.value) == (1074, 1152)
    assert adopted.universe_status.value == "RECOVERED"
    assert discarded.universe_status.value == "PARTIAL"
    collision = adopted.identity_collision
    assert collision.key_type == "wandb.group"
    assert collision.collision_count == 35
    for cid in ("candidates:exp3-adopted-grid", "candidates:exp3-discarded-grid"):
        f = table[("RD004", f"candidates:{cid}")]
        assert f.status.value == "INCONCLUSIVE"
        assert "no judgment is made here" in f.reason
        assert "混淆" not in f.reason and "confus" not in f.reason.lower()
        assert "unrelated" not in f.reason.lower()


def test_hyperopt_universe_is_partial_and_never_read_as_complete(vectors) -> None:
    bundle, table = vectors
    cs = bundle.candidate_sets["candidates:hyperopt/BC/samtron_bc"]
    assert cs.universe_status.value == "PARTIAL"
    f = table[("RD004", "candidates:candidates:hyperopt/BC/samtron_bc")]
    assert f.status.value == "INCONCLUSIVE"
    assert "never inferred from the count of surviving artifacts" in f.reason


# ------------------------------------------------------------------ FM12/FM13/FM14
def test_presentation_marks_are_recorded_as_unrecovered_not_absent(vectors) -> None:
    bundle, table = vectors
    cs = bundle.comparison_sets["cmp:TALOS"]
    assert cs.observed_marks.grade.value == "UNKNOWN"
    assert cs.presentation_rule is not None and cs.presentation_rule.symmetric is False
    f = table[("RD007", "comparison:cmp:TALOS")]
    assert f.status.value == "INCONCLUSIVE"
    assert f.measurements["marks_recovered_from"] == "UNKNOWN"
    assert "the marks actually shown in the product are not" in f.reason


def test_fm13_conflicting_pair_is_reported_without_a_cause(vectors) -> None:
    f = _v(vectors, "RD008", "quantity:STM300/sepyfux/-elbo")
    assert f.status.value == "FAIL"
    assert set(f.measurements["values"]) == {"26.69", "26.87"}
    assert set(f.measurements["spreads"]) == {"0.39", "0.45"}
    assert "is not determined here" in f.reason
    assert "typo" not in f.reason.lower()


def test_fm13_agreeing_pairs_pass(vectors) -> None:
    _, table = vectors
    for key in ("TALOS/sepyfux/-elbo", "TALOS/samtron/-elbo", "PlanarRobot/samtron/-elbo"):
        assert table[("RD008", f"quantity:{key}")].status.value == "PASS"


def test_external_baseline_cell_is_out_of_recomputation_scope(vectors) -> None:
    _, table = vectors
    for rule in ("RD001", "RD006"):
        assert (
            table[
                (rule, "VIPS/vipsum/-elbo/Table 8" if rule == "RD001" else "reported:VIPS/vipsum/-elbo/Table 8")
            ].status.value
            == "NOT_APPLICABLE"
        )
    f = table[("RD008", "artifact:repo/evaluations/iBayesLR_results")]
    assert f.status.value == "FAIL"
    assert f.measurements["missing"] == ["track_elbos", "track_n_fevals"]


def test_na_cells_are_not_applied_over(vectors) -> None:
    _, table = vectors
    for target in ("STM300/zamtrux/-elbo/Table 8", "STM300/zamtrux/num_detected_modes/Table 8"):
        assert table[("RD001", target)].status.value == "NOT_APPLICABLE"
        assert table[("RD005", target)].status.value == "NOT_APPLICABLE"


def test_deterministic_and_reproducible(vectors) -> None:
    from result_doctor.status import canonical_json

    bundle, _ = vectors
    a = canonical_json(evaluate(bundle))
    b = canonical_json(evaluate(load_gmmvi_bundle(ARCHIVE)))
    assert a == b and len(a) > 10000
