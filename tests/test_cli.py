"""Phase 6: the CLI is a thin face on the audited pipeline.

Every case here compares the CLI against the Python API it wraps, because the claim being
tested is that the two cannot drift: same findings, same bytes, and the same exit code for a
completed audit no matter what the rules said. Nothing in this file adds a rule, a code, or a
discovery mechanism.
"""

from __future__ import annotations

import json
import os

import pytest
from test_generic_firewall import ART, BASE, CELL_VALUE, EXAMPLE_B, load

from result_doctor.audit import audit_manifest
from result_doctor.cli import EXIT_INPUT_ERROR, EXIT_OK, main
from result_doctor.status import RuleStatus, canonical_json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOT = os.path.join(REPO, "phase4", "rtdl-revisiting-models", "result-doctor.yml")

needs_pilot = pytest.mark.skipif(not os.path.isfile(PILOT), reason="Phase 4 pilot checkout not on this machine")

#: A printed cell quoted as a whole line: the G1 shape Phase 5 made an authoring refusal.
G1_SHAPE = "    value: {observed: {path: paper/t.txt, line: 3}}\n"
BROKEN = BASE.replace(CELL_VALUE, G1_SHAPE)

#: Frozen in the Phase 5 report section 7 and re-checked by test_phase5_ux.
PILOT_CENSUS = "PASS: 6\nFAIL: 0\nINCONCLUSIVE: 6\nNOT_APPLICABLE: 3\nNOT_RUN: 1"


def _blocks(stdout: str) -> tuple[list[str], list[str], str]:
    """Split the default output into finding lines, their reason lines, and the census."""
    head, _, tail = stdout.partition("\n")  # the header echo
    assert head.startswith("# result-doctor audit ")
    table, _, census = tail.strip("\n").rpartition("\n\n")
    lines = [line for line in table.split("\n") if line]
    findings = [line for line in lines if not line.startswith("        reason:")]
    reasons = [line for line in lines if line.startswith("        reason:")]
    return findings, reasons, census.strip("\n")


def _columns(line: str) -> tuple[str, str, str]:
    rule_id, status, target = line.split(None, 2)
    return rule_id, status, target


def test_the_help_text_names_the_statuses_and_says_the_tool_does_not_judge(capsys) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == EXIT_OK
    out = capsys.readouterr().out
    for status in ("PASS", "FAIL", "INCONCLUSIVE", "NOT_APPLICABLE", "NOT_RUN"):
        assert status in out
    assert "Exit codes" in out
    assert "reliable" in out  # the sentence saying it never concludes that

    with pytest.raises(SystemExit) as stop:
        main(["audit", "--help"])
    assert stop.value.code == EXIT_OK
    audit_help = capsys.readouterr().out
    assert "--json REPORT_JSON" in audit_help
    assert "it does not look for them" in audit_help


def test_a_completed_audit_exits_zero_even_though_a_rule_says_FAIL(capsys) -> None:
    """A FAIL is a finding about evidence, not a failed program (Phase 6 brief section 9)."""
    assert main(["audit", EXAMPLE_B]) == EXIT_OK
    findings, _reasons, census = _blocks(capsys.readouterr().out)
    assert [status for _rule, status, _target in map(_columns, findings)].count("FAIL") == 1
    assert census.split("\n")[1] == "FAIL: 1"


def test_the_table_lists_one_line_per_finding_in_rule_and_target_order(tmp_path, capsys) -> None:
    manifest = load(tmp_path, BASE, ART)
    assert main(["audit", manifest]) == EXIT_OK
    findings, reasons, census = _blocks(capsys.readouterr().out)
    api = audit_manifest(manifest)
    assert len(findings) == len(api)
    assert len(reasons) == sum(1 for finding in api if finding.reason)
    assert [_columns(line)[:2] for line in findings] == [(finding.rule_id, finding.status.value) for finding in api]
    assert [_columns(line)[2] for line in findings] == [finding.target for finding in api]
    assert census == "\n".join(
        f"{status.value}: {sum(1 for finding in api if finding.status is status)}" for status in RuleStatus
    )


def test_a_directory_argument_reads_the_one_fixed_file_name(tmp_path, capsys) -> None:
    load(tmp_path, BASE, ART)
    assert main(["audit", str(tmp_path)]) == EXIT_OK
    header, _ = capsys.readouterr().out.split("\n", 1)
    assert header.endswith(os.path.join(str(tmp_path), "result-doctor.yml").replace("\\", "/"))


def test_the_json_report_is_the_findings_the_api_returns(tmp_path, capsys) -> None:
    manifest = load(tmp_path, BASE, ART)
    report = tmp_path / "report.json"
    assert main(["audit", manifest, "--json", str(report)]) == EXIT_OK
    assert report.read_text(encoding="utf-8") == canonical_json(audit_manifest(manifest)) + "\n"
    assert isinstance(json.loads(report.read_text(encoding="utf-8")), list)


def test_the_json_report_is_byte_identical_when_the_audit_is_rerun(tmp_path, capsys) -> None:
    manifest = load(tmp_path, BASE, ART)
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    main(["audit", manifest, "--json", str(first)])
    main(["audit", manifest, "--json", str(second)])
    capsys.readouterr()
    assert first.read_bytes() == second.read_bytes()
    # No CR, so the canonical bytes are the same report on any platform, not just this one.
    assert b"\r" not in first.read_bytes()


def test_a_manifest_that_is_not_a_contract_stops_with_its_code_and_no_traceback(tmp_path, capsys) -> None:
    manifest = load(tmp_path, BROKEN, ART)
    assert main(["audit", manifest]) == EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("E_LOCATOR_TEXT at reported_results[0]/value/observed:")
    assert "the printed value" in captured.err
    assert "Traceback" not in captured.err


def test_a_missing_manifest_is_refused_with_a_code_not_a_traceback(tmp_path, capsys) -> None:
    assert main(["audit", str(tmp_path / "absent.yml")]) == EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert captured.err.startswith("E_ARTIFACT_MISSING at ")
    assert "Traceback" not in captured.err


@needs_pilot
def test_the_real_project_audit_over_the_cli_says_what_the_api_says(capsys, tmp_path) -> None:
    report = tmp_path / "pilot.json"
    assert main(["audit", PILOT, "--json", str(report)]) == EXIT_OK
    assert report.read_text(encoding="utf-8") == canonical_json(audit_manifest(PILOT)) + "\n"
    findings, _reasons, census = _blocks(capsys.readouterr().out)
    assert len(findings) == 16
    assert census == PILOT_CENSUS
    assert len(json.loads(report.read_text(encoding="utf-8"))) == 16
