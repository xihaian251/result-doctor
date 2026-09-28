"""The generic audit entry point: partial audit as a first-class result (Phase 2 §13).

RD001-RD008 are called unchanged. This layer only records the fourth thing a rule cannot
say for itself: that a whole class of object was never supplied. Insufficient evidence
stays the rules' business (`INCONCLUSIVE` / `NOT_APPLICABLE`); a missing class is here.

The legacy adapter path never calls this, so the two frozen archives keep emitting
byte-identical findings.
"""

from __future__ import annotations

from collections.abc import Iterable

from .bundle import Bundle
from .manifest import bundle_from_manifest
from .rules import NAME, QUESTION, RULE_IDS, evaluate
from .status import RuleFinding, RuleStatus

#: The object class each rule iterates. Empty means the rule has nothing to say.
DRIVING_CLASS = {
    "RD001": "reported_results",
    "RD002": "aggregations",
    "RD003": "selection_events",
    "RD004": "candidate_sets",
    "RD005": "reported_results",
    "RD006": "reported_results",
    "RD007": "comparison_sets",
    "RD008": "reported_results",
}


def not_run_findings(bundle: Bundle, findings: Iterable[RuleFinding]) -> list[RuleFinding]:
    """One NOT_RUN record per rule that was given nothing to judge.

    A rule emits zero findings exactly when it has zero targets. That is a different fact
    from "the evidence does not decide" (INCONCLUSIVE) and from "this target has no such
    dependency" (NOT_APPLICABLE), and unlike those two it is not something the rule can
    say for itself, because it says nothing at all.
    """
    ran = {f.rule_id for f in findings}
    out: list[RuleFinding] = []
    for rule_id in RULE_IDS:
        if rule_id in ran:
            continue
        cls = DRIVING_CLASS[rule_id]
        objects = getattr(bundle, cls)
        if objects:
            reason = (
                f"no target was supplied for this rule: {cls} is populated, but nothing in it carries the key "
                f"{rule_id} reads"
            )
        else:
            reason = f"no target of this class was supplied ({cls} is empty)"
        out.append(
            RuleFinding(
                rule_id,
                NAME[rule_id],
                f"rule:{rule_id}",
                RuleStatus.NOT_RUN,
                QUESTION[rule_id],
                {"driving_object_class": cls, "n_objects": len(objects), "n_targets": 0},
                (),
                reason,
            )
        )
    return out


def audit_bundle(bundle: Bundle, rule_ids: Iterable[str] | None = None) -> list[RuleFinding]:
    """The rules plus the entry layer's NOT_RUN records, in canonical order."""
    findings = evaluate(bundle, rule_ids)
    return sorted([*findings, *not_run_findings(bundle, findings)], key=lambda f: (f.rule_id, f.target))


def audit_manifest(path: str, rule_ids: Iterable[str] | None = None) -> list[RuleFinding]:
    """`result-doctor.yml` -> bundle -> RD001-RD008 -> partial audit.

    Raises `ManifestError` only for a manifest that cannot be read as a contract; a
    manifest that is thin on evidence audits successfully and says so in statuses.
    """
    return audit_bundle(bundle_from_manifest(path), rule_ids)
