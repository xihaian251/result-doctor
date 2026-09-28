"""RD001-RD008. Deterministic, evidence-shaped judgments only.

Each rule returns `RuleFinding`s keyed to a target id. There is no aggregation across
rules: no overall status, no score, no ranking (Phase 0 §8 / §15 discipline).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from .bundle import Bundle
from .compute import (
    apply_stage,
    center,
    declared_vs_observed_conflict,
    dispersion,
    render,
    stage_transforms,
    std,
)
from .evidence import Grade, SourceRef
from .schema import Aggregation, AppliedAt, ReportedResult, SelectionEvent, SpreadKind
from .status import RuleFinding, RuleStatus

QUESTION = {
    "RD001": "can the reported number be recomputed from the declared members and transforms?",
    "RD002": "is the aggregation membership enumerable, and are exclusions bindable?",
    "RD003": "is every selection criterion backed by direct evidence, and was the declared policy followed?",
    "RD004": "how far can the candidate set be recovered?",
    "RD005": "what is the published +/- and does it match the project's own wording?",
    "RD006": "is every step from raw metric to table cell enumerated?",
    "RD007": "does the cell's presentation depend on data outside the cell, and is that dependency recomputable?",
    "RD008": "does the same quantity agree across the products it appears in?",
}

NAME = {
    "RD001": "Reported-Value Recomputability",
    "RD002": "Aggregation Membership Derivability",
    "RD003": "Selection-Criterion Recoverability",
    "RD004": "Candidate-Set Recoverability",
    "RD005": "Spread-Semantics Consistency",
    "RD006": "Transformation-Chain Auditability",
    "RD007": "Presentation-Dependency Integrity",
    "RD008": "Cross-Artifact Consistency",
}


def _src(*objs: SourceRef | None) -> tuple[SourceRef, ...]:
    return tuple(s for s in objs if s is not None)


def _fmt_of(bundle: Bundle, rr: ReportedResult):
    """The rendering step is itself evidence; without it the string comparison is undefined."""
    for t in bundle.chain(rr.transformation_refs):
        if t.step.value == "format":
            return str(t.params.get("mode", "fixed")), int(cast("int", t.params.get("digits", 2)))
    return None, None


def _recompute(bundle: Bundle, rr: ReportedResult, agg: Aggregation) -> dict | None:
    """Apply the recorded chain stage by stage, then render. None if not computable."""
    members = bundle.included(agg)
    chain = bundle.chain(rr.transformation_refs)
    unknown = [m.member_id for m in members if not m.observed_value.is_known]
    if not members or unknown:
        return {"n_members": len(members), "unknown_member_values": sorted(unknown), "computable": False}
    member_chain = stage_transforms(chain, "member")
    values = [apply_stage(float(m.observed_value.value), member_chain) for m in members]
    c = center(values, agg.center)
    d = dispersion(values, agg.spread_form)
    c = apply_stage(c, stage_transforms(chain, "center"))
    d = apply_stage(d, stage_transforms(chain, "dispersion"))
    mode, digits = _fmt_of(bundle, rr)
    meas = {
        "n_members": len(members),
        "member_values": [round(v, 6) for v in values],
        "recomputed_center": c,
        "recomputed_dispersion": d,
        "computable": True,
    }
    if mode is None:
        meas["rendering_undeclared"] = True
        return meas
    meas["rendered_center"] = render(c, mode, digits)
    if agg.spread_form.kind is SpreadKind.NONE:
        meas["rendered_dispersion"] = ""
    else:
        meas["rendered_dispersion"] = render(d, mode, digits)
    return meas


def _identity_indeterminate(bundle: Bundle, agg: Aggregation) -> tuple[bool, str]:
    """FM1/FM2/FM3: a mismatch is only a FAIL once member identity is determined."""
    if agg.member_rule.kind.value == "undeclared":
        return True, "member rule is not declared in the artifacts"
    for m in bundle.included(agg):
        art = bundle.artifacts.get(m.artifact_ref)
        if art is not None and art.produced_by.grade is Grade.UNKNOWN:
            return True, f"producer of {art.path} is not recorded"
        if art is not None and art.required_columns:
            missing = [c for c in art.required_columns if c not in art.columns]
            if missing:
                return True, f"{art.path} lacks the column(s) the declared producer writes: {missing}"
        if m.run_ref.external_id.grade is Grade.UNKNOWN:
            return True, f"member {m.member_id} cannot be bound to an external run id"
    return False, ""


def _is_conditional(t) -> bool:
    return t.params.get("conditional") is True


# ---------------------------------------------------------------- RD001
def rd001(bundle: Bundle) -> list[RuleFinding]:
    out: list[RuleFinding] = []
    for rid in sorted(bundle.reported_results):
        rr = bundle.reported_results[rid]
        ev = _src(*rr.value.sources, *rr.spread.sources)
        if rr.aggregation_ref not in bundle.aggregations:
            na = bool(rr.not_aggregated_reason)
            out.append(
                RuleFinding(
                    "RD001",
                    NAME["RD001"],
                    rid,
                    RuleStatus.NOT_APPLICABLE if na else RuleStatus.INCONCLUSIVE,
                    QUESTION["RD001"],
                    {
                        "aggregation_ref": rr.aggregation_ref or "none",
                        "not_aggregated_reason": rr.not_aggregated_reason or "",
                    },
                    ev,
                    rr.not_aggregated_reason
                    or "no aggregation is referenced and no non-aggregation reason is recorded",
                )
            )
            continue
        agg = bundle.aggregations[rr.aggregation_ref]
        meas = _recompute(bundle, rr, agg)
        if meas is None or not meas["computable"]:
            out.append(
                RuleFinding(
                    "RD001",
                    NAME["RD001"],
                    rid,
                    RuleStatus.INCONCLUSIVE,
                    QUESTION["RD001"],
                    meas or {},
                    ev,
                    "at least one declared member has no observable value",
                )
            )
            continue
        if "rendering_undeclared" in meas:
            out.append(
                RuleFinding(
                    "RD001",
                    NAME["RD001"],
                    rid,
                    RuleStatus.INCONCLUSIVE,
                    QUESTION["RD001"],
                    meas,
                    ev,
                    "no rendering step is recorded, so the printed form cannot be compared",
                )
            )
            continue
        want_v = str(rr.value.value)
        want_s = str(rr.spread.value) if rr.spread.value not in (None, "", "N/A") else ""
        got_v, got_s = meas["rendered_center"], meas["rendered_dispersion"]
        match_v, match_s = got_v == want_v, (got_s == want_s if want_s else True)
        meas.update(
            {
                "reported_center": want_v,
                "reported_dispersion": want_s,
                "center_matches": match_v,
                "dispersion_matches": match_s,
            }
        )
        if match_v and match_s:
            status, reason = RuleStatus.PASS, "recomputed rendering equals the reported cell"
        else:
            indet, why = _identity_indeterminate(bundle, agg)
            if indet:
                status = RuleStatus.INCONCLUSIVE
                reason = f"mismatch, and member identity is not determined: {why}"
            else:
                status = RuleStatus.FAIL
                reason = "members, aggregation and transforms are all determined yet the cell differs"
        out.append(RuleFinding("RD001", NAME["RD001"], rid, status, QUESTION["RD001"], meas, ev, reason))
    return out


# ---------------------------------------------------------------- RD002
def rd002(bundle: Bundle) -> list[RuleFinding]:
    out: list[RuleFinding] = []
    for aid in sorted(bundle.aggregations):
        agg = bundle.aggregations[aid]
        members = bundle.members_of(agg)
        target = f"aggregation:{aid}"
        ev = _src(
            SourceRef(agg.member_rule.source, note="member rule"),
            *[x.listed.sources[0] for x in agg.exclusions if x.listed.sources],
        )
        if not members:
            out.append(
                RuleFinding(
                    "RD002",
                    NAME["RD002"],
                    target,
                    RuleStatus.INCONCLUSIVE,
                    QUESTION["RD002"],
                    {"n_members": 0},
                    ev,
                    "an aggregation is declared but no member record exists",
                )
            )
            continue
        if len(members) <= 1:
            out.append(
                RuleFinding(
                    "RD002",
                    NAME["RD002"],
                    target,
                    RuleStatus.NOT_APPLICABLE,
                    QUESTION["RD002"],
                    {"n_members": len(members)},
                    ev,
                    "single-member aggregation",
                )
            )
            continue
        anonymous = [m.member_id for m in members if m.run_ref.external_id.grade is Grade.UNKNOWN]
        missing = [m.member_id for m in members if not m.observed_value.is_known]
        unbound = [x.member_id for x in agg.exclusions if x.member_id not in bundle.members]
        listed = [x for x in agg.exclusions if x.listed.grade in (Grade.DIRECT, Grade.DERIVED)]
        unlisted = [x.member_id for x in agg.exclusions if x.listed.grade is Grade.UNKNOWN]
        gate_undeclared = agg.member_rule.kind is not None and agg.member_rule.kind.value == "undeclared"
        criterion_ok = all(x.criterion_recomputable for x in agg.exclusions) if agg.exclusions else None
        meas = {
            "n_members": len(members),
            "n_included": len(bundle.included(agg)),
            "n_exclusions": len(agg.exclusions),
            "n_exclusions_listed": len(listed),
            "n_exclusions_unlisted": len(unlisted),
            "n_exclusions_unbound_to_members": len(unbound),
            "n_members_anonymous": len(anonymous),
            "n_members_without_value": len(missing),
            "member_rule_kind": agg.member_rule.kind.value,
            "member_rule_grade": agg.member_rule.grade.value,
            "exclusion_criterion_recomputable": criterion_ok,
        }
        parts = []
        if anonymous:
            parts.append(f"{len(anonymous)} member(s) cannot be bound to an external run id")
        if unlisted:
            parts.append(f"{len(unlisted)} exclusion(s) have no list evidence")
        if criterion_ok is False:
            parts.append("an exclusion criterion is not recomputable")
        if gate_undeclared:
            parts.append("the member rule is not declared in the artifacts")
        if missing:
            parts.append(f"{len(missing)} member(s) have no observable value")
        if gate_undeclared and agg.exclusions:
            status, reason = RuleStatus.FAIL, "membership is set by an undeclared rule while exclusions exist"
        elif unbound:
            status, reason = RuleStatus.FAIL, "an exclusion cannot be bound to any member record"
        elif parts:
            status, reason = RuleStatus.INCONCLUSIVE, "; ".join(parts)
        else:
            status, reason = RuleStatus.PASS, "membership enumerable and every exclusion bindable"
        out.append(RuleFinding("RD002", NAME["RD002"], target, status, QUESTION["RD002"], meas, ev, reason))
    return out


# ---------------------------------------------------------------- RD003
def _deviations(se: SelectionEvent) -> tuple[list[dict], dict, bool]:
    """Champion-vs-promoted comparison at the declared precision (FM8).

    The third element says whether the comparison could be carried out at all, which is
    a different fact from "it was carried out and found no deviation".
    """
    extra: dict[str, object] = {}
    devs: list[dict] = []
    if not se.declared_policy.is_known or not se.candidate_values or not se.promoted_ref:
        if se.declared_policy.is_known and not se.candidate_values:
            extra["candidate_values_unrecorded"] = True
        if se.declared_policy.is_known and not se.promoted_ref:
            extra["promoted_ref_unrecorded"] = True
        return devs, extra, True
    vals = dict(se.candidate_values)
    if se.promoted_ref not in vals:
        return devs, {"promoted_not_in_candidates": True}, True
    minimizes = se.direction_is_minimizes
    champ = min(vals, key=lambda k: vals[k]) if minimizes else max(vals, key=lambda k: vals[k])
    best = vals[champ]
    promoted = vals[se.promoted_ref]
    gap = (promoted - best) if minimizes else (best - promoted)
    within = gap <= se.tie_tolerance
    extra.update(
        {
            "champion_ref": champ,
            "champion_value": round(best, 6),
            "promoted_value": round(promoted, 6),
            "gap": round(gap, 6),
            "gap_within_declared_precision": within,
        }
    )
    if not within and gap > 0:
        devs.append({"champion": champ, "promoted": se.promoted_ref, "gap": round(gap, 6)})
    return devs, extra, False


def rd003(bundle: Bundle) -> list[RuleFinding]:
    out: list[RuleFinding] = []
    for sid in sorted(bundle.selection_events):
        se = bundle.selection_events[sid]
        crit = se.criterion
        fields = {
            "metric": crit.metric,
            "split": crit.split,
            "direction": crit.direction,
            "scope": crit.scope,
            "tie_break": crit.tie_break,
            "timing": crit.timing,
        }
        grades = {k: v.grade.value for k, v in fields.items()}
        ev = _src(
            *[s for f in fields.values() for s in f.sources], *se.declared_policy.sources, *se.is_recorded.sources
        )
        devs, extra, indeterminate = _deviations(se)
        meas = {
            "kind": se.kind.value,
            "candidate_set_ref": se.candidate_set_ref,
            "criterion_values": {k: v.value for k, v in fields.items()},
            "criterion_grades": grades,
            "n_candidates": len(se.candidate_values),
            "is_recorded": se.is_recorded.value,
            "declared_policy_grade": se.declared_policy.grade.value,
            "tie_tolerance": se.tie_tolerance,
            "n_deviations": len(devs),
            "deviations": devs,
            **extra,
        }
        if devs:
            status = RuleStatus.FAIL
            reason = "the promoted member is not the champion under the declared policy, beyond the declared precision"
        elif se.declared_policy.grade is Grade.UNKNOWN:
            status = RuleStatus.INCONCLUSIVE
            reason = "no declared selection policy; the criterion is only implicit in code"
        elif indeterminate:
            status = RuleStatus.INCONCLUSIVE
            reason = (
                "the promoted member cannot be bound to a candidate record, so the declared policy cannot be "
                f"checked against it ({sorted(extra)})"
            )
        elif all(g == Grade.DIRECT.value for g in grades.values()):
            status = RuleStatus.PASS
            reason = "every criterion field is backed by direct evidence and no declared policy is contradicted"
        else:
            status = RuleStatus.INCONCLUSIVE
            reason = f"criterion fields not all direct: {grades}"
        out.append(RuleFinding("RD003", NAME["RD003"], f"selection:{sid}", status, QUESTION["RD003"], meas, ev, reason))
    for rid in sorted(bundle.reported_results):
        rr = bundle.reported_results[rid]
        if not rr.selection_refs:
            out.append(
                RuleFinding(
                    "RD003",
                    NAME["RD003"],
                    f"reported:{rid}",
                    RuleStatus.NOT_APPLICABLE,
                    QUESTION["RD003"],
                    {"selection_refs": []},
                    _src(*rr.value.sources),
                    "no selection step is recorded in the production of this cell",
                )
            )
    return out


# ---------------------------------------------------------------- RD004
def rd004(bundle: Bundle) -> list[RuleFinding]:
    out: list[RuleFinding] = []
    for cid in sorted(bundle.candidate_sets):
        cs = bundle.candidate_sets[cid]
        decl, surv = cs.declared_size, cs.surviving_size
        coll = cs.identity_collision
        meas = {
            "kind": cs.kind.value,
            "universe_status": cs.universe_status.value,
            "declared_size": decl.value,
            "declared_grade": decl.grade.value,
            "surviving_size": surv.value,
            "surviving_grade": surv.grade.value,
            "generation": cs.generation,
            "unobservable_sources": sorted({u.kind for u in cs.unobservable_sources}),
            "promotion_recorded": cs.promotion_evidence.value,
            "promotion_grade": cs.promotion_evidence.grade.value,
            "identity_key_type": coll.key_type if coll else "",
            "identity_collision_count": coll.collision_count if coll else 0,
        }
        ev = _src(*decl.sources, *surv.sources, *cs.promotion_evidence.sources)
        # The two sizes are only comparable when both are stated in the same unit; a
        # larger candidate universe than the surviving count is never a contradiction.
        comparable = decl.note == surv.note and decl.note != ""
        contradict = (
            comparable
            and decl.is_known
            and surv.is_known
            and isinstance(decl.value, int)
            and isinstance(surv.value, int)
            and surv.value > decl.value
        )
        meas["sizes_stated_in_same_unit"] = comparable
        if contradict:
            status = RuleStatus.FAIL
            reason = (
                "two declarations of the same candidate set in the same unit contradict each other: "
                f"{decl.value} declared vs {surv.value} surviving"
            )
        elif coll and coll.collision_count:
            status = RuleStatus.INCONCLUSIVE
            reason = (
                f"{coll.collision_count} identity key(s) of type {coll.key_type} are reused across search "
                "generations; declared and surviving sizes are both reported, and no judgment is made here about "
                "what relationship the two generations have"
            )
        elif cs.universe_status.value == "RECOVERED":
            status = RuleStatus.PASS
            reason = "candidate set is explicit in the artifacts and consistent with the surviving products"
        elif cs.universe_status.value == "UNRECOVERABLE":
            status = RuleStatus.INCONCLUSIVE
            reason = (
                "the candidate universe is affirmatively unrecoverable, not merely unfound: "
                + (", ".join(sorted({u.kind for u in cs.unobservable_sources})) or "no search product exists")
                + "; this is never downgraded to a singleton candidate set"
            )
        else:
            status = RuleStatus.INCONCLUSIVE
            reason = (
                f"candidate universe recoverability is {cs.universe_status.value}; this is never inferred from the "
                "count of surviving artifacts"
            )
        out.append(
            RuleFinding("RD004", NAME["RD004"], f"candidates:{cid}", status, QUESTION["RD004"], meas, ev, reason)
        )
    return out


# ---------------------------------------------------------------- RD005
#: (ddof, multiplier kind) for each formula family Phase 0 observed in the wild.
_FAMILIES = {
    "std_ddof0": (0, None),
    "std_ddof1": (1, None),
    "sem_ddof0": (0, "sem"),
    "sem_ddof1": (1, "sem"),
    "k_sem_ddof0_k3": (0, "k_sem"),
    "k_sem_ddof1_k3": (1, "k_sem"),
}


def rd005(bundle: Bundle) -> list[RuleFinding]:
    out: list[RuleFinding] = []
    for rid in sorted(bundle.reported_results):
        rr = bundle.reported_results[rid]
        if rr.spread_form.kind is SpreadKind.NONE or rr.spread.value in (None, "", "N/A"):
            out.append(
                RuleFinding(
                    "RD005",
                    NAME["RD005"],
                    rid,
                    RuleStatus.NOT_APPLICABLE,
                    QUESTION["RD005"],
                    {"spread": rr.spread.value},
                    _src(*rr.spread.sources),
                    "the cell carries no dispersion",
                )
            )
            continue
        agg = bundle.aggregations.get(rr.aggregation_ref)
        if agg is None or not bundle.all_member_values_known(agg):
            out.append(
                RuleFinding(
                    "RD005",
                    NAME["RD005"],
                    rid,
                    RuleStatus.INCONCLUSIVE,
                    QUESTION["RD005"],
                    {"aggregation_ref": rr.aggregation_ref or "none"},
                    _src(*rr.spread.sources),
                    "member values are unavailable, so no formula family can be tested",
                )
            )
            continue
        chain = bundle.chain(rr.transformation_refs)
        member_chain = stage_transforms(chain, "member")
        values = [apply_stage(float(m.observed_value.value), member_chain) for m in bundle.included(agg)]
        n = len(values)
        mode, digits = _fmt_of(bundle, rr)
        digits = 2 if digits is None else digits
        rendered = {}
        for name, (ddof, kind) in _FAMILIES.items():
            s = std(values, ddof)
            v = s if kind is None else (s / (n**0.5) if kind == "sem" else s * 3.0 / (n**0.5))
            rendered[name] = render(v, mode or "fixed", digits)
        matches = sorted([k for k, v in rendered.items() if v == str(rr.spread.value)])
        label = rr.spread_label
        form_label = f"{rr.spread_form.kind.value}(k={rr.spread_form.k},ddof={rr.spread_form.ddof},n={n})"
        meas = {
            "reported_spread": str(rr.spread.value),
            "formula_family_renderings": rendered,
            "families_matching_published_spread": matches,
            "declared_form": form_label,
            "spread_label": label.value,
            "spread_label_grade": label.grade.value,
            "n": n,
            "families_coincide_at_this_n": n == 1,
        }
        if label.grade is Grade.UNKNOWN or label.value in (None, ""):
            status, reason = (
                RuleStatus.INCONCLUSIVE,
                ("no wording declares what the +/- is; the reproducing family is recorded but not judged"),
            )
        elif not matches:
            status, reason = RuleStatus.FAIL, "no formula family reproduces the published dispersion"
        else:
            lab = str(label.value).lower()
            says_se = "standard error" in lab or lab.strip().startswith("se ") or " s.e" in lab
            says_std = ("standard deviation" in lab) or lab.strip() in ("std", "stdev", "standard dev")
            formula_is_se = rr.spread_form.kind.value in ("sem", "k_sem")
            if n == 1:
                status, reason = (
                    RuleStatus.INCONCLUSIVE,
                    (
                        "with a single member the std / SE / k·SE families coincide numerically, so agreement between "
                        "the wording and a reproducing family cannot be established"
                    ),
                )
            elif says_se and says_std:
                status, reason = RuleStatus.INCONCLUSIVE, f"the wording uses both families: {label.value!r}"
            elif says_se and formula_is_se:
                status, reason = RuleStatus.PASS, "wording and the formula family that reproduces the value agree"
            elif says_se and not formula_is_se:
                status, reason = (
                    RuleStatus.FAIL,
                    (
                        "the wording claims a standard error while the published dispersion is reproduced by a plain "
                        "standard deviation family"
                    ),
                )
            elif says_std and not formula_is_se:
                status, reason = RuleStatus.PASS, "wording and the formula family that reproduces the value agree"
            elif says_std and formula_is_se:
                status, reason = (
                    RuleStatus.FAIL,
                    (
                        "the wording claims a standard deviation while the published dispersion is reproduced by a "
                        "standard-error family"
                    ),
                )
            else:
                status, reason = (
                    RuleStatus.INCONCLUSIVE,
                    (f"wording {label.value!r} is not classifiable against {form_label}"),
                )
        out.append(
            RuleFinding(
                "RD005",
                NAME["RD005"],
                rid,
                status,
                QUESTION["RD005"],
                meas,
                _src(*rr.spread.sources, *label.sources),
                reason,
            )
        )
    return out


# ---------------------------------------------------------------- RD006
def rd006(bundle: Bundle) -> list[RuleFinding]:
    out: list[RuleFinding] = []
    for rid in sorted(bundle.reported_results):
        rr = bundle.reported_results[rid]
        chain = bundle.chain(rr.transformation_refs)
        target = f"reported:{rid}"
        ev = _src(*[s for t in chain for s in t.sources])
        unresolved = [
            t.transform_id
            for t in chain
            if t.applied_at is AppliedAt.UNKNOWN or (_is_conditional(t) and t.condition.grade is Grade.UNKNOWN)
        ]
        conflicts = [t.transform_id for t in chain if declared_vs_observed_conflict(t)]
        ungraded = [t.transform_id for t in chain if t.grade is Grade.UNKNOWN]
        missing_refs = [r for r in rr.transformation_refs if r not in bundle.transformations]
        meas = {
            "chain": [f"{t.step.value}@{t.applied_at.value}" for t in chain],
            "n_steps": len(chain),
            "refs_not_in_bundle": missing_refs,
            "declared_vs_observed_conflicts": conflicts,
            "branch_conditions_unresolved": unresolved,
            "steps_without_evidence_grade": ungraded,
        }
        if conflicts:
            status, reason = RuleStatus.FAIL, f"a declared quantity is replaced by a different one: {conflicts}"
        elif missing_refs:
            status, reason = RuleStatus.INCONCLUSIVE, f"referenced transformations are absent: {missing_refs}"
        elif rr.aggregation_ref not in bundle.aggregations:
            status, reason = (
                RuleStatus.NOT_APPLICABLE,
                (rr.not_aggregated_reason or "no aggregation and no stated non-aggregation reason"),
            )
        elif unresolved:
            status, reason = (
                RuleStatus.INCONCLUSIVE,
                (f"which branch produced this cell is not recoverable: {unresolved}"),
            )
        elif not chain:
            status, reason = (
                RuleStatus.INCONCLUSIVE,
                ("no transformation is recorded; identity-with-raw would need evidence, not a default"),
            )
        elif all(t.step.value == "identity" for t in chain) and not unresolved:
            status, reason = (
                RuleStatus.NOT_APPLICABLE,
                ("the recorded chain asserts raw value == reported value, and that assertion is itself evidenced"),
            )
        else:
            res = _recompute(bundle, rr, bundle.aggregations[rr.aggregation_ref])
            if res is None or not res["computable"] or "rendering_undeclared" in res:
                status, reason = RuleStatus.INCONCLUSIVE, "the chain cannot be evaluated to a printed form"
            else:
                meas.update(
                    {
                        "rendered_center": res["rendered_center"],
                        "reported_center": str(rr.value.value),
                    }
                )
                if res.get("rendered_center") == str(rr.value.value):
                    status, reason = RuleStatus.PASS, "the chain applied step by step yields the printed cell"
                else:
                    status, reason = (
                        RuleStatus.INCONCLUSIVE,
                        ("the recorded chain does not yield the printed cell; an unrecorded step cannot be excluded"),
                    )
        out.append(RuleFinding("RD006", NAME["RD006"], target, status, QUESTION["RD006"], meas, ev, reason))
    return out


# ---------------------------------------------------------------- RD007
def rd007(bundle: Bundle) -> list[RuleFinding]:
    out: list[RuleFinding] = []
    for cid in sorted(bundle.comparison_sets):
        cs = bundle.comparison_sets[cid]
        target = f"comparison:{cid}"
        rule = cs.presentation_rule
        if rule is None:
            out.append(
                RuleFinding(
                    "RD007",
                    NAME["RD007"],
                    target,
                    RuleStatus.NOT_APPLICABLE,
                    QUESTION["RD007"],
                    {"n_members": len(cs.members)},
                    (),
                    "this comparison set carries no presentation mark",
                )
            )
            continue
        ev = _src(
            SourceRef(rule.source, note="presentation rule"), *cs.external_origin.sources, *cs.observed_marks.sources
        )
        peers = [(r, bundle.reported_results.get(r)) for r, _ in cs.members]
        known = [
            (r, rr) for r, rr in peers if rr is not None and rr.value.is_known and rr.spread.value not in (None, "")
        ]
        recomputable = len(known) == len(cs.members) and len(cs.members) > 1
        observed = tuple(cs.observed_marks.value or ())
        meas = {
            "n_members": len(cs.members),
            "expression": rule.expression,
            "operator": rule.operator,
            "symmetric_operator": rule.symmetric,
            "k_factor": rule.k_factor,
            "cell_value_depends_on_peers": True,
            "peer_values_recoverable": recomputable,
            "marks_recovered_from": cs.observed_marks.grade.value,
            "observed_marks": sorted(observed),
            "recomputed_marks": sorted(cs.recomputed_marks),
            "external_origin_grade": cs.external_origin.grade.value,
        }
        if not recomputable:
            status, reason = (
                RuleStatus.INCONCLUSIVE,
                ("not every peer value of this comparison set is recoverable, so the mark cannot be recomputed"),
            )
        elif not cs.observed_marks.is_known:
            status, reason = (
                RuleStatus.INCONCLUSIVE,
                (
                    "the rule and the peer values are recovered, but the marks actually shown in the product are not; "
                    "the recomputed set is reported without a judgment"
                ),
            )
        elif not observed and not cs.recomputed_marks:
            status, reason = (
                RuleStatus.PASS,
                ("no member qualifies for a mark under the recovered rule, and none is shown"),
            )
        elif set(observed) == set(cs.recomputed_marks):
            status, reason = RuleStatus.PASS, "the recomputed mark set equals the marks shown"
        elif not rule.symmetric:
            status, reason = (
                RuleStatus.INCONCLUSIVE,
                (
                    "the recovered rule's comparison operators are not symmetric, so the boundary case has two "
                    "readings; the discrepancy is not attributed"
                ),
            )
        else:
            status, reason = RuleStatus.FAIL, "the recovered presentation rule disagrees with the marks shown"
        out.append(RuleFinding("RD007", NAME["RD007"], target, status, QUESTION["RD007"], meas, ev, reason))
    return out


# ---------------------------------------------------------------- RD008
def rd008(bundle: Bundle) -> list[RuleFinding]:
    out: list[RuleFinding] = []
    groups: dict[str, list[ReportedResult]] = {}
    for rid in sorted(bundle.reported_results):
        key = bundle.reported_results[rid].locus.quantity_key
        if key:
            groups.setdefault(key, []).append(bundle.reported_results[rid])
    for key in sorted(groups):
        rrs = groups[key]
        target = f"quantity:{key}"
        loci = {
            f"{rr.locus.artifact}:{rr.locus.table}:{rr.locus.row}:{rr.locus.column}": (
                f"{rr.value.value}±{rr.spread.value}"
            )
            for rr in rrs
        }
        ev = _src(*[s for rr in rrs for s in rr.value.sources])
        if len(rrs) < 2:
            out.append(
                RuleFinding(
                    "RD008",
                    NAME["RD008"],
                    target,
                    RuleStatus.INCONCLUSIVE,
                    QUESTION["RD008"],
                    {"loci": loci, "n_loci": len(rrs)},
                    ev,
                    "the quantity is printed in a single product, so there is nothing to cross-check",
                )
            )
            continue
        agree = len(set(loci.values())) == 1
        meas = {
            "loci": loci,
            "n_loci": len(rrs),
            "identical": agree,
            "values": sorted({str(rr.value.value) for rr in rrs}),
            "spreads": sorted({str(rr.spread.value) for rr in rrs}),
        }
        if agree:
            status, reason = RuleStatus.PASS, "every locus shows the same value"
        else:
            status = RuleStatus.FAIL
            reason = (
                "the same quantity is printed with different values in two products; which one is intended, "
                "and why they differ, is not determined here"
            )
        out.append(RuleFinding("RD008", NAME["RD008"], target, status, QUESTION["RD008"], meas, ev, reason))
    for path in sorted(bundle.artifacts):
        art = bundle.artifacts[path]
        if not art.required_columns:
            continue
        missing = [c for c in art.required_columns if c not in art.columns]
        claimed = sorted({a.path for a in bundle.artifacts.values() if a.path == path and a is not art})
        meas = {
            "columns": list(art.columns),
            "required_by_declared_producer": list(art.required_columns),
            "missing": missing,
            "other_artifacts_claiming_path": claimed,
            "superseded_from": list(art.superseded_from),
            "superseded_by": list(art.superseded_by),
            "producer_grade": art.produced_by.grade.value,
        }
        if missing:
            out.append(
                RuleFinding(
                    "RD008",
                    NAME["RD008"],
                    f"artifact:{path}",
                    RuleStatus.FAIL,
                    QUESTION["RD008"],
                    meas,
                    _src(SourceRef(art.produced_by.script or art.path, note="declared producer")),
                    "a declared producer writes these column(s) here and the surviving file does not carry "
                    "them; the surviving file is therefore not the artifact that produced the cell",
                )
            )
        else:
            out.append(
                RuleFinding(
                    "RD008",
                    NAME["RD008"],
                    f"artifact:{path}",
                    RuleStatus.PASS,
                    QUESTION["RD008"],
                    meas,
                    _src(SourceRef(art.produced_by.script or art.path, note="declared producer")),
                    "the surviving file carries every column the declared producer writes",
                )
            )
    return out


RULES = (rd001, rd002, rd003, rd004, rd005, rd006, rd007, rd008)
RULE_IDS = tuple(f"RD{i:03d}" for i in range(1, 9))


def evaluate(bundle: Bundle, rule_ids: Iterable[str] | None = None) -> list[RuleFinding]:
    ids = tuple(rule_ids) if rule_ids else RULE_IDS
    findings: list[RuleFinding] = []
    for rule_id, fn in zip(RULE_IDS, RULES):
        if rule_id in ids:
            findings.extend(fn(bundle))
    return sorted([f for f in findings if f.rule_id in ids], key=lambda f: (f.rule_id, f.target))
