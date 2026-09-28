"""§21 firewall for the generic path, plus the §12 error/unknown split.

Row by row, each test states a confusion the loader could have committed and shows the
artifact that proves it did not. The last group pins the other side of §12: a manifest
that cannot be read as a contract raises with a code, and never quietly substitutes a
scientific default for the field it could not read.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any

import pytest
from test_firewall import BANNED  # the same vocabulary ban as Phase 1 §8

from result_doctor.audit import audit_manifest, not_run_findings
from result_doctor.bundle import Bundle
from result_doctor.evidence import EvidenceField, Grade
from result_doctor.manifest import bundle_from_manifest
from result_doctor.rules import evaluate
from result_doctor.schema import (
    Aggregation,
    AggregationMember,
    CandidateSet,
    ComparisonSet,
    ReportedResult,
    ResultArtifact,
    SelectionEvent,
    Transformation,
)
from result_doctor.status import RuleStatus, canonical_json

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generic_fixtures")
G1 = os.path.join(FIXTURES, "g1", "result-doctor.yml")
G2 = os.path.join(FIXTURES, "g2", "result-doctor.yml")
G5 = os.path.join(FIXTURES, "g5", "result-doctor.yml")
EXAMPLE_B = os.path.join(FIXTURES, "example_b", "result-doctor.yml")

CELL = "acc/cifar-resnet20"
AGG = f"agg:{CELL}"

#: One cell, one OBSERVED member and one DECLARED member: both doors, hand-computable.
#: mean(0.80, 2.00) = 1.40 and std ddof=1 = 0.848528 -> "0.85".
BASE = """schema_version: 1
project: err
root: .
reported_results:
  - label: c/1
    value: {declared: {value: "1.40 +/- 0.85", by: author}}
    spread: {kind: std, ddof: 1}
    aggregate: {center: mean}
    members:
      - {name: a, path: runs/a/log.csv, column: acc, row: last}
      - {name: b, value: 2.0}
    member_rule: {kind: enumerated, declared: {value: enumerated, by: author}}
    steps:
      - {step: format, stage: render, mode: fixed, digits: 2, applied_at: manual}
"""

GOOD_STEP = "      - {step: format, stage: render, mode: fixed, digits: 2, applied_at: manual}"
LOCATOR = "path: runs/a/log.csv, column: acc, row: last"
CELL_VALUE = """    value: {declared: {value: "1.40 +/- 0.85", by: author}}\n"""

ART = {
    "runs/a/log.csv": "epoch,acc\n1,0.70\n2,0.80\n",
    "paper/t.txt": "x\n\nmean value\n\ny\nz 1.40 +/- 0.85\n",
    "ckpt/r1/val.json": '{"acc": {"ep1": 0.7}}\n',
}


def load(tmp_path, text: str, files: dict[str, str] | None = None) -> str:
    for rel, body in (files or {}).items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    path = tmp_path / "result-doctor.yml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def bad(tmp_path, text: str) -> str:
    return load(tmp_path, text, ART)


def raises(tmp_path, text: str) -> str:
    """Load `text` expecting a refusal, and hand back its error code."""
    with pytest.raises(Exception) as excinfo:
        bundle_from_manifest(bad(tmp_path, text))
    return excinfo.value.code


def grades_of(bundle: Bundle) -> set[str]:
    """Every evidence grade the loader put anywhere in the bundle."""
    out: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, EvidenceField):
            out.add(node.grade.value)
        elif dataclasses.is_dataclass(node) and not isinstance(node, type):
            for f in dataclasses.fields(node):
                walk(getattr(node, f.name))
        elif isinstance(node, (list, tuple, set)):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for item in node.values():
                walk(item)

    for name in (
        "reported_results",
        "aggregations",
        "members",
        "artifacts",
        "transformations",
        "candidate_sets",
        "selection_events",
        "comparison_sets",
    ):
        walk(getattr(bundle, name))
    return out


# ------------------------------------------------------------------ the eleven rows
def test_row1_a_missing_field_stays_UNKNOWN_and_never_becomes_a_fact(tmp_path) -> None:
    """`missing field != false fact`: nothing is defaulted into a scientific value."""
    path = load(
        tmp_path,
        """schema_version: 1
project: sparse
root: .
reported_results:
  - label: c/1
    value: {declared: {value: "1.40", by: author}}
""",
    )
    bundle = bundle_from_manifest(path)
    rr = bundle.reported_results["c/1"]
    assert rr.metric_name.grade is Grade.UNKNOWN and rr.metric_name.value is None
    assert rr.spread.grade is Grade.UNKNOWN and rr.spread_label.grade is Grade.UNKNOWN
    assert rr.transformation_refs == () and rr.spread_form.kind.value == "none"
    assert bundle.aggregations == {} and bundle.selection_events == {} and bundle.candidate_sets == {}
    statuses = {(f.rule_id, f.status.value) for f in audit_manifest(path)}
    assert ("RD001", "INCONCLUSIVE") in statuses and ("RD005", "NOT_APPLICABLE") in statuses
    assert not [pair for pair in statuses if pair[1] in ("PASS", "FAIL")]


def test_row1_a_center_is_not_defaulted(tmp_path) -> None:
    assert raises(tmp_path, BASE.replace("aggregate: {center: mean}", "aggregate: {}")) == "E_MISSING_FIELD"
    assert raises(tmp_path, BASE.replace("aggregate: {center: mean}", "aggregate: {center: UNKNOWN}")) == "E_BAD_ENUM"


def test_row2_listed_candidates_are_not_the_universe(tmp_path) -> None:
    """`listed candidates != complete universe`, however exhaustive the list looks."""
    path = load(
        tmp_path,
        BASE
        + """candidate_sets:
  - kind: hyperparameter
    members: [lr=0.1, lr=0.01, lr=0.001]
""",
        ART,
    )
    cs = bundle_from_manifest(path).candidate_sets["cand:0"]
    assert cs.universe_status.value == "UNKNOWN"
    assert cs.declared_size.grade is Grade.DECLARED and cs.declared_size.value == 3
    assert cs.surviving_size.grade is Grade.UNKNOWN
    f = next(f for f in audit_manifest(path) if f.rule_id == "RD004")
    assert f.status is RuleStatus.INCONCLUSIVE
    assert "universe_size" not in f.measurements
    assert "never inferred from the count" in f.reason


def test_row2_a_universe_claim_without_evidence_is_downgraded(tmp_path) -> None:
    """`universe: complete` is an assertion; with no locator it earns DECLARED_ONLY."""
    path = load(
        tmp_path,
        BASE
        + """candidate_sets:
  - kind: hyperparameter
    members: [lr=0.1, lr=0.01]
    universe: complete
""",
        ART,
    )
    assert bundle_from_manifest(path).candidate_sets["cand:0"].universe_status.value == "DECLARED_ONLY"
    f = next(f for f in audit_manifest(path) if f.rule_id == "RD004")
    assert f.status is RuleStatus.INCONCLUSIVE


def test_row2_sizes_in_one_unit_are_comparable(tmp_path) -> None:
    """Two sizes in the same unit are comparable; different units are not (RD004)."""
    path = load(
        tmp_path,
        BASE
        + """candidate_sets:
  - kind: checkpoint
    universe: recovered
    universe_evidence: {observed: {path: paper/t.txt, line: 3}}
    declared_size: {value: 2, statement: evaluations}
    surviving_size: {value: 1, statement: evaluations}
""",
        ART,
    )
    cs = bundle_from_manifest(path).candidate_sets["cand:0"]
    assert cs.universe_status.value == "RECOVERED"
    assert cs.declared_size.grade is Grade.DECLARED and cs.surviving_size.grade is Grade.DECLARED
    f = next(f for f in audit_manifest(path) if f.rule_id == "RD004")
    assert f.measurements["sizes_stated_in_same_unit"] is True
    assert f.status is RuleStatus.PASS


def test_row3_a_declaration_is_not_an_observation() -> None:
    """`declared evidence != direct observation`, including when the number is right."""
    declared = bundle_from_manifest(G2).members[f"{AGG}/seed-a"]
    assert declared.observed_value.grade is Grade.DECLARED and declared.observed_value.value == 93.85
    assert declared.observed_value.sources[0].path.startswith("result-doctor.yml#reported_results[0]/members[0]")
    observed = bundle_from_manifest(G1).members[f"{AGG}/seed-a"]
    assert observed.observed_value.grade is Grade.DIRECT
    assert observed.observed_value.sources[0].path == "runs/a/log.csv"
    assert observed.observed_value.sources[0].key == "column:test_acc"


def test_row4_a_file_name_carries_no_provenance(tmp_path) -> None:
    """`best filename != best-checkpoint provenance`: a name is only a path."""
    path = load(
        tmp_path,
        """schema_version: 1
project: names
root: .
reported_results:
  - label: c/1
    value: {declared: {value: "0.80", by: author}}
    aggregate: {center: mean}
    members:
      - name: best
        path: runs/seed_42/best_final_mean.csv
        column: acc
        row: last
""",
        {"runs/seed_42/best_final_mean.csv": "epoch,acc\n1,0.70\n2,0.80\n"},
    )
    member = bundle_from_manifest(path).members["agg:c/1/best"]
    assert member.observed_value.value == 0.80
    #: The only selector the loader knows is the one the manifest itself wrote (`row: last`).
    assert member.selector.kind.value == "last_row" and member.selector.grade is Grade.DECLARED
    assert member.selector.kind.value not in ("best", "mean_over_rows", "final_epoch")
    assert member.run_ref.external_id.grade is Grade.UNKNOWN
    assert member.run_ref.run_name == "best", "an author-chosen label, not a claim about epochs"
    assert bundle_from_manifest(path).selection_events == {}


def test_row4_the_best_claim_stays_a_declaration() -> None:
    selector = bundle_from_manifest(EXAMPLE_B).members["agg:acc/x/r1"].selector
    assert selector.kind.value == "best" and selector.grade is Grade.DECLARED


def test_row5_two_aggregations_over_one_file_stay_two_aggregations(tmp_path) -> None:
    """`same directory != same aggregation`: sharing a product links nothing."""
    path = load(
        tmp_path,
        """schema_version: 1
project: same-file
root: .
aggregations:
  - id: first-two
    center: mean
    members:
      - {name: row1, path: runs/a/log.csv, column: acc, row: 1}
      - {name: row2, path: runs/a/log.csv, column: acc, row: 2}
  - id: last-one
    center: mean
    members:
      - {name: row2, path: runs/a/log.csv, column: acc, row: last}
""",
        ART,
    )
    bundle = bundle_from_manifest(path)
    assert bundle.aggregations["agg:first-two"].member_ids == ("agg:first-two/row1", "agg:first-two/row2")
    assert bundle.aggregations["agg:last-one"].member_ids == ("agg:last-one/row2",)
    sizes = {f.target: f.measurements["n_members"] for f in audit_manifest(path) if f.rule_id == "RD002"}
    assert sizes == {"aggregation:agg:first-two": 2, "aggregation:agg:last-one": 1}


def test_row6_a_repeated_group_name_is_neither_identity_nor_independence(tmp_path) -> None:
    path = load(
        tmp_path,
        BASE
        + """candidate_sets:
  - kind: hyperparameter
    members: [grid_a, grid_a, grid_b]
""",
        ART,
    )
    coll = bundle_from_manifest(path).candidate_sets["cand:0"].identity_collision
    assert coll is not None and coll.collision_count == 1
    assert coll.samples == ({"ref": "grid_a", "listed_times": 2},)
    assert "not determined here" in coll.note
    f = next(f for f in audit_manifest(path) if f.rule_id == "RD004")
    assert f.status is RuleStatus.INCONCLUSIVE
    for banned in ("same grid", "unrelated", "confus", "duplicate"):
        assert banned not in f.reason.lower()


def test_row7_a_manifest_that_parses_is_not_a_manifest_that_proves() -> None:
    """`successful parse != scientific completeness`: G2 parses and proves nothing."""
    findings = audit_manifest(G2)
    assert len(findings) == 8
    assert {f.status.value for f in findings} == {"INCONCLUSIVE", "NOT_APPLICABLE", "NOT_RUN"}


def test_row8_a_declared_identity_unlocks_a_FAIL_without_becoming_evidence() -> None:
    """`declared identity != observed identity`: the cap lifts, the grade does not."""
    bundle = bundle_from_manifest(EXAMPLE_B)
    for name in ("r1", "r2", "r3"):
        identity = bundle.members[f"agg:acc/x/{name}"].run_ref.external_id
        assert identity.grade is Grade.DECLARED and identity.sources[0].path.startswith("result-doctor.yml#")
    fail = next(f for f in audit_manifest(EXAMPLE_B) if f.rule_id == "RD001" and f.target == "acc/x")
    assert fail.status is RuleStatus.FAIL and "all determined" in fail.reason
    capped = next(f for f in audit_manifest(G2) if f.rule_id == "RD001")
    assert capped.status is RuleStatus.INCONCLUSIVE and "identity is not determined" in capped.reason


def test_row9_marks_are_two_lists_never_a_derivation() -> None:
    """`declared marks != recomputed marks`: the tool only reports the grades it was given."""
    f = next(f for f in audit_manifest(G5) if f.rule_id == "RD007")
    assert f.measurements["marks_recovered_from"] == "DECLARED"
    assert "rule" not in f.reason.lower()
    cs = bundle_from_manifest(G5).comparison_sets["cmp:table4"]
    assert cs.observed_marks.grade is Grade.DECLARED
    assert cs.observed_marks.sources[0].path.startswith("result-doctor.yml#comparisons[0]/marks")
    assert cs.observed_marks.sources[-1].path == "paper/table4.txt"
    assert tuple(cs.observed_marks.value) == cs.recomputed_marks == ("acc/ours",)


def test_row10_an_unapplied_step_is_rejected_where_it_would_lie(tmp_path) -> None:
    for step in ("round", "delta", "best_of_n", "truncate_window"):
        text = BASE.replace(GOOD_STEP, f"      - {{step: {step}, stage: member}}")
        assert raises(tmp_path, text) == "E_STEP_NOT_APPLIED", step
    assert raises(tmp_path, BASE.replace(GOOD_STEP, "      - {step: scale, stage: render, factor: 2}")) == (
        "E_RENDER_STEP"
    )
    #: The same lie in the other direction: a format step that renders nothing.
    lie = BASE.replace(GOOD_STEP, "      - {step: format, stage: member, mode: fixed, digits: 2}")
    assert raises(tmp_path, lie) == "E_RENDER_STEP"


def test_row11_an_inline_value_is_never_an_artifact_cell(tmp_path) -> None:
    """`inline value != artifact cell value`: the grade stays DECLARED even when it matches."""
    bundle = bundle_from_manifest(load(tmp_path, BASE, ART))
    member = bundle.members["agg:c/1/b"]
    assert member.observed_value.grade is Grade.DECLARED
    assert member.artifact_ref == "" and member.run_ref.artifact_ref == ""
    assert bundle.artifacts == {}
    assert next(f for f in audit_manifest(load(tmp_path, BASE, ART)) if f.rule_id == "RD001").status is (
        RuleStatus.PASS
    )


# ------------------------------------------------------------------ structure gates
def test_the_generic_path_never_emits_INFERRED_or_DERIVED(tmp_path) -> None:
    for path in (G1, G2, G5, EXAMPLE_B, load(tmp_path, BASE, ART)):
        assert grades_of(bundle_from_manifest(path)) <= {"DIRECT", "DECLARED", "UNKNOWN"}


def test_no_banned_vocabulary_in_a_generic_finding() -> None:
    for path in (G1, G2, G5, EXAMPLE_B):
        for f in audit_manifest(path):
            low = (f.reason + json.dumps(f.measurements, default=str) + f.target).lower()
            for word in BANNED:
                assert word not in low, f"{word} in {f.rule_id}/{f.target}"


def test_generic_output_carries_no_score_key() -> None:
    payload = json.loads(canonical_json(audit_manifest(EXAMPLE_B)))

    def keys(node):
        if isinstance(node, dict):
            yield from node
            for value in node.values():
                yield from keys(value)
        elif isinstance(node, list):
            for value in node:
                yield from keys(value)

    names = [k.lower() for k in keys(payload)]
    assert names
    for banned in ("overall", "score", "confidence", "trust", "verdict", "ranking"):
        assert not any(banned in k for k in names), sorted(set(names))


def test_the_generic_bundle_uses_only_the_eight_frozen_objects() -> None:
    """No manifest-specific schema: the same dataclasses the frozen adapters build."""
    expected = {
        "reported_results": ReportedResult,
        "aggregations": Aggregation,
        "members": AggregationMember,
        "artifacts": ResultArtifact,
        "transformations": Transformation,
        "candidate_sets": CandidateSet,
        "selection_events": SelectionEvent,
        "comparison_sets": ComparisonSet,
    }
    for path in (G1, G2, G5, EXAMPLE_B):
        bundle = bundle_from_manifest(path)
        assert type(bundle) is Bundle
        for name, cls in expected.items():
            values = list(getattr(bundle, name).values())
            assert all(type(v) is cls for v in values), (path, name)


def test_the_entry_layer_only_adds_NOT_RUN_records(tmp_path) -> None:
    """It records an absent object class and rewrites no judgment the rules already made."""
    g1 = bundle_from_manifest(G1)
    assert [f.rule_id for f in not_run_findings(g1, evaluate(g1))] == ["RD004", "RD007"]
    for path in (G1, G2, G5, EXAMPLE_B, load(tmp_path, BASE, ART)):
        bundle = bundle_from_manifest(path)
        ran = {f.rule_id for f in evaluate(bundle)}
        added = not_run_findings(bundle, evaluate(bundle))
        assert all(f.status is RuleStatus.NOT_RUN and f.evidence == () for f in added)
        assert not [f.rule_id for f in added if f.rule_id in ran], path
    empty = Bundle(project="nothing")
    added = not_run_findings(empty, evaluate(empty))
    assert [f.rule_id for f in added] == [f"RD{i:03d}" for i in range(1, 9)]
    assert {f.status for f in added} == {RuleStatus.NOT_RUN}
    assert all(f.evidence == () for f in added)
    assert audit_manifest(load(tmp_path, BASE, ART))[0].rule_id == "RD001"


# ------------------------------------------------------------------ §12 error codes
ERROR_CODES = {
    "E_YAML",
    "E_ROOT",
    "E_SCHEMA_VERSION",
    "E_TOP_LEVEL",
    "E_UNKNOWN_KEY",
    "E_MISSING_FIELD",
    "E_DUPLICATE_ID",
    "E_UNRESOLVED_REF",
    "E_BAD_ENUM",
    "E_BAD_FIELD",
    "E_BAD_DIRECTION",
    "E_STEP_NOT_APPLIED",
    "E_RENDER_STEP",
    "E_PATH_OUTSIDE_ROOT",
    "E_ARTIFACT_MISSING",
    "E_LOCATOR_KEYS",
    "E_LOCATOR_LINE",
    "E_LOCATOR_TEXT",
    "E_LOCATOR_COLUMN",
    "E_LOCATOR_ROW",
    "E_LOCATOR_KEY",
    "E_NOT_A_NUMBER",
    "E_TYPE",
    "E_UNIVERSE_EVIDENCE",
    "E_MARK_DERIVATION",
    "E_CONFLICTING_REF",
}


def test_the_error_vocabulary_is_exactly_the_documented_one() -> None:
    from result_doctor import manifest

    emitted = {v for k, v in vars(manifest).items() if k.startswith("E_") and isinstance(v, str)}
    assert emitted == ERROR_CODES


@pytest.mark.parametrize(
    "text,code",
    [
        ("schema_version: 1\nproject: x\nroot: .\nreported_results: [\n", "E_YAML"),
        ("- a\n- b\n", "E_TOP_LEVEL"),
        (BASE.replace("schema_version: 1", "schema_version: 2"), "E_SCHEMA_VERSION"),
        (BASE.replace("project: err", "project: err\nscanners: []"), "E_UNKNOWN_KEY"),
        (BASE.replace("- {name: a, path:", "- {mood: sunny, name: a, path:"), "E_UNKNOWN_KEY"),
        (BASE.replace(CELL_VALUE, ""), "E_MISSING_FIELD"),
        (BASE + '  - label: c/1\n    value: {declared: {value: "1.40", by: author}}\n', "E_DUPLICATE_ID"),
        (BASE.replace("- {name: b, value: 2.0}", "- {name: b}"), "E_MISSING_FIELD"),
        (BASE.replace("aggregate: {center: mean}", "aggregate: {center: median, ref: x}"), "E_UNKNOWN_KEY"),
        (BASE.replace("spread: {kind: std, ddof: 1}", "spread: {kind: mad}"), "E_BAD_ENUM"),
        (BASE.replace("- {name: b, value: 2.0}", "- {name: b, value: two}"), "E_NOT_A_NUMBER"),
        (BASE + "candidate_sets:\n  kind: checkpoint\n", "E_TYPE"),
        (BASE.replace("runs/a/log.csv", "../../secrets.txt"), "E_PATH_OUTSIDE_ROOT"),
        (BASE.replace("runs/a/log.csv", "C:/Windows/win.ini"), "E_PATH_OUTSIDE_ROOT"),
        (BASE.replace("runs/a/log.csv", "runs/gone/log.csv"), "E_ARTIFACT_MISSING"),
        (BASE.replace(LOCATOR, "path: runs/a/log.csv"), "E_LOCATOR_KEYS"),
        (BASE.replace(LOCATOR, "path: runs/a/log.csv, column: nope, row: 1"), "E_LOCATOR_COLUMN"),
        (BASE.replace(LOCATOR, "path: runs/a/log.csv, column: acc, row: 9"), "E_LOCATOR_ROW"),
        (BASE.replace(LOCATOR, "path: paper/t.txt, line: 99"), "E_LOCATOR_LINE"),
        (BASE.replace(LOCATOR, 'path: paper/t.txt, line: 6, text: "9.90 +/- 0.85"'), "E_LOCATOR_TEXT"),
        (BASE.replace(LOCATOR, "path: ckpt/r1/val.json, key: /nope"), "E_LOCATOR_KEY"),
        (
            BASE.replace(
                "- {name: b, value: 2.0}",
                "- {name: b, value: 2.0, path: runs/a/log.csv, column: acc, row: last}",
            ),
            "E_BAD_FIELD",
        ),
        (
            BASE.replace(
                "member_rule: {kind: enumerated, declared: {value: enumerated, by: author}}",
                "member_rule: {kind: enumerated, declared: 1, observed: {path: paper/t.txt, line: 3}}",
            ),
            "E_BAD_FIELD",
        ),
        (BASE.replace(CELL_VALUE, '    value: {inferred: {value: "1.40", by: author}}\n'), "E_UNKNOWN_KEY"),
        (BASE + "evidence:\n  - id: e1\n    unknown: nothing\n  - id: e1\n    unknown: nothing\n", "E_DUPLICATE_ID"),
        (
            BASE + "candidate_sets:\n  - id: same\n    kind: checkpoint\n  - id: same\n    kind: checkpoint\n",
            "E_DUPLICATE_ID",
        ),
        (BASE + "selection_events:\n  - kind: checkpoint\n    over: 7\n", "E_UNRESOLVED_REF"),
        (BASE.replace("- {name: b, value: 2.0}", "- {name: b, value: 2.0, identity: {via: nope}}"), "E_UNRESOLVED_REF"),
        (
            BASE + "candidate_sets:\n  - kind: checkpoint\n    members: [a]\n"
            "selection_events:\n  - kind: checkpoint\n    over: 0\n"
            "    criterion:\n      direction: {declared: {value: lower is better, by: author}}\n",
            "E_BAD_DIRECTION",
        ),
        (BASE + "candidate_sets:\n  - kind: checkpoint\n    universe: unrecoverable\n", "E_UNIVERSE_EVIDENCE"),
        (
            BASE + "comparisons:\n  - over: [c/1]\n    marks: {declared: {value: [c/1], by: author}}\n",
            "E_MARK_DERIVATION",
        ),
        (
            BASE + 'comparisons:\n  - over: [c/1]\n    marks: {observed: {path: paper/t.txt, line: 6, text: "1.40"}}\n'
            "    marks_derivation: {declared: {value: [c/1], by: author}}\n",
            "E_BAD_FIELD",
        ),
        (BASE + "comparisons:\n  - id: one\n    over: [c/1]\n  - id: two\n    over: [c/1]\n", "E_CONFLICTING_REF"),
        (BASE + "root: no-such-directory\n", "E_ROOT"),
    ],
    ids=[
        "yaml",
        "top-level",
        "version",
        "unknown-section",
        "unknown-key",
        "no-printed-cell",
        "duplicate-label",
        "member-without-value",
        "aggregate-ref-combined",
        "spread-enum",
        "not-a-number",
        "section-as-mapping",
        "parent-escape",
        "absolute-escape",
        "missing-artifact",
        "locator-without-locator",
        "locator-column",
        "locator-row",
        "locator-line",
        "locator-text",
        "locator-json-key",
        "member-value-and-locator",
        "two-doors",
        "door-that-does-not-exist",
        "duplicate-evidence-id",
        "duplicate-candidate-set-id",
        "selection-over-nothing",
        "evidence-via-unknown",
        "direction-not-min-max",
        "unrecoverable-without-evidence",
        "marks-without-derivation",
        "marks-observed",
        "cell-in-two-comparison-sets",
        "root-missing",
    ],
)
def test_a_manifest_that_is_not_a_contract_raises_with_a_code(tmp_path, text: str, code: str) -> None:
    assert raises(tmp_path, text) == code


def test_an_error_message_names_the_code_the_object_and_the_problem(tmp_path) -> None:
    """§26: readable, without a diagnostic framework."""
    with pytest.raises(Exception) as excinfo:
        bundle_from_manifest(bad(tmp_path, BASE.replace("center: mean", "center: trimmed_mean")))
    message = str(excinfo.value)
    assert message.startswith("E_BAD_ENUM at reported_results[0]/aggregate:")
    assert "center='trimmed_mean'" in message and "is not one of ['mean', 'median']" in message


def test_a_thin_manifest_audits_and_never_raises() -> None:
    """The other channel of §12: no evidence is not a parse failure anywhere."""
    assert audit_manifest(G2) and audit_manifest(G1)
