"""The command-line face of Result Doctor (Phase 6).

`audit` is deliberately thin: it calls the same `audit_manifest` the acceptance tests call
and prints the findings that come back. Nothing here judges anything. There is no score and
no overall verdict; the closing status census counts findings and says nothing about whether
they are good.

Exit codes keep the two kinds of "bad" apart:

```text
0  the audit ran, whatever the rules said
2  the manifest is not a readable contract (or the command line itself was wrong)
1  the tool failed unexpectedly
```

A rule saying FAIL or INCONCLUSIVE exits 0. Inference is not a crash, and a finding is not a
broken program.

Two authoring facts the help text repeats, because they are what a new user asks first:

* A directory argument resolves to the one fixed name `result-doctor.yml` inside it. The CLI
  never searches for a manifest and never picks one up from a file or directory name.
* Artifact paths inside a manifest are relative to the header's `root:`, which resolves
  relative to the directory holding the manifest.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .audit import audit_manifest
from .manifest import ManifestError
from .status import RuleFinding, RuleStatus, canonical_json

#: The only file name a directory argument resolves to. A convention, not a discovery rule.
MANIFEST_NAME = "result-doctor.yml"

EXIT_OK = 0
EXIT_TOOL_ERROR = 1
EXIT_INPUT_ERROR = 2

STATUS_ORDER = (
    RuleStatus.PASS,
    RuleStatus.FAIL,
    RuleStatus.INCONCLUSIVE,
    RuleStatus.NOT_APPLICABLE,
    RuleStatus.NOT_RUN,
)


def _force_utf8_stdout() -> None:
    """Keep output byte-stable when stdout is redirected.

    On Windows a redirected stream gets the locale codepage (cp936 here), and a finding that
    quotes an evidence path or a printed value can then raise on encode. Console output is
    already UTF-8, so this only takes effect for files and pipes.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    encoding = str(getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "")
    if reconfigure is not None and encoding not in ("utf8", "utf16", "utf32"):
        reconfigure(encoding="utf-8")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def render_text(findings: Sequence[RuleFinding]) -> str:
    """One line per finding in `(rule_id, target)` order, then the status census.

    A long reason stays on its own indented line rather than being truncated: shortening an
    evidence sentence silently would be a scientific loss, while the table stays scannable
    because rule, status and target sit in fixed columns.
    """
    ordered = sorted(findings, key=lambda f: (f.rule_id, f.target))
    lines: list[str] = []
    for finding in ordered:
        lines.append(f"{finding.rule_id:<6}  {finding.status.value:<14}  {finding.target}")
        if finding.reason:
            lines.append(f"        reason: {_one_line(finding.reason)}")
    counts = {status: sum(1 for f in ordered if f.status is status) for status in STATUS_ORDER}
    lines.append("")
    lines.extend(f"{status.value}: {counts[status]}" for status in STATUS_ORDER)
    return "\n".join(lines) + "\n"


def manifest_path(target: str) -> str:
    """A directory means `<dir>/result-doctor.yml`; anything else is used as given."""
    path = Path(target)
    return str(path / MANIFEST_NAME) if path.is_dir() else target


def write_json(findings: Sequence[RuleFinding], destination: str) -> None:
    """The findings as canonical JSON -- the same bytes `canonical_json` gives the API tests.

    `newline="\\n"` because the default text mode would write CRLF on Windows, making the
    "byte-identical report" promise depend on the platform the audit happened to run on.
    """
    Path(destination).write_text(canonical_json(list(findings)) + "\n", encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="result-doctor",
        description="Audit how the runs behind a reported ML result produced the reported number.",
        epilog=(
            "Rule statuses are exactly PASS | FAIL | INCONCLUSIVE | NOT_APPLICABLE | NOT_RUN.\n"
            "  PASS            the evidence the manifest supplies decides this target in favour of the report\n"
            "  FAIL            one rule found an inconsistency in the evidence for this target"
            " - not a failed experiment or paper\n"
            "  INCONCLUSIVE    the evidence on file is insufficient to decide\n"
            "  NOT_APPLICABLE  this target has no such dependency to check\n"
            "  NOT_RUN         no target of the class this rule reads was supplied\n"
            "INCONCLUSIVE and NOT_RUN record missing evidence, not a found problem. This tool never"
            " concludes that a paper is reliable, unreliable, or cherry-picked.\n\n"
            "Exit codes: 0 = the audit ran, whatever it found; 2 = the manifest is not a readable"
            " contract; 1 = the tool failed unexpectedly."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"result-doctor {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    audit = commands.add_parser(
        "audit",
        help="load a manifest, run RD001-RD008, print the findings",
        description=(
            "Read a `result-doctor.yml` and print one line per finding. The manifest is evidence"
            " only: the tool reads the artifacts it quotes, it does not look for them."
        ),
        epilog=(
            "Give it the manifest itself, or a project directory containing `result-doctor.yml`.\n"
            "If a manifest cannot be read as a contract the command stops with exit 2 and prints"
            " `{code} at {where}: {problem}` unchanged - the code, the field path, and the fix."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    audit.add_argument("path", help="a result-doctor.yml, or a directory containing one")
    audit.add_argument(
        "--json",
        metavar="REPORT_JSON",
        help="also write the full findings, as canonical JSON, to this file",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _force_utf8_stdout()
    args = build_parser().parse_args(argv)
    manifest = manifest_path(args.path)
    try:
        findings = audit_manifest(manifest)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INPUT_ERROR
    print(f"# result-doctor audit {Path(manifest).as_posix()}")
    sys.stdout.write(render_text(findings))
    if args.json:
        write_json(findings, args.json)
    return EXIT_OK
