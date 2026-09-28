"""Phase 5: authoring sugar and the two silent-trap guards.

Every case here is a shape Phase 4 actually had to write (or actually misread), so each
test states the author cost or the misjudgement it removes and asserts the loader still
refuses to guess. Nothing in this file adds a discovery mechanism or a new error code.
"""

from __future__ import annotations

import json
import os

import pytest
from test_generic_firewall import ART, BASE, CELL_VALUE, load, raises

from result_doctor.audit import audit_manifest
from result_doctor.bundle import Bundle
from result_doctor.evidence import Grade
from result_doctor.manifest import bundle_from_manifest
from result_doctor.rules import evaluate
from result_doctor.status import canonical_json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHASE4_DIR = os.path.join(REPO, "phase4", "rtdl-revisiting-models")
#: The Phase 4 manifest as it was authored, kept for the backward-compatibility check.
BEFORE = os.path.join(REPO, "phase5", "rtdl-revisiting-models", "result-doctor.phase4-before.yml")
#: The same manifest after UX1/UX2.
AFTER = os.path.join(PHASE4_DIR, "result-doctor.yml")

needs_phase4 = pytest.mark.skipif(not os.path.isfile(BEFORE), reason="Phase 4 pilot checkout not on this machine")

_MEMBER = "{name: a, path: runs/a/log.csv, column: acc, row: last"
_ID_EXPLICIT = "identity: {observed: {path: runs/a/log.csv, column: acc, row: last}}}"
_ID_SUGAR = "identity: {observed: {column: acc, row: last}}}"
MEMBER_EXPLICIT = f"      - {_MEMBER}, {_ID_EXPLICIT}\n"
MEMBER_INHERITED = f"      - {_MEMBER}, {_ID_SUGAR}\n"
BASE_MEMBER = "      - {name: a, path: runs/a/log.csv, column: acc, row: last}\n"


def _with(member_line: str) -> str:
    return BASE.replace(BASE_MEMBER, member_line)


def _load_in(tmp_path, name: str, text: str) -> str:
    """`load` into a sibling directory, so two bundles can be built without clobbering each other."""
    target = tmp_path / name
    target.mkdir(parents=True, exist_ok=True)
    return load(target, text, ART)


# ------------------------------------------------------------------ T1: identity sugar


def _identity_facts(bundle: Bundle) -> list[tuple[str, object, str, object]]:
    return sorted(
        (
            mid,
            member.run_ref.external_id.value,
            member.run_ref.external_id.grade.value,
            tuple((s.path, str(s.line), s.key, s.note) for s in member.run_ref.external_id.sources),
        )
        for mid, member in bundle.members.items()
    )


def test_an_identity_without_a_path_is_read_against_the_members_own_file(tmp_path) -> None:
    """UX1: the same fact stated once, lowered to the same bundle as when it is quoted."""
    explicit = bundle_from_manifest(load(tmp_path / "x", _with(MEMBER_EXPLICIT), ART))
    sugar = bundle_from_manifest(load(tmp_path / "y", _with(MEMBER_INHERITED), ART))
    assert _identity_facts(explicit) == _identity_facts(sugar)
    assert canonical_json(evaluate(explicit)) == canonical_json(evaluate(sugar))


def test_an_identity_sugar_never_upgrades_a_missing_identity(tmp_path) -> None:
    """Omitting `identity:` stays UNKNOWN; only an explicit door can be DIRECT."""
    bundle = bundle_from_manifest(load(tmp_path, BASE, ART))
    member = next(m for k, m in bundle.members.items() if k.endswith("/a"))
    assert member.run_ref.external_id.grade is Grade.UNKNOWN
    sugar = bundle_from_manifest(load(tmp_path / "z", _with(MEMBER_INHERITED), ART))
    other = next(m for k, m in sugar.members.items() if k.endswith("/a"))
    assert other.run_ref.external_id.grade is Grade.DIRECT


def test_an_identity_without_a_path_still_needs_a_member_path(tmp_path) -> None:
    """An inline-valued member has no file of its own, so there is nothing to inherit."""
    text = BASE.replace(
        "      - {name: b, value: 2.0}\n",
        "      - {name: b, value: 2.0, identity: {observed: {key: /id}}}\n",
    )
    assert raises(tmp_path, text) == "E_MISSING_FIELD"


# ------------------------------------------------------------------ T2 / T6: the real manifest


def _logical_lines(path: str) -> int:
    with open(path, encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip() and not line.strip().startswith("#"))


def _vector(path: str) -> dict[tuple[str, str], str]:
    return {(f.rule_id, f.target): f.status.value for f in audit_manifest(path)}


def _projection(path: str) -> list[dict[str, object]]:
    return [
        {
            "rule": f.rule_id,
            "target": f.target,
            "status": f.status.value,
            "measurements": json.dumps(f.measurements, sort_keys=True, default=str),
            "evidence": [[e.path, str(e.line), e.key, e.artifact_id, e.note] for e in f.evidence],
        }
        for f in audit_manifest(path)
    ]


@needs_phase4
def test_the_phase4_manifest_still_loads_and_still_judges_the_same_way() -> None:
    before = _vector(BEFORE)
    assert before == {
        ("RD001", "mlp-tuned/adult"): "PASS",
        ("RD001", "mlp-tuned/california_housing"): "PASS",
        ("RD002", "aggregation:agg:mlp-tuned/adult"): "PASS",
        ("RD002", "aggregation:agg:mlp-tuned/california_housing"): "PASS",
        ("RD003", "reported:mlp-tuned/california_housing"): "NOT_APPLICABLE",
        ("RD003", "selection:sel:adult-tuned-config"): "INCONCLUSIVE",
        ("RD003", "selection:sel:per-run-epoch"): "INCONCLUSIVE",
        ("RD004", "candidates:cand:adult-epochs"): "INCONCLUSIVE",
        ("RD004", "candidates:cand:adult-tuning-trials"): "INCONCLUSIVE",
        ("RD005", "mlp-tuned/adult"): "NOT_APPLICABLE",
        ("RD005", "mlp-tuned/california_housing"): "NOT_APPLICABLE",
        ("RD006", "reported:mlp-tuned/adult"): "PASS",
        ("RD006", "reported:mlp-tuned/california_housing"): "PASS",
        ("RD007", "rule:RD007"): "NOT_RUN",
        ("RD008", "quantity:metrics.test.score/adult"): "INCONCLUSIVE",
        ("RD008", "quantity:metrics.test.score/california_housing"): "INCONCLUSIVE",
    }


@needs_phase4
def test_the_simplified_manifest_is_shorter_and_says_the_same_things() -> None:
    assert _logical_lines(BEFORE) == 110
    assert _logical_lines(AFTER) <= 100
    assert _vector(AFTER) == _vector(BEFORE)
    before, after = _projection(BEFORE), _projection(AFTER)
    assert len(before) == len(after)
    differences = []
    for b, a in zip(before, after):
        if b == a:
            continue
        differences.append((b["rule"], b["target"]))
        #: the one permitted gap is an evidence note that the new form carries and the
        #: door-workaround form dropped; no grade, measurement or status may move.
        assert b["status"] == a["status"] and b["measurements"] == a["measurements"]
        assert [e[:4] for e in b["evidence"]] == [e[:4] for e in a["evidence"]]
        for be, ae in zip(b["evidence"], a["evidence"]):
            assert be[4] == ae[4] or (be[4] == "" and ae[4]), (be, ae)
    assert differences == [("RD004", "candidates:cand:adult-tuning-trials")]


# ------------------------------------------------------------------ T3: size companions


def _candidate_sizes(declared: str, surviving: str) -> str:
    return (
        BASE
        + "\ncandidate_sets:\n"
        + "  - id: k\n    kind: hyperparameter\n    universe: partial\n"
        + "    members: [runs/a/log.csv]\n"
        + f"    declared_size: {declared}\n    surviving_size: {surviving}\n"
    )


def test_a_size_can_carry_its_prose_as_a_companion(tmp_path) -> None:
    """UX2: {value, statement, note, supported_by} is one declaration, not two doors."""
    text = _candidate_sizes(
        '{value: 100, statement: "trials", note: "the config asks for 100", supported_by:'
        ' {path: paper/t.txt, text: "mean value"}}',
        '{value: 1, statement: "trials", note: "only one survives"}',
    )
    bundle = bundle_from_manifest(load(tmp_path, text, ART))
    cand = bundle.candidate_sets["cand:k"]
    assert cand.declared_size.value == 100 and cand.declared_size.grade is Grade.DECLARED
    assert cand.surviving_size.value == 1 and cand.surviving_size.grade is Grade.DECLARED
    assert cand.declared_size.note == "trials"


def test_the_old_size_doors_still_mean_the_same_thing(tmp_path) -> None:
    """Phase 4's workaround form keeps loading, with the same value, grade and note."""
    text = _candidate_sizes(
        '{value: 100, statement: "trials", declared: {value: 100, statement: "trials", by: "the config"},'
        ' supported_by: {path: paper/t.txt, text: "mean value"}}',
        '{value: 1, statement: "trials", declared: {value: 1, statement: "survives"}}',
    )
    bundle = bundle_from_manifest(load(tmp_path, text, ART))
    cand = bundle.candidate_sets["cand:k"]
    assert cand.declared_size.value == 100 and cand.declared_size.grade is Grade.DECLARED
    assert cand.surviving_size.value == 1 and cand.declared_size.note == "trials"


def test_a_size_that_declares_no_number_is_refused_with_the_shape_it_wants(tmp_path) -> None:
    """UX2 widens the accepted shape; it does not widen what counts as a size."""
    exact = {
        '{statement: "trials"}': "E_MISSING_FIELD",
        "{value: 100, bogus: x}": "E_UNKNOWN_KEY",
        '{value: "many", statement: t}': "E_NOT_A_NUMBER",
    }
    for form, code in exact.items():
        assert raises(tmp_path, _candidate_sizes(form, "{unknown: none}")) == code, form
    with pytest.raises(Exception) as excinfo:
        bundle_from_manifest(load(tmp_path, _candidate_sizes('{statement: "trials"}', "{unknown: none}"), ART))
    problem = str(excinfo.value)
    assert "candidate_sets[0]/declared_size" in problem and "value: <integer>" in problem


# ------------------------------------------------------------------ T4: G1, the whole-line trap


def test_a_line_locator_without_a_quoted_fragment_cannot_be_a_printed_cell(tmp_path) -> None:
    """G1: reading row `adult 0.852` whole would compare the label and FAIL a correct number."""
    line_only = BASE.replace(CELL_VALUE, "    value: {observed: {path: paper/t.txt, line: 3}}\n")
    assert raises(tmp_path, line_only) == "E_LOCATOR_TEXT"
    quoted = BASE.replace(CELL_VALUE, '    value: {observed: {path: paper/t.txt, line: 3, text: "mean value"}}\n')
    bundle = bundle_from_manifest(load(tmp_path, quoted, ART))
    assert bundle.reported_results["c/1"].value.value == "mean value"


def test_the_G1_refusal_names_the_field_the_problem_and_the_shape(tmp_path) -> None:
    line_only = BASE.replace(CELL_VALUE, "    value: {observed: {path: paper/t.txt, line: 3}}\n")
    with pytest.raises(Exception) as excinfo:
        bundle_from_manifest(load(tmp_path, line_only, ART))
    problem = str(excinfo.value)
    assert "reported_results[0]/value/observed" in problem
    assert 'text: "<the printed value>"' in problem
    assert "path: 'paper/t.txt', line: 3" in problem


# ------------------------------------------------------------------ T5: G2, the row-identity trap


def _two_cells(quantity_first: str, quantity_second: str, row_first: str = "x", row_second: str = "y") -> str:
    first = BASE.replace(
        "  - label: c/1\n",
        f"  - label: c/1\n    printed_in: {{artifact: paper/t.txt, table: T, row: {row_first}}}\n"
        f"    quantity: {quantity_first}\n",
    )
    second = f"""  - label: c/2
    printed_in: {{artifact: paper/t.txt, table: T, row: {row_second}}}
    quantity: {quantity_second}
    value: {{declared: {{value: "1.50", by: author}}}}
    aggregate: {{center: mean}}
    members:
      - {{name: b, path: runs/a/log.csv, column: acc, row: last}}
    member_rule: {{kind: enumerated, declared: {{value: enumerated, by: author}}}}
"""
    return first + second


def test_one_quantity_key_cannot_name_two_rows_of_one_table(tmp_path) -> None:
    """G2: RD008 groups by key alone, so a shared key compares two different rows."""
    assert raises(tmp_path, _two_cells("acc", "acc")) == "E_MISSING_FIELD"


def test_the_G2_refusal_says_which_two_rows_and_the_minimal_fix(tmp_path) -> None:
    with pytest.raises(Exception) as excinfo:
        bundle_from_manifest(load(tmp_path, _two_cells("acc", "acc"), ART))
    problem = str(excinfo.value)
    assert "reported_results[1]/quantity" in problem
    assert "row 'x' and row 'y'" in problem
    assert "acc/y" in problem


def test_row_scoped_quantities_load_and_a_cross_product_key_is_still_allowed(tmp_path) -> None:
    bundle = bundle_from_manifest(load(tmp_path, _two_cells("acc/x", "acc/y"), ART))
    assert bundle.reported_results["c/1"].locus.quantity_key == "acc/x"
    same_key_in_two_products = _two_cells("acc", "acc").replace(
        "  - label: c/2\n    printed_in: {artifact: paper/t.txt, table: T, row: y}\n",
        "  - label: c/2\n    printed_in: {artifact: ckpt/r1/val.json, table: T, row: y}\n",
    )
    other = bundle_from_manifest(load(tmp_path / "p", same_key_in_two_products, ART))
    assert len(other.reported_results) == 2
