"""§8 / §15.3 firewall: the inferences Result Doctor must never make, locked as tests.

Each test corresponds to one row of the Phase 0 firewall table and uses the real archive
evidence for that row, so the guarantee is about the shipped loaders and rules.
"""

from __future__ import annotations

import dataclasses
import os
import re

import pytest

import result_doctor
from result_doctor import schema as schema_module
from result_doctor.evidence import EvidenceField
from result_doctor.loaders import load_gmmvi_bundle, load_torchssl_bundle
from result_doctor.rules import evaluate
from result_doctor.status import RuleFinding, UniverseStatus

GMMVI_ARCHIVE = os.environ.get("RD_GMMVI_ARCHIVE", r"F:\MLResearch\experiment-doctor\phase0-gmmvi")
TORCHSSL_ARCHIVE = os.environ.get("RD_TORCHSSL_ARCHIVE", r"F:\MLResearch\experiment-doctor\acceptance1-torchssl")

BANNED = (
    "p-hacking",
    "p-hacked",
    "cherry-pick",
    "cherry pick",
    "misconduct",
    "fraud",
    "可信度评分",
    "学术不当",
    "论文错误",
    "paper is wrong",
    "paper wrong",
    "invalid paper",
    "leakage",
    "negligen",
    "biased",
    "suspicious",
    "misleading",
)


@pytest.fixture(scope="module")
def gmmvi():
    if not os.path.isdir(GMMVI_ARCHIVE):
        pytest.skip(f"frozen GMMVI archive not present at {GMMVI_ARCHIVE}")
    bundle = load_gmmvi_bundle(GMMVI_ARCHIVE)
    return bundle, {(f.rule_id, f.target): f for f in evaluate(bundle)}


@pytest.fixture(scope="module")
def torchssl():
    if not os.path.isdir(TORCHSSL_ARCHIVE):
        pytest.skip(f"frozen TorchSSL archive not present at {TORCHSSL_ARCHIVE}")
    bundle = load_torchssl_bundle(TORCHSSL_ARCHIVE)
    return bundle, {(f.rule_id, f.target): f for f in evaluate(bundle)}


def _texts(table) -> list[tuple[str, str]]:
    return [(f.target, f.reason) for f in table.values()] + [(f.target, str(f.measurements)) for f in table.values()]


def test_no_banned_vocabulary_anywhere_in_the_findings(gmmvi, torchssl) -> None:
    for _, table in (gmmvi, torchssl):
        for target, text in _texts(table):
            low = text.lower()
            for word in BANNED:
                assert word not in low, f"{word} in {target}"


# ---------------------------------------------------------------- firewall rows
def test_many_runs_is_not_treated_as_selection(gmmvi) -> None:
    """Row 1: a group whose 30 seeds all count is a re-run count, and no rule reads it as picking."""
    bundle, table = gmmvi
    agg_id = next(a for a, agg in bundle.aggregations.items() if len(agg.member_ids) == 30)
    agg = bundle.aggregations[agg_id]
    f = table[("RD002", f"aggregation:{agg_id}")]
    assert f.measurements["n_members"] == len(agg.member_ids) == 30
    assert not agg.exclusions
    assert f.measurements["n_exclusions"] == 0
    assert f.status.value == "INCONCLUSIVE"
    assert "bound to an external run id" in f.reason
    rid = next(r for r, rr in bundle.reported_results.items() if rr.aggregation_ref == agg_id)
    cell = table[("RD001", rid)]
    assert cell.status.value == "PASS"
    assert cell.measurements["n_members"] == 30


def test_a_best_checkpoint_is_not_a_leakage_verdict(torchssl) -> None:
    """Row 2: the split is recorded, and the word for its consequence never appears."""
    _, table = torchssl
    f = table[("RD003", "selection:sel:checkpoint/fixmatch_cifar10_250_0")]
    assert f.status.value == "PASS"
    assert f.measurements["criterion_values"]["split"] == "test"
    assert "leak" not in (f.reason + str(f.measurements)).lower()


def test_surviving_count_is_never_reported_as_the_universe_size(gmmvi, torchssl) -> None:
    """Rows 3 and 4 plus S5: RD004 always reports both sizes and never a universe size."""
    for bundle, table in (gmmvi, torchssl):
        for f in table.values():
            assert "universe_size" not in f.measurements
        for f in table.values():
            if f.rule_id == "RD004":
                assert {"declared_size", "surviving_size"} <= set(f.measurements)
                assert f.measurements["surviving_size"] is not None
        for cs in bundle.candidate_sets.values():
            assert cs.universe_status is not None
    cs = torchssl[0].candidate_sets["candidates:hyperparameter/torchssl"]
    assert cs.universe_status.value == "UNRECOVERABLE"
    assert cs.declared_size.value == 3
    f = torchssl[1][("RD004", "candidates:candidates:hyperparameter/torchssl")]
    assert f.status.value == "INCONCLUSIVE"
    assert f.measurements["sizes_stated_in_same_unit"] is False


def test_a_mismatch_between_paper_and_recomputation_is_not_called_a_paper_error(gmmvi) -> None:
    """Row 5: FM1's conclusion is about artifact identity, and the status stays INCONCLUSIVE."""
    _, table = gmmvi
    for target in (
        "BreastCancer/samtron/-elbo/Table 8",
        "BreastCancer/sepyfux/-elbo/Table 8",
        "BreastCancer/sepyrux/-elbo/Table 8",
    ):
        f = table[("RD001", target)]
        assert f.status.value == "INCONCLUSIVE"
        assert "identity" in f.reason
    assert not any(
        f.status.value == "FAIL" and f.rule_id == "RD001" for f in table.values() if f.target.startswith("BreastCancer")
    )


def test_excluded_runs_are_recorded_without_a_motivation_judgment(gmmvi) -> None:
    """Row 6: 22 discarded runs on disk, referenced by 34 (cell, run) exclusion records."""
    bundle, table = gmmvi
    excluded = [m for m in bundle.members.values() if m.excluded]
    assert len(excluded) == 34
    assert len({(m.run_ref.family_key, m.run_ref.run_name) for m in excluded}) == 22
    for aid, agg in bundle.aggregations.items():
        if not agg.exclusions:
            continue
        f = table[("RD002", f"aggregation:{aid}")]
        assert f.status.value == "INCONCLUSIVE"
        assert "criterion is not recomputable" in f.reason
        assert "intent" not in f.reason.lower()


def test_shared_group_names_yield_neither_identity_nor_independence(gmmvi) -> None:
    """Row 7, the real case: 35/35 discarded names are reused, and the parameter evidence is
    comparable only over common keys - so the tool abstains in both directions."""
    bundle, table = gmmvi
    collision = bundle.candidate_sets["candidates:exp3-discarded-grid"].identity_collision
    assert collision.collision_count == 35 == len(collision.samples)
    same_key_sets = [
        s for s in collision.samples if s["common_key_count"] == s["adopted_key_count"] == s["discarded_key_count"]
    ]
    assert len(same_key_sets) == 7
    assert any(s["compared_over_common_keys"] is False for s in collision.samples)
    # no pair is fully disjoint on its common keys, and no pair is fully shared either
    assert not any(s["value_overlap_on_common_keys"] == 0 for s in collision.samples)
    assert any(0 < s["value_overlap_on_common_keys"] < s["common_key_count"] for s in collision.samples)
    assert "neither 'the same grid' nor 'an unrelated grid'" in collision.note
    for cid in ("candidates:exp3-adopted-grid", "candidates:exp3-discarded-grid"):
        reason = table[("RD004", f"candidates:{cid}")].reason.lower()
        assert "same grid" not in reason and "unrelated" not in reason
        assert "confus" not in reason and "混淆" not in reason


def test_a_bold_mark_is_not_read_as_a_claim_of_superiority(gmmvi) -> None:
    """Row 8: the mark depends on peers and an asymmetric operator; abstention is required."""
    _, table = gmmvi
    for env in ("TALOS", "STM300", "PlanarRobot", "BreastCancer"):
        f = table[("RD007", f"comparison:cmp:{env}")]
        assert f.status.value == "INCONCLUSIVE"
        assert "without a judgment" in f.reason or "two readings" in f.reason
        assert f.measurements["marks_recovered_from"] == "UNKNOWN"


def test_no_status_is_invented_to_fill_missing_evidence(gmmvi, torchssl) -> None:
    """Row 9: every PASS carries at least one located source."""
    for _, table in (gmmvi, torchssl):
        for f in table.values():
            if f.status.value == "PASS":
                assert f.evidence, f
                assert any(s.path for s in f.evidence), f.target


# ---------------------------------------------------------------- structure gates
def test_output_record_has_no_score_or_verdict_field() -> None:
    names = {f.name for f in dataclasses.fields(RuleFinding)}
    assert names == {"rule_id", "rule_name", "target", "status", "question", "measurements", "evidence", "reason"}
    for banned in ("score", "confidence", "trust", "verdict", "rank", "severity"):
        assert not any(banned in n for n in names)


def test_no_schema_object_is_a_dag_score_or_tracker_connection() -> None:
    present = {
        o.__name__
        for _, o in vars(schema_module).items()
        if dataclasses.is_dataclass(o) and getattr(o, "__module__", "") == "result_doctor.schema"
    }
    assert present == {
        "Locus",
        "SpreadForm",
        "RunRef",
        "ObservationSelector",
        "AggregationMember",
        "Exclusion",
        "MemberRule",
        "ProducedBy",
        "ResultArtifact",
        "Aggregation",
        "IdentityCollision",
        "UnobservableSource",
        "CandidateSet",
        "SelectionCriterion",
        "SelectionEvent",
        "PresentationRule",
        "ComparisonSet",
        "Transformation",
        "ReportedResult",
    }
    for banned in ("DAG", "ClaimRef", "Tracker", "Score", "MetricRecord", "Paper"):
        assert not any(banned in name for name in present)


def test_canonical_output_contains_no_score_key(gmmvi) -> None:
    """Gate the JSON keys, not the prose: a quoted paper caption may name its own interval."""
    import json

    from result_doctor.status import canonical_json

    payload = json.loads(canonical_json(evaluate(gmmvi[0])))

    def keys(node):
        if isinstance(node, dict):
            yield from node
            for v in node.values():
                yield from keys(v)
        elif isinstance(node, list):
            for v in node:
                yield from keys(v)

    names = [k.lower() for k in keys(payload)]
    assert names, "the serializer produced no keys"
    for banned in ("overall", "score", "confidence", "trust", "verdict", "ranking"):
        assert not any(banned in k for k in names), sorted(set(names))


def test_evidence_field_keeps_unknown_unreachable_from_pass() -> None:
    """An UNKNOWN evidence value can never be read as a fact by the rules."""
    unknown = EvidenceField(None)
    assert not unknown.is_known
    assert unknown.grade.value == "UNKNOWN"


def test_unrecoverable_requires_affirmative_evidence_not_absence(torchssl) -> None:
    """Absence of a search product defaults to UNKNOWN; UNRECOVERABLE must carry evidence."""
    from result_doctor.schema import CandidateKind, CandidateSet

    assert (
        CandidateSet(candidate_set_id="x", kind=CandidateKind.HYPERPARAMETER).universe_status is UniverseStatus.UNKNOWN
    )
    bundle = torchssl[0]
    unrecoverable = [cs for cs in bundle.candidate_sets.values() if cs.universe_status is UniverseStatus.UNRECOVERABLE]
    assert len(unrecoverable) == 1
    assert unrecoverable[0].unobservable_sources, "UNRECOVERABLE without evidence"
    assert all(u.evidence.is_known for u in unrecoverable[0].unobservable_sources)
    assert [cs for cs in bundle.candidate_sets.values() if cs.universe_status is UniverseStatus.UNKNOWN] == []


def test_package_exposes_no_network_or_tracker_dependency(gmmvi) -> None:
    src = os.path.dirname(result_doctor.__file__)
    banned_modules = ("requests", "wandb", "mlflow", "socket", "http", "urllib", "subprocess", "shutil", "sqlalchemy")
    offenders = []
    for root, _, files in os.walk(src):
        for name in files:
            if not name.endswith(".py"):
                continue
            text = open(os.path.join(root, name), encoding="utf-8").read()
            for mod in banned_modules:
                if re.search(rf"^\s*(?:import|from)\s+{mod}\b", text, re.MULTILINE):
                    offenders.append((name, mod))
    assert offenders == []
