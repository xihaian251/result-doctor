"""S1-S5 of Phase 0 §15.1: five hand-computable bundles with pre-written answer vectors.

Each fixture isolates one semantic boundary that the real archives also show, and each
expected vector covers all eight rules, including the NOT_APPLICABLE and UNKNOWN cases.
Every number below is computable by hand: the member sets are 2-3 integers.
"""

from __future__ import annotations

from result_doctor.bundle import Bundle
from result_doctor.evidence import Grade, declared, direct, unknown_field
from result_doctor.schema import (
    Aggregation,
    AggregationMember,
    AppliedAt,
    CandidateKind,
    CandidateSet,
    ComparisonSet,
    IdentityCollision,
    Locus,
    MemberRule,
    MemberRuleKind,
    ObservationSelector,
    PresentationRule,
    ProducedBy,
    ReportedResult,
    ResultArtifact,
    RunRef,
    SelectionCriterion,
    SelectionEvent,
    SelectionKind,
    SelectorKind,
    SpreadForm,
    SpreadKind,
    Transformation,
    TransformStep,
    UnobservableSource,
)
from result_doctor.status import UniverseStatus


def _fmt(bundle: Bundle, transform_id: str = "t:fmt", mode: str = "fixed") -> str:
    bundle.add(
        Transformation(
            transform_id=transform_id,
            step=TransformStep.FORMAT,
            applied_at=AppliedAt.CODE,
            target="cell",
            params={"stage": "render", "mode": mode, "digits": 2},
            condition=declared("always", "s/collect.py", 10, key="render"),
        )
    )
    return transform_id


def _members(
    bundle: Bundle, agg_id: str, values: dict[str, float], anonymous: bool = False, artifact: str = ""
) -> list[str]:
    ids = []
    for run, v in values.items():
        mid = f"{agg_id}/{run}"
        ids.append(mid)
        bundle.add(
            AggregationMember(
                member_id=mid,
                run_ref=RunRef(
                    project="synthetic",
                    family_key=agg_id,
                    run_name=run,
                    artifact_ref=artifact,
                    external_id=(
                        unknown_field("index <-> id binding absent")
                        if anonymous
                        else direct(f"id-{run}", "s/collect.py", 4)
                    ),
                ),
                selector=ObservationSelector(
                    kind=SelectorKind.LAST_ROW, column="metric", grade=Grade.DIRECT, source="s/collect.py:6"
                ),
                observed_value=direct(v, f"{artifact or 's/artifact'}/{run}.csv", key="metric"),
                artifact_ref=artifact,
            )
        )
    return ids


def _agg(
    bundle: Bundle,
    agg_id: str,
    member_ids: tuple[str, ...],
    form: SpreadForm,
    rule_kind: MemberRuleKind = MemberRuleKind.ENUMERATED,
) -> None:
    bundle.add(
        Aggregation(
            aggregation_id=agg_id,
            center="mean",
            dispersion_expression="std over the members",
            spread_form=form,
            member_rule=MemberRule(
                kind=rule_kind, expression="the listed members", grade=Grade.DIRECT, source="s/collect.py:8"
            ),
            member_ids=member_ids,
        )
    )


def _cell(
    bundle: Bundle,
    rid: str,
    value: str,
    spread: str,
    agg_id: str,
    form: SpreadForm,
    label,
    refs: tuple[str, ...],
    artifact: str = "",
    quantity: str | None = None,
    selection: tuple[str, ...] = (),
    comparison: str = "",
) -> None:
    bundle.add(
        ReportedResult(
            rid=rid,
            locus=Locus(
                artifact=artifact or "paper Table 1",
                table="Table 1",
                row=rid,
                column="m",
                quoted_text=f"{value} \u00b1{spread}",
                quantity_key=rid if quantity is None else quantity,
            ),
            metric_name=direct("metric", "s/collect.py", 5),
            value=direct(value, "paper Table 1", key=rid),
            spread=direct(spread, "paper Table 1", key=rid),
            spread_form=form,
            aggregation_ref=agg_id,
            transformation_refs=refs,
            selection_refs=selection,
            comparison_set_ref=comparison,
            spread_label=label,
        )
    )


_STD = SpreadForm(SpreadKind.STD, k=1.0, ddof=0, n=3, grade=Grade.DIRECT)
_K3 = SpreadForm(SpreadKind.K_SEM, k=3.0, ddof=0, n=3, grade=Grade.DIRECT)
_STD2 = SpreadForm(SpreadKind.STD, k=1.0, ddof=0, n=2, grade=Grade.DIRECT)


# --------------------------------------------------------------------- S1 clean chain
def s1_clean_chain() -> Bundle:
    """3 runs, explicit members, plain std: every link is present and every rule passes."""
    b = Bundle(project="S1")
    fmt = _fmt(b)
    b.add(
        ResultArtifact(
            path="s1/runs",
            columns=("metric",),
            produced_by=ProducedBy(
                script="s1/collect.py", call_site="main", invocation_args="--out s1/runs", grade=Grade.DIRECT
            ),
        )
    )
    ids = tuple(_members(b, "agg:s1/A", {"r1": 10.0, "r2": 12.0, "r3": 14.0}, artifact="s1/runs"))
    _agg(b, "agg:s1/A", ids, _STD)
    _agg(b, "agg:s1/A@README", ids, _STD)
    ids_b = tuple(_members(b, "agg:s1/B", {"r1": 10.5, "r2": 11.5}, artifact="s1/runs"))
    _agg(b, "agg:s1/B", ids_b, _STD2)
    b.add(
        SelectionEvent(
            selection_id="sel:s1",
            kind=SelectionKind.CHECKPOINT,
            candidate_set_ref="candidates:s1",
            criterion=SelectionCriterion(
                metric=direct("metric", "s/train.py", 20),
                split=direct("validation", "s/train.py", 21),
                direction=direct("minimize", "s/train.py", 22),
                scope=direct("within one run", "s/train.py", 23),
                tie_break=direct("strict <, earliest wins", "s/train.py", 22),
                timing=direct("in training", "s/train.py", 23),
            ),
            candidate_values=(("e1", 2.0), ("e2", 1.5)),
            promoted_ref="e2",
            declared_policy=declared("report the best checkpoint", "README.md", 8),
            is_recorded=direct(True, "s/train.py", 24, key="saved"),
        )
    )
    b.add(
        CandidateSet(
            candidate_set_id="candidates:s1",
            kind=CandidateKind.CHECKPOINT,
            universe_status=UniverseStatus.RECOVERED,
            declared_size=direct(2, "s1/runs/r1.csv", key="rows", note="evaluations"),
            surviving_size=direct(2, "s1/runs/r1.csv", key="rows", note="evaluations"),
            promotion_evidence=direct(True, "s/train.py", 24, note="saved"),
        )
    )
    std_label = declared("standard deviation", "README.md", 6)
    _cell(
        b,
        "s1/A",
        "12.00",
        "1.63",
        "agg:s1/A",
        _STD,
        std_label,
        (fmt,),
        artifact="paper Table 1",
        selection=("sel:s1",),
        comparison="cmp:s1",
    )
    _cell(
        b,
        "s1/A@README",
        "12.00",
        "1.63",
        "agg:s1/A@README",
        _STD,
        std_label,
        (fmt,),
        artifact="README.md",
        quantity="s1/A",
        comparison="cmp:s1",
    )
    _cell(
        b, "s1/B", "11.00", "0.50", "agg:s1/B", _STD2, std_label, (fmt,), artifact="paper Table 1", comparison="cmp:s1"
    )
    b.add(
        ComparisonSet(
            comparison_set_id="cmp:s1",
            members=(("s1/A", "A"), ("s1/B", "B")),
            external_origin=direct("both members are this project's own", "README.md", 7),
            presentation_rule=PresentationRule(
                expression="bold the smaller mean", operator="<", symmetric=True, source="s/collect.py:12"
            ),
            observed_marks=direct(("s1/B",), "paper Table 1", note="the printed bold"),
            recomputed_marks=("s1/B",),
        )
    )
    return b


# ----------------------------------------------------------------- S2 identity mismatch
def s2_member_identity_mismatch() -> Bundle:
    """FM1/FM2: the surviving artifact cannot be shown to be the one that made the cell."""
    b = Bundle(project="S2")
    fmt = _fmt(b)
    b.add(
        ResultArtifact(
            path="s2/runs",
            columns=("metric",),
            produced_by=ProducedBy(
                script="s2/fetch.py",
                call_site="two calls write this directory",
                invocation_args="the matching call is commented out at HEAD",
                grade=Grade.UNKNOWN,
            ),
            required_columns=("extra_metric",),
            note="the surviving file lacks the column the producer writes",
        )
    )
    ids = tuple(_members(b, "agg:s2/A", {"r1": 10.0, "r2": 12.0, "r3": 14.0}, anonymous=True, artifact="s2/runs"))
    _agg(b, "agg:s2/A", ids, _STD)
    _cell(
        b,
        "s2/A",
        "13.00",
        "1.63",
        "agg:s2/A",
        _STD,
        declared("standard deviation", "README.md", 6),
        (fmt,),
        artifact="paper Table 1",
    )
    b.add(
        CandidateSet(
            candidate_set_id="candidates:s2",
            kind=CandidateKind.RUN,
            universe_status=UniverseStatus.UNKNOWN,
            declared_size=unknown_field("no declaration"),
            surviving_size=direct(3, "s2/runs", key="files", note="files on disk"),
        )
    )
    b.add(
        ComparisonSet(
            comparison_set_id="cmp:s2", members=(("s2/A", "A"),), external_origin=direct("own", "README.md", 7)
        )
    )
    return b


# ------------------------------------------------------------------ S3 spread wording
def s3_spread_wording() -> Bundle:
    """FM6/FM7: the published +/- is 3*SE; one cell names no formula, one names the wrong one."""
    b = Bundle(project="S3")
    fmt = _fmt(b)
    b.add(
        ResultArtifact(
            path="s3/runs", columns=("metric",), produced_by=ProducedBy(script="s3/collect.py", grade=Grade.DIRECT)
        )
    )
    ids = tuple(_members(b, "agg:s3/A", {"r1": 10.0, "r2": 12.0, "r3": 14.0}, artifact="s3/runs"))
    _agg(b, "agg:s3/A", ids, _K3)
    ids_b = tuple(_members(b, "agg:s3/B", {"r1": 10.0, "r2": 12.0, "r3": 14.0}, artifact="s3/runs"))
    _agg(b, "agg:s3/B", ids_b, _K3)
    _cell(
        b,
        "s3/A",
        "12.00",
        "2.83",
        "agg:s3/A",
        _K3,
        unknown_field("no wording says what the +/- is"),
        (fmt,),
        artifact="paper Table 1",
    )
    _cell(
        b,
        "s3/B",
        "12.00",
        "2.83",
        "agg:s3/B",
        _K3,
        declared("standard deviation", "README.md", 6),
        (fmt,),
        artifact="paper Table 1",
    )
    b.add(
        CandidateSet(
            candidate_set_id="candidates:s3",
            kind=CandidateKind.RUN,
            universe_status=UniverseStatus.RECOVERED,
            declared_size=direct(3, "s3/runs", key="runs", note="runs"),
            surviving_size=direct(3, "s3/runs", key="runs", note="runs"),
            promotion_evidence=direct(True, "s3/collect.py", 3),
        )
    )
    b.add(
        ComparisonSet(
            comparison_set_id="cmp:s3",
            members=(("s3/A", "A"), ("s3/B", "B")),
            external_origin=direct("own", "README.md", 7),
        )
    )
    return b


# ------------------------------------------------------------- S4 selection deviation
def s4_selection_deviation() -> Bundle:
    """FM8: the declared policy is "take the best"; the promoted candidate is not the best."""
    b = Bundle(project="S4")
    fmt = _fmt(b)
    b.add(
        ResultArtifact(
            path="s4/runs", columns=("metric",), produced_by=ProducedBy(script="s4/collect.py", grade=Grade.DIRECT)
        )
    )
    ids = tuple(_members(b, "agg:s4/A", {"r1": 20.0, "r2": 22.0, "r3": 24.0}, artifact="s4/runs"))
    _agg(b, "agg:s4/A", ids, _STD)
    b.add(
        SelectionEvent(
            selection_id="sel:s4",
            kind=SelectionKind.HYPERPARAMETER,
            candidate_set_ref="candidates:s4",
            criterion=SelectionCriterion(
                metric=direct("objective", "s4/search.py", 10),
                split=direct("validation", "s4/search.py", 11),
                direction=direct("minimize", "s4/search.py", 12),
                scope=direct("one search group", "s4/search.py", 13),
                tie_break=direct("strict <, earliest wins", "s4/search.py", 12),
                timing=direct("search time", "s4/search.py", 13),
            ),
            candidate_values=(("c1", 2.0), ("c2", 1.5), ("c3", 2.4)),
            promoted_ref="c1",
            declared_policy=declared("the best run's parameters are used", "README.md", 9),
            is_recorded=direct(True, "s4/search.py", 14),
        )
    )
    b.add(
        CandidateSet(
            candidate_set_id="candidates:s4",
            kind=CandidateKind.HYPERPARAMETER,
            universe_status=UniverseStatus.RECOVERED,
            declared_size=direct(3, "s4/search.py", 9, note="candidates"),
            surviving_size=direct(3, "s4/search.py", 9, note="candidates"),
            promotion_evidence=direct(True, "s4/search.py", 14, note="saved"),
        )
    )
    _cell(
        b,
        "s4/A",
        "22.00",
        "1.63",
        "agg:s4/A",
        _STD,
        declared("standard deviation", "README.md", 6),
        (fmt,),
        selection=("sel:s4",),
        comparison="cmp:s4",
    )
    b.add(
        ComparisonSet(
            comparison_set_id="cmp:s4", members=(("s4/A", "A"),), external_origin=direct("own", "README.md", 7)
        )
    )
    return b


# ------------------------------------------------------------- S5 invisible candidates
def s5_invisible_candidates() -> Bundle:
    """FM9/FM10: the surviving product count is never the size of the candidate universe."""
    b = Bundle(project="S5")
    fmt = _fmt(b)
    b.add(
        ResultArtifact(
            path="s5/runs", columns=("metric",), produced_by=ProducedBy(script="s5/collect.py", grade=Grade.DIRECT)
        )
    )
    ids = tuple(_members(b, "agg:s5/A", {"r1": 5.0, "r2": 7.0}, artifact="s5/runs"))
    _agg(b, "agg:s5/A", ids, _STD2)
    _cell(
        b,
        "s5/A",
        "6.00",
        "1.00",
        "agg:s5/A",
        _STD2,
        declared("standard deviation", "README.md", 6),
        (fmt,),
        comparison="cmp:s5",
    )
    coll = IdentityCollision(
        key_type="run.name",
        collision_count=2,
        samples=({"name": "grid_a"}, {"name": "grid_b"}),
        note="two search generations reuse the same key",
    )
    b.add(
        CandidateSet(
            candidate_set_id="candidates:s5/grid",
            kind=CandidateKind.HYPERPARAMETER,
            universe_status=UniverseStatus.PARTIAL,
            declared_size=declared(24, "README.md", 10, key="grid", note="grid points"),
            surviving_size=direct(3, "s5/runs", key="files", note="files on disk"),
            generation="adopted",
            superseded_by="",
            identity_collision=coll,
            unobservable_sources=(
                UnobservableSource(
                    "a fetch filter drops runs by name before any product is written",
                    direct("keep", "s5/fetch.py", 4, key="filter"),
                ),
            ),
            promotion_evidence=direct(False, "s5/fetch.py", 9, note="printed only"),
        )
    )
    b.add(
        CandidateSet(
            candidate_set_id="candidates:s5/open",
            kind=CandidateKind.HYPERPARAMETER,
            universe_status=UniverseStatus.UNRECOVERABLE,
            declared_size=declared(3, "README.md", 11, key="seeds", note="declared runs"),
            surviving_size=direct(2, "s5/runs", key="files", note="files on disk"),
            generation="unknown",
            unobservable_sources=(
                UnobservableSource(
                    "no search product of any kind exists", direct("census", "s5", note="directory inventory")
                ),
                UnobservableSource(
                    "every shipped config hardcodes the same seed", declared("seed: 0", "s5/config.yml", 1)
                ),
            ),
            promotion_evidence=unknown_field("nothing promotes a configuration"),
        )
    )
    b.add(
        ComparisonSet(
            comparison_set_id="cmp:s5", members=(("s5/A", "A"),), external_origin=direct("own", "README.md", 7)
        )
    )
    return b


FIXTURES = {
    "S1": s1_clean_chain,
    "S2": s2_member_identity_mismatch,
    "S3": s3_spread_wording,
    "S4": s4_selection_deviation,
    "S5": s5_invisible_candidates,
}

#: (rule_id, target) -> expected status. Derived from Phase 0 §11-14, not from output.
EXPECTED: dict[str, dict[tuple[str, str], str]] = {
    "S1": {
        ("RD001", "s1/A"): "PASS",
        ("RD001", "s1/A@README"): "PASS",
        ("RD001", "s1/B"): "PASS",
        ("RD002", "aggregation:agg:s1/A"): "PASS",
        ("RD002", "aggregation:agg:s1/A@README"): "PASS",
        ("RD002", "aggregation:agg:s1/B"): "PASS",
        ("RD003", "selection:sel:s1"): "PASS",
        ("RD003", "reported:s1/A@README"): "NOT_APPLICABLE",
        ("RD003", "reported:s1/B"): "NOT_APPLICABLE",
        ("RD004", "candidates:candidates:s1"): "PASS",
        ("RD005", "s1/A"): "PASS",
        ("RD005", "s1/A@README"): "PASS",
        ("RD005", "s1/B"): "PASS",
        ("RD006", "reported:s1/A"): "PASS",
        ("RD006", "reported:s1/A@README"): "PASS",
        ("RD006", "reported:s1/B"): "PASS",
        ("RD007", "comparison:cmp:s1"): "PASS",
        ("RD008", "quantity:s1/A"): "PASS",
        ("RD008", "quantity:s1/B"): "INCONCLUSIVE",
    },
    "S2": {
        ("RD001", "s2/A"): "INCONCLUSIVE",
        ("RD002", "aggregation:agg:s2/A"): "INCONCLUSIVE",
        ("RD003", "reported:s2/A"): "NOT_APPLICABLE",
        ("RD004", "candidates:candidates:s2"): "INCONCLUSIVE",
        ("RD005", "s2/A"): "PASS",
        ("RD006", "reported:s2/A"): "INCONCLUSIVE",
        ("RD007", "comparison:cmp:s2"): "NOT_APPLICABLE",
        ("RD008", "quantity:s2/A"): "INCONCLUSIVE",
        ("RD008", "artifact:s2/runs"): "FAIL",
    },
    "S3": {
        ("RD001", "s3/A"): "PASS",
        ("RD001", "s3/B"): "PASS",
        ("RD002", "aggregation:agg:s3/A"): "PASS",
        ("RD002", "aggregation:agg:s3/B"): "PASS",
        ("RD003", "reported:s3/A"): "NOT_APPLICABLE",
        ("RD003", "reported:s3/B"): "NOT_APPLICABLE",
        ("RD004", "candidates:candidates:s3"): "PASS",
        ("RD005", "s3/A"): "INCONCLUSIVE",
        ("RD005", "s3/B"): "FAIL",
        ("RD006", "reported:s3/A"): "PASS",
        ("RD006", "reported:s3/B"): "PASS",
        ("RD007", "comparison:cmp:s3"): "NOT_APPLICABLE",
        ("RD008", "quantity:s3/A"): "INCONCLUSIVE",
        ("RD008", "quantity:s3/B"): "INCONCLUSIVE",
    },
    "S4": {
        ("RD001", "s4/A"): "PASS",
        ("RD002", "aggregation:agg:s4/A"): "PASS",
        ("RD003", "selection:sel:s4"): "FAIL",
        ("RD004", "candidates:candidates:s4"): "PASS",
        ("RD005", "s4/A"): "PASS",
        ("RD006", "reported:s4/A"): "PASS",
        ("RD007", "comparison:cmp:s4"): "NOT_APPLICABLE",
        ("RD008", "quantity:s4/A"): "INCONCLUSIVE",
    },
    "S5": {
        ("RD001", "s5/A"): "PASS",
        ("RD002", "aggregation:agg:s5/A"): "PASS",
        ("RD003", "reported:s5/A"): "NOT_APPLICABLE",
        ("RD004", "candidates:candidates:s5/grid"): "INCONCLUSIVE",
        ("RD004", "candidates:candidates:s5/open"): "INCONCLUSIVE",
        ("RD005", "s5/A"): "PASS",
        ("RD006", "reported:s5/A"): "PASS",
        ("RD007", "comparison:cmp:s5"): "NOT_APPLICABLE",
        ("RD008", "quantity:s5/A"): "INCONCLUSIVE",
    },
}
