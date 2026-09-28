"""Evidence bundle: a deterministic container that holds the eight schema objects.

It is plumbing for the loaders and rules, not a ninth schema entity. Layered
aggregation is expressed by `Aggregation.parent_aggregation_ref` references only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import Grade
from .schema import (
    Aggregation,
    AggregationMember,
    CandidateSet,
    ComparisonSet,
    ReportedResult,
    ResultArtifact,
    SelectionEvent,
    Transformation,
)


@dataclass
class Bundle:
    project: str = ""
    root: str = ""
    reported_results: dict[str, ReportedResult] = field(default_factory=dict)
    aggregations: dict[str, Aggregation] = field(default_factory=dict)
    members: dict[str, AggregationMember] = field(default_factory=dict)
    artifacts: dict[str, ResultArtifact] = field(default_factory=dict)
    transformations: dict[str, Transformation] = field(default_factory=dict)
    candidate_sets: dict[str, CandidateSet] = field(default_factory=dict)
    selection_events: dict[str, SelectionEvent] = field(default_factory=dict)
    comparison_sets: dict[str, ComparisonSet] = field(default_factory=dict)

    def add(self, *objs: object) -> None:
        for o in objs:
            if isinstance(o, ReportedResult):
                self.reported_results[o.rid] = o
            elif isinstance(o, Aggregation):
                self.aggregations[o.aggregation_id] = o
            elif isinstance(o, AggregationMember):
                self.members[o.member_id] = o
            elif isinstance(o, ResultArtifact):
                self.artifacts[o.path] = o
            elif isinstance(o, Transformation):
                self.transformations[o.transform_id] = o
            elif isinstance(o, CandidateSet):
                self.candidate_sets[o.candidate_set_id] = o
            elif isinstance(o, SelectionEvent):
                self.selection_events[o.selection_id] = o
            elif isinstance(o, ComparisonSet):
                self.comparison_sets[o.comparison_set_id] = o
            else:  # pragma: no cover - programmer error
                raise TypeError(f"unsupported schema object {type(o)!r}")

    def chain(self, refs) -> list[Transformation]:
        """Transformation chain in the order the producing script applies it."""
        return [self.transformations[r] for r in refs if r in self.transformations]

    def members_of(self, agg: Aggregation) -> list[AggregationMember]:
        return [self.members[m] for m in agg.member_ids if m in self.members]

    def included(self, agg: Aggregation) -> list[AggregationMember]:
        return [m for m in self.members_of(agg) if not m.excluded]

    def unknown_member_values(self, agg: Aggregation) -> list[AggregationMember]:
        return [m for m in self.included(agg) if m.observed_value.grade is Grade.UNKNOWN]

    def all_member_values_known(self, agg: Aggregation) -> bool:
        inc = self.included(agg)
        return bool(inc) and not self.unknown_member_values(agg)
