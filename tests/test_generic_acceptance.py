"""G0-G5 of Phase 2 §23: the generic manifest path, judged by its status vector.

Each case compares the *whole* vector, so a rule that silently gains or loses a target
fails the gate. The inverse invariant rows are asserted too, because that is the half of
the oracle that says what the tool must *not* conclude.
"""

from __future__ import annotations

import json
import os

import pytest

from result_doctor.audit import audit_bundle, audit_manifest
from result_doctor.loaders import load_gmmvi_bundle, load_torchssl_bundle
from result_doctor.manifest import bundle_from_manifest
from result_doctor.rules import evaluate
from result_doctor.status import RuleStatus, canonical_json

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generic_fixtures")
GMMVI_ARCHIVE = os.environ.get("RD_GMMVI_ARCHIVE", r"F:\MLResearch\experiment-doctor\phase0-gmmvi")
TORCHSSL_ARCHIVE = os.environ.get("RD_TORCHSSL_ARCHIVE", r"F:\MLResearch\experiment-doctor\acceptance1-torchssl")

CELL = "acc/cifar-resnet20"

EXPECTED: dict[str, dict[str, dict[tuple[str, str], str]]] = {
    # G1: Example A. Everything provable is proved; the two absent object classes say NOT_RUN.
    "g1": {
        "vector": {
            ("RD001", CELL): "PASS",
            ("RD002", f"aggregation:agg:{CELL}"): "PASS",
            ("RD003", f"reported:{CELL}"): "NOT_APPLICABLE",
            ("RD004", "rule:RD004"): "NOT_RUN",
            ("RD005", CELL): "PASS",
            ("RD006", f"reported:{CELL}"): "PASS",
            ("RD007", "rule:RD007"): "NOT_RUN",
            ("RD008", f"quantity:{CELL}"): "INCONCLUSIVE",
        },
        "findings": 8,
    },
    # G2: nothing was parser-error, and nothing is PASS either.
    "g2": {
        "vector": {
            ("RD001", CELL): "INCONCLUSIVE",
            ("RD002", f"aggregation:agg:{CELL}"): "INCONCLUSIVE",
            ("RD003", f"reported:{CELL}"): "NOT_APPLICABLE",
            ("RD004", "rule:RD004"): "NOT_RUN",
            ("RD005", CELL): "INCONCLUSIVE",
            ("RD006", f"reported:{CELL}"): "INCONCLUSIVE",
            ("RD007", "rule:RD007"): "NOT_RUN",
            ("RD008", f"quantity:{CELL}"): "INCONCLUSIVE",
        },
        "findings": 8,
    },
    # G3: the same manifest in a directory full of suggestive names.
    "g3": {
        "vector": {},
        "findings": 8,
    },
    "g4": {
        "vector": {
            ("RD001", CELL): "PASS",
            ("RD002", f"aggregation:agg:{CELL}"): "PASS",
            ("RD003", f"reported:{CELL}"): "NOT_APPLICABLE",
            ("RD004", "rule:RD004"): "NOT_RUN",
            ("RD005", CELL): "FAIL",
            ("RD006", f"reported:{CELL}"): "PASS",
            ("RD007", "rule:RD007"): "NOT_RUN",
            ("RD008", f"quantity:{CELL}"): "INCONCLUSIVE",
        },
        "findings": 8,
    },
    "g5": {
        "vector": {
            ("RD001", "acc/ours"): "PASS",
            ("RD002", "aggregation:agg:acc/ours"): "PASS",
            ("RD003", "reported:acc/ours"): "NOT_APPLICABLE",
            ("RD004", "rule:RD004"): "NOT_RUN",
            ("RD005", "acc/ours"): "PASS",
            ("RD006", "reported:acc/ours"): "PASS",
            ("RD007", "comparison:cmp:table4"): "INCONCLUSIVE",
            ("RD008", "quantity:acc/ours"): "INCONCLUSIVE",
        },
        "findings": 8,
    },
    # Phase 2 §20 Example B, now a real input.
    "example_b": {
        "vector": {
            ("RD001", "acc/x"): "FAIL",
            ("RD001", "acc/y"): "PASS",
            ("RD002", "aggregation:agg:acc/x"): "PASS",
            ("RD002", "aggregation:agg:acc/y"): "PASS",
            ("RD003", "reported:acc/x"): "NOT_APPLICABLE",
            ("RD003", "reported:acc/y"): "NOT_APPLICABLE",
            ("RD003", "selection:sel:0"): "INCONCLUSIVE",
            ("RD004", "candidates:cand:0"): "PASS",
            ("RD005", "acc/x"): "NOT_APPLICABLE",
            ("RD005", "acc/y"): "NOT_APPLICABLE",
            ("RD006", "reported:acc/x"): "INCONCLUSIVE",
            ("RD006", "reported:acc/y"): "PASS",
            ("RD007", "comparison:cmp:0"): "INCONCLUSIVE",
            ("RD008", "rule:RD008"): "NOT_RUN",
        },
        "findings": 14,
    },
}
EXPECTED["g3"]["vector"] = EXPECTED["g1"]["vector"]


def manifest_path(case: str) -> str:
    return os.path.join(FIXTURES, case, "result-doctor.yml")


def vector_of(findings) -> dict[tuple[str, str], str]:
    return {(f.rule_id, f.target): f.status.value for f in findings}


def findings_of(case: str):
    return audit_manifest(manifest_path(case))


@pytest.mark.parametrize("case", ["g1", "g2", "g3", "g4", "g5", "example_b"])
def test_the_status_vector_is_exactly_the_oracle(case: str) -> None:
    findings = findings_of(case)
    assert vector_of(findings) == EXPECTED[case]["vector"]
    assert len(findings) == EXPECTED[case]["findings"]


def test_g1_invents_no_selection_or_candidate_target() -> None:
    """G1 reverse invariant: an absent object class stays absent, never implicit."""
    findings = findings_of("g1")
    assert not [f.target for f in findings if f.target.startswith(("selection:", "candidates:", "comparison:"))]
    bundle = bundle_from_manifest(manifest_path("g1"))
    assert bundle.selection_events == {} and bundle.candidate_sets == {} and bundle.comparison_sets == {}
    for rule_id in ("RD004", "RD007"):
        f = next(f for f in findings if f.rule_id == rule_id)
        assert f.status is RuleStatus.NOT_RUN
        assert f.measurements["n_objects"] == 0 and f.measurements["n_targets"] == 0
        assert f.evidence == (), "a NOT_RUN record claims nothing, so it cites nothing"


def test_g1_does_not_read_universe_size_from_the_member_count() -> None:
    f = next(f for f in findings_of("g1") if f.rule_id == "RD005")
    assert f.measurements["n"] == 3
    bundle = bundle_from_manifest(manifest_path("g1"))
    agg = bundle.aggregations[f"aggregation:agg:{CELL}".removeprefix("aggregation:")]
    assert len(agg.member_ids) == 3
    assert bundle.candidate_sets == {}, "three members are not three candidates"


def test_g2_loads_and_abstains_rather_than_failing() -> None:
    """G2 reverse invariant: missing fields are not a parser error and not a FAIL."""
    findings = findings_of("g2")
    assert not [f for f in findings if f.status.value == "FAIL"]
    assert not [f for f in findings if f.status.value == "PASS"]
    assert "member rule is not declared" in next(f.reason for f in findings if f.rule_id == "RD001")
    assert "no wording declares" in next(f.reason for f in findings if f.rule_id == "RD005")


def test_g3_file_names_change_nothing_in_the_bundle_or_the_output() -> None:
    """G3 reverse invariant: the loader has no discovery, so decoys are invisible."""
    assert canonical_json(findings_of("g3")) == canonical_json(findings_of("g1"))
    bundle = bundle_from_manifest(manifest_path("g3"))
    output = canonical_json(findings_of("g3")) + json.dumps(
        sorted({m.member_id for m in bundle.members.values()})
        + sorted(bundle.aggregations)
        + sorted(bundle.candidate_sets)
        + sorted(bundle.artifacts)
    )
    for decoy in ("best.pt", "seed_42", "final", "mean.csv", "results.csv", "wandb_group_a", "99.99"):
        assert decoy not in output, decoy
    paths = {s.path for m in bundle.members.values() for s in m.observed_value.sources}
    assert paths == {f"runs/{d}/log.csv" for d in "abc"}
    assert len(bundle.members) == 3


def test_g4_wording_neither_upgrades_nor_downgrades_the_recomputation() -> None:
    """G4 reverse invariant: RD005 FAILs on its own axis while RD001 stays PASS."""
    g1 = {f.rule_id: f.status.value for f in findings_of("g1") if f.rule_id in ("RD001", "RD006")}
    g4 = {f.rule_id: f.status.value for f in findings_of("g4") if f.rule_id in ("RD001", "RD006")}
    assert g1 == g4 == {"RD001": "PASS", "RD006": "PASS"}
    f = next(f for f in findings_of("g4") if f.rule_id == "RD005")
    assert f.measurements["spread_label_grade"] == "DECLARED"
    assert f.measurements["families_matching_published_spread"] == ["std_ddof0"]


def test_g5_keeps_the_external_baseline_outside_the_bundle() -> None:
    """G5 reverse invariant: an inaccessible peer yields no fact and no FAIL."""
    bundle = bundle_from_manifest(manifest_path("g5"))
    assert "external/eqnet" not in bundle.reported_results
    assert list(bundle.reported_results) == ["acc/ours"]
    findings = findings_of("g5")
    assert not [f for f in findings if f.status.value == "FAIL"]
    f = next(f for f in findings if f.rule_id == "RD007")
    assert f.measurements["peer_values_recoverable"] is False
    assert f.measurements["external_origin_grade"] == "UNKNOWN"
    assert f.measurements["n_members"] == 2
    assert "not every peer value" in f.reason
    g = next(f for f in findings if f.rule_id == "RD008")
    assert g.measurements["n_loci"] == 1


@pytest.mark.parametrize(
    "archive,loader",
    [(GMMVI_ARCHIVE, load_gmmvi_bundle), (TORCHSSL_ARCHIVE, load_torchssl_bundle)],
    ids=["gmmvi", "torchssl"],
)
def test_g0_the_generic_entry_layer_adds_nothing_to_the_frozen_archives(archive: str, loader) -> None:
    """G0: legacy output is byte-identical, and the NOT_RUN layer is a no-op on it."""
    if not os.path.isdir(archive):
        pytest.skip(f"frozen archive not present at {archive}")
    bundle = loader(archive)
    legacy = evaluate(bundle)
    assert canonical_json(audit_bundle(bundle)) == canonical_json(legacy)
    assert not [f for f in audit_bundle(bundle) if f.status is RuleStatus.NOT_RUN]


def test_g0_example_a_and_b_are_loadable_without_adaptation_files() -> None:
    """The fixtures carry no generated state: two parses of one manifest agree."""
    for case in ("g1", "example_b"):
        path = manifest_path(case)
        assert canonical_json(audit_manifest(path)) == canonical_json(audit_manifest(path))
