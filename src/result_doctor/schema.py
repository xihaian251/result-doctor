"""The eight Phase 0 schema objects.

Every field traces to an observed failure mode (FM1-FM14 of
`phase0/RESULT_DOCTOR_PHASE0_REPORT.md` §9). Objects that Phase 0 explicitly excluded
(ResultDAG, MetricRecord, ClaimRef, TrackerConnection, any score) are not present here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .evidence import EvidenceField, Grade, SourceRef
from .status import UniverseStatus


class SpreadKind(str, Enum):
    NONE = "none"
    STD = "std"
    SEM = "sem"
    K_SEM = "k_sem"


class MemberRuleKind(str, Enum):
    """FM5: a member gate can be real (it excludes runs) and still never be declared."""

    ENUMERATED = "enumerated"
    BY_PATTERN = "by_pattern"
    BY_QUERY = "by_query"
    UNDECLARED = "undeclared"


class SelectorKind(str, Enum):
    LAST_ROW = "last_row"
    BEST = "best"
    MIN = "min"
    MAX = "max"
    MEAN = "mean"
    TIME_TRUNCATED = "time_truncated_at"
    UNKNOWN = "unknown"


class CandidateKind(str, Enum):
    HYPERPARAMETER = "hyperparameter"
    CHECKPOINT = "checkpoint"
    RUN = "run"
    MODEL = "model"
    DATASET = "dataset"
    REPORTED_RESULT = "reported_result"


class SelectionKind(str, Enum):
    CHECKPOINT = "checkpoint"
    RUN = "run"
    HYPERPARAMETER = "hyperparameter"
    MODEL = "model"
    DATASET_LEVEL = "dataset_level"
    REPORTED_RESULT = "reported_result"


class TransformStep(str, Enum):
    SIGN_FLIP = "sign_flip"
    SCALE = "scale"
    SUM_OF_PART = "sum_of_part"
    ROUND = "round"
    FORMAT = "format"
    DELTA = "delta"
    BEST_OF_N = "best_of_n"
    TRUNCATE_WINDOW = "truncate_window"
    IDENTITY = "identity"


class AppliedAt(str, Enum):
    CODE = "code"
    SCRIPT = "script"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Locus:
    """Where the reported number is printed. FM1/FM13 require the quoted original.

    `quantity_key` is what makes FM13 detectable at all: two printed cells are only
    comparable once they are declared to be the same quantity.
    """

    artifact: str
    page: str = ""
    table: str = ""
    row: str = ""
    column: str = ""
    quoted_text: str = ""
    quantity_key: str = ""


@dataclass(frozen=True)
class SpreadForm:
    kind: SpreadKind = SpreadKind.NONE
    k: float = 1.0
    ddof: int = 0
    n: int = 0
    grade: Grade = Grade.UNKNOWN


@dataclass(frozen=True)
class RunRef:
    """Reference into Experiment Doctor territory. Nothing upstream is re-derived."""

    project: str
    family_key: str
    run_name: str
    artifact_ref: str = ""
    external_id: EvidenceField = field(default_factory=EvidenceField)


@dataclass(frozen=True)
class ObservationSelector:
    kind: SelectorKind = SelectorKind.UNKNOWN
    param: float | None = None
    column: str = ""
    grade: Grade = Grade.UNKNOWN
    source: str = ""


@dataclass(frozen=True)
class AggregationMember:
    """FM3: identity binding is usually UNKNOWN while the value itself is DIRECT."""

    member_id: str
    run_ref: RunRef
    selector: ObservationSelector
    observed_value: EvidenceField
    artifact_ref: str = ""
    excluded: bool = False


@dataclass(frozen=True)
class Exclusion:
    """FM4: the list can exist while the criterion is not recomputable."""

    member_id: str
    listed: EvidenceField
    reason_grade: Grade = Grade.UNKNOWN
    criterion_recomputable: bool = False
    note: str = ""


@dataclass(frozen=True)
class MemberRule:
    kind: MemberRuleKind
    expression: str = ""
    grade: Grade = Grade.UNKNOWN
    source: str = ""


@dataclass(frozen=True)
class ProducedBy:
    """FM2: the basis on which artifact supersession is diagnosable at all."""

    script: str = ""
    call_site: str = ""
    invocation_args: str = ""
    project_id: str = ""
    grade: Grade = Grade.UNKNOWN


@dataclass(frozen=True)
class ResultArtifact:
    path: str
    sha256: str = ""
    size: int = 0
    columns: tuple[str, ...] = ()
    produced_by: ProducedBy = field(default_factory=ProducedBy)
    superseded_from: tuple[str, ...] = ()
    superseded_by: tuple[str, ...] = ()
    required_columns: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Aggregation:
    aggregation_id: str
    center: str = "mean"
    dispersion_expression: str = ""
    spread_form: SpreadForm = field(default_factory=SpreadForm)
    member_rule: MemberRule = field(default_factory=lambda: MemberRule(MemberRuleKind.UNDECLARED))
    member_ids: tuple[str, ...] = ()
    exclusions: tuple[Exclusion, ...] = ()
    parent_aggregation_ref: str = ""
    output_ref: str = ""


@dataclass(frozen=True)
class IdentityCollision:
    """FM9. `value_overlap` is always reported together with the comparison basis,
    because an ill-defined basis (differing key sets) makes a zero overlap vacuous.
    """

    key_type: str
    collision_count: int
    samples: tuple[dict[str, object], ...] = ()
    note: str = ""


@dataclass(frozen=True)
class UnobservableSource:
    kind: str
    evidence: EvidenceField


@dataclass(frozen=True)
class CandidateSet:
    candidate_set_id: str
    kind: CandidateKind
    universe_status: UniverseStatus = UniverseStatus.UNKNOWN
    declared_size: EvidenceField = field(default_factory=EvidenceField)
    surviving_size: EvidenceField = field(default_factory=EvidenceField)
    generation: str = ""
    superseded_by: str = ""
    identity_collision: IdentityCollision | None = None
    unobservable_sources: tuple[UnobservableSource, ...] = ()
    promotion_evidence: EvidenceField = field(default_factory=EvidenceField)


@dataclass(frozen=True)
class SelectionCriterion:
    metric: EvidenceField = field(default_factory=EvidenceField)
    split: EvidenceField = field(default_factory=EvidenceField)
    direction: EvidenceField = field(default_factory=EvidenceField)
    scope: EvidenceField = field(default_factory=EvidenceField)
    tie_break: EvidenceField = field(default_factory=EvidenceField)
    timing: EvidenceField = field(default_factory=EvidenceField)


@dataclass(frozen=True)
class SelectionEvent:
    """FM8. `declared_policy` vs `promoted_ref` is what makes RD003 deterministic."""

    selection_id: str
    kind: SelectionKind
    candidate_set_ref: str
    criterion: SelectionCriterion
    candidate_values: tuple[tuple[str, float], ...] = ()
    promoted_ref: str = ""
    declared_policy: EvidenceField = field(default_factory=EvidenceField)
    tie_tolerance: float = 0.0
    is_recorded: EvidenceField = field(default_factory=EvidenceField)
    effect_on_report: str = ""

    @property
    def direction_is_minimizes(self) -> bool:
        return str(self.criterion.direction.value or "").strip().lower().startswith("min")


@dataclass(frozen=True)
class PresentationRule:
    expression: str = ""
    operator: str = ""
    symmetric: bool = True
    k_factor: float = 1.0
    source: str = ""


@dataclass(frozen=True)
class ComparisonSet:
    """FM12/FM14.

    `observed_marks` is an evidence field, not a list: "the table shows no mark" and
    "the marks were not recoverable" are different facts and must not collapse.
    """

    comparison_set_id: str
    members: tuple[tuple[str, str], ...] = ()
    external_origin: EvidenceField = field(default_factory=EvidenceField)
    presentation_rule: PresentationRule | None = None
    observed_marks: EvidenceField = field(default_factory=EvidenceField)
    recomputed_marks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Transformation:
    """FM11: the chain is typed, conditioned and placed, so a branch that did not
    fire is distinguishable from a step that was never applied.
    """

    transform_id: str
    step: TransformStep
    applied_at: AppliedAt
    target: str = ""
    params: dict[str, object] = field(default_factory=dict)
    condition: EvidenceField = field(default_factory=EvidenceField)
    grade: Grade = Grade.DIRECT
    sources: tuple[SourceRef, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class ReportedResult:
    rid: str
    locus: Locus
    metric_name: EvidenceField = field(default_factory=EvidenceField)
    direction_semantics: EvidenceField = field(default_factory=EvidenceField)
    value: EvidenceField = field(default_factory=EvidenceField)
    spread: EvidenceField = field(default_factory=EvidenceField)
    spread_form: SpreadForm = field(default_factory=SpreadForm)
    aggregation_ref: str = ""
    transformation_refs: tuple[str, ...] = ()
    selection_refs: tuple[str, ...] = ()
    comparison_set_ref: str = ""
    spread_label: EvidenceField = field(default_factory=EvidenceField)
    not_aggregated_reason: str = ""
