"""Frozen TorchSSL archive loader.

Maps the evidence frozen in `phase0/RESULT_DOCTOR_PHASE0_REPORT.md` §5.4 onto the schema:
six downloaded training logs, `scripts/average_log.py`'s aggregation, and the README cell
that reports it. It discovers nothing and reads nothing outside these pinned paths.
"""

from __future__ import annotations

import os
import re

from ..bundle import Bundle
from ..evidence import Grade, SourceRef, declared, direct, unknown_field
from ..schema import (
    Aggregation,
    AggregationMember,
    AppliedAt,
    CandidateKind,
    CandidateSet,
    ComparisonSet,
    Locus,
    MemberRule,
    MemberRuleKind,
    ObservationSelector,
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
from ..status import UniverseStatus

AVERAGE = "scripts/average_log.py"
FIXMATCH = "models/fixmatch/fixmatch.py"
SSL_DATASET = "datasets/ssl_dataset.py"
README = "README.md"
GATE = "1048000 iteration"
RE_BEST_LINE = re.compile(r"BEST_EVAL_ACC: ((?:[0-9]|\.)*)")
RE_TOP1 = re.compile(r"eval/top-1-acc': ((?:[0-9]|\.)*)")

#: The two README cells Phase 0 re-derived exactly (`95.14 ± 0.05`, `95.02 ± 0.09`).
CELLS = {
    "fixmatch_cifar10_250": ("95.14", "0.05"),
    "flexmatch_cifar10_250": ("95.02", "0.09"),
}

#: README.md:58 calls the published +/- "standard errors".
SPREAD_LABEL = "best accuracies with standard errors"


def _eval_lines(log_path: str) -> list[tuple[float, float]]:
    """(top-1 accuracy, running best) of every `iters` evaluation line in a log."""
    out: list[tuple[float, float]] = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.endswith("iters\n"):
                continue
            best, top1 = RE_BEST_LINE.search(line), RE_TOP1.search(line)
            if best and top1:
                out.append((float(top1.group(1)), float(best.group(1))))
    return out


def _add_shared_transforms(bundle: Bundle) -> None:
    bundle.add(
        Transformation(
            transform_id="t:percent",
            step=TransformStep.SCALE,
            applied_at=AppliedAt.CODE,
            target="accuracy",
            params={"stage": "member", "factor": 100},
            condition=declared("always, for every column", AVERAGE, 85, key="*100"),
            sources=(SourceRef(AVERAGE, "x * 100", 85, note="accuracy fraction -> percent"),),
        )
    )
    bundle.add(
        Transformation(
            transform_id="t:str_round",
            step=TransformStep.FORMAT,
            applied_at=AppliedAt.CODE,
            target="table cell",
            params={"stage": "render", "mode": "str_round", "digits": 2},
            condition=declared("always", AVERAGE, 132, key="str(round(x,2))"),
            sources=(
                SourceRef(
                    AVERAGE,
                    "mean/std rendered separately",
                    132,
                    note="str(round(mean,2)) + '\\u00b1' + str(round(std,2))",
                ),
            ),
        )
    )
    #: FM11: the Top5_20 / Top5_50 columns are filled with rolling Top-1 means.
    bundle.add(
        Transformation(
            transform_id="t:top5_column_fill",
            step=TransformStep.SUM_OF_PART,
            applied_at=AppliedAt.CODE,
            target="Top5_20 / Top5_50",
            params={
                "stage": "center",
                "parts": (),
                "declared_source": "eval/top-5-acc",
                "observed_source": "rolling mean of eval/top-1-acc",
            },
            condition=declared("the workbook sheet named Top5_20/Top5_50", AVERAGE, 58, key="avg_20_5acc"),
            sources=(
                SourceRef(
                    AVERAGE, "Top5_20: avg_20_1acc", 58, note="the computed Top-5 means at :52-53 are never written out"
                ),
            ),
        )
    )


def _reported_cells(bundle: Bundle, logs_root: str) -> None:
    for cell, (value, spread) in sorted(CELLS.items()):
        agg_id = f"agg:{cell}/BestAcc"
        refs = ["t:percent", "t:str_round"]
        member_ids = []
        selection_ids = []
        for run in sorted(os.listdir(logs_root)):
            if not run.startswith(cell + "_"):
                continue
            log = os.path.join(logs_root, run, "log.txt")
            if not os.path.exists(log):
                continue
            lines = _eval_lines(log)
            if not lines:
                continue
            rel = f"downloads/logs/{run}/log.txt"
            selection_ids.append(f"sel:checkpoint/{run}")
            bundle.add(
                ResultArtifact(
                    path=rel,
                    columns=("eval/top-1-acc", "BEST_EVAL_ACC"),
                    produced_by=ProducedBy(
                        script="train.py",
                        call_site="per-iteration evaluation",
                        invocation_args="not recorded in the log header",
                        grade=Grade.DECLARED,
                    ),
                    note="a training log; the run's own evaluation stream",
                )
            )
            mid = f"{agg_id}/{run}"
            member_ids.append(mid)
            bundle.add(
                AggregationMember(
                    member_id=mid,
                    run_ref=RunRef(
                        project="torchssl",
                        family_key=cell,
                        run_name=run,
                        artifact_ref=rel,
                        external_id=direct(run, rel, note="the directory name is the run identity"),
                    ),
                    selector=ObservationSelector(
                        kind=SelectorKind.BEST, column="BEST_EVAL_ACC", grade=Grade.DIRECT, source=f"{AVERAGE}:38-41"
                    ),
                    observed_value=direct(
                        lines[-1][1],
                        rel,
                        key="BEST_EVAL_ACC",
                        note="the running maximum as printed on the last evaluation line",
                    ),
                    artifact_ref=rel,
                )
            )
            bundle.add(
                SelectionEvent(
                    selection_id=f"sel:checkpoint/{run}",
                    kind=SelectionKind.CHECKPOINT,
                    candidate_set_ref=f"candidates:checkpoint/{run}",
                    criterion=SelectionCriterion(
                        metric=direct(
                            "eval/top-1-acc",
                            FIXMATCH,
                            206,
                            key="best_eval_acc update",
                            note="computed inside evaluate() after ema.apply_shadow(), so the selected "
                            "weights are the EMA copy (train_utils.py:366-378 leaves BN running "
                            "buffers out of the EMA)",
                        ),
                        split=direct(
                            "test",
                            SSL_DATASET,
                            247,
                            note="loader_dict['eval'] is built with train=False and CIFAR/SVHN/STL-10 "
                            "have no validation split in this codebase",
                        ),
                        direction=direct("maximize", FIXMATCH, 206, key="acc > best_eval_acc"),
                        scope=direct("within one training run", FIXMATCH, 200),
                        tie_break=direct("strict >, so the earliest checkpoint reaching the value wins", FIXMATCH, 206),
                        timing=direct("in training", FIXMATCH, 200),
                    ),
                    candidate_values=tuple((str(i), acc) for i, (acc, _b) in enumerate(lines)),
                    promoted_ref=str(max(range(len(lines)), key=lambda i: lines[i][0])),
                    declared_policy=declared(
                        "the best evaluation accuracy of the run is reported", README, 58, key="results table"
                    ),
                    tie_tolerance=0.0,
                    is_recorded=direct(True, FIXMATCH, 214, note="the winning weights are saved as model_best.pth"),
                    effect_on_report="the value that is averaged into the reported cell; the evaluated weights "
                    "are the EMA shadow copy (evaluate() calls ema.apply_shadow()), and BN "
                    "running buffers are not part of that copy",
                )
            )
            accs = [a for a, _b in lines]
            bundle.add(
                CandidateSet(
                    candidate_set_id=f"candidates:checkpoint/{run}",
                    kind=CandidateKind.CHECKPOINT,
                    universe_status=UniverseStatus.RECOVERED,
                    declared_size=direct(len(accs), rel, key="evaluation lines", note="recorded evaluations"),
                    surviving_size=direct(len(accs), rel, key="evaluation lines", note="recorded evaluations"),
                    generation="within-run",
                    unobservable_sources=(
                        UnobservableSource(
                            "checkpoints overwritten during training are not retained, but their recorded "
                            "evaluation lines are all present",
                            direct("model_best.pth", FIXMATCH, 212, key="save path"),
                        ),
                    ),
                    promotion_evidence=direct(True, FIXMATCH, 212, key="model_best"),
                )
            )
        bundle.add(
            Aggregation(
                aggregation_id=agg_id,
                center="mean",
                dispersion_expression="np.std(values) with numpy's default ddof=0",
                spread_form=SpreadForm(SpreadKind.STD, k=1.0, ddof=0, n=len(member_ids), grade=Grade.DIRECT),
                member_rule=MemberRule(
                    kind=MemberRuleKind.BY_PATTERN,
                    expression=f"group by run name minus its last '_' segment; a log counts only if it "
                    f"contains the literal {GATE!r}",
                    grade=Grade.DIRECT,
                    source=f"{AVERAGE}:23-34, :79-83",
                ),
                member_ids=tuple(member_ids),
            )
        )
        bundle.add(
            ReportedResult(
                rid=f"{cell}/BestAcc",
                locus=Locus(
                    artifact=README,
                    page="58",
                    table="results",
                    row=cell,
                    column="BestAcc",
                    quoted_text=f"{value}\u00b1{spread}",
                    quantity_key=f"{cell}/BestAcc",
                ),
                metric_name=direct("BestAcc (test accuracy of the best checkpoint)", AVERAGE, 96),
                direction_semantics=direct("maximize", FIXMATCH, 210),
                value=direct(value, README, 58, key=cell),
                spread=direct(spread, README, 58, key=cell),
                spread_form=SpreadForm(SpreadKind.STD, k=1.0, ddof=0, n=len(member_ids), grade=Grade.DIRECT),
                aggregation_ref=agg_id,
                transformation_refs=tuple(refs),
                selection_refs=tuple(selection_ids),
                comparison_set_ref=f"cmp:{cell}",
                spread_label=declared(SPREAD_LABEL, README, 58, key="wording"),
            )
        )


def _generated_workbook_cell(bundle: Bundle) -> None:
    """The FM11 victim: a produced column whose declared quantity is not what is written."""
    bundle.add(
        ReportedResult(
            rid="generated/fixmatch_cifar10_250/Top5_20",
            locus=Locus(
                artifact="scripts/../saved_models/final_res workbook, sheet Top5_20 (generated)",
                table="Top5_20",
                row="fixmatch_cifar10_250",
                column="cifar10_250",
                quoted_text="written by average_log.py, not retained in the archive",
                quantity_key="generated/fixmatch_cifar10_250/Top5_20",
            ),
            metric_name=declared("Top5_20 (mean of the last 20 Top-5 evaluations)", AVERAGE, 58),
            value=unknown_field("the generated workbook is not part of the frozen archive"),
            spread=unknown_field("the generated workbook is not part of the frozen archive"),
            transformation_refs=("t:top5_column_fill", "t:percent", "t:str_round"),
            comparison_set_ref="cmp:generated",
            not_aggregated_reason="the cell is a generated presentation product; its members are the same "
            "runs as the accuracy cell but the file itself is not in the archive",
        )
    )


def _seed_universe(bundle: Bundle, logs_root: str) -> None:
    """The project-level candidate universe: no search product of any kind exists."""
    n_logs = len([d for d in os.listdir(logs_root) if os.path.exists(os.path.join(logs_root, d, "log.txt"))])
    bundle.add(
        CandidateSet(
            candidate_set_id="candidates:hyperparameter/torchssl",
            kind=CandidateKind.HYPERPARAMETER,
            universe_status=UniverseStatus.UNRECOVERABLE,
            declared_size=declared(3, README, 58, key="three different random seeds", note="declared runs"),
            surviving_size=direct(n_logs, "downloads/logs", key="log.txt", note="logs present in the archive"),
            generation="unknown",
            unobservable_sources=(
                UnobservableSource(
                    "no sweep, grid, tracker or search product exists anywhere in the repository",
                    direct("directory census", "repo", note="recorded by the Phase 0 archive inventory"),
                ),
                UnobservableSource(
                    "all shipped configs hardcode seed 0 and the generator hardcodes seeds=[0], so the "
                    "declared seed set is not reconstructible from the configs",
                    declared("seeds=[0]", "scripts/config_generator.py", 192, key="seed"),
                ),
                UnobservableSource(
                    "a log counts toward a cell only if it contains the completion marker, so logs present "
                    "and runs executed are different quantities",
                    direct(GATE, AVERAGE, 23, key="membership gate"),
                ),
                UnobservableSource(
                    "the shipped evaluation entry point reads checkpoint keys that the shipped save_model "
                    "never writes, so the reported numbers cannot come from that path but from the "
                    "in-training evaluation log parsed above",
                    direct("eval_model / train_model", "eval.py", 37, key="checkpoint load"),
                ),
            ),
            promotion_evidence=unknown_field("nothing promotes a configuration in this project"),
        )
    )
    for cell in sorted(CELLS):
        bundle.add(
            ComparisonSet(
                comparison_set_id=f"cmp:{cell}",
                members=((f"{cell}/BestAcc", cell),),
                external_origin=direct("the only peer of this cell is itself", README, 58),
                observed_marks=direct((), README, 58, note="the table prints no mark"),
            )
        )
    bundle.add(
        ComparisonSet(
            comparison_set_id="cmp:generated",
            members=(("generated/fixmatch_cifar10_250/Top5_20", "fixmatch_cifar10_250"),),
            external_origin=direct("produced by this project's own script", AVERAGE, 58),
            observed_marks=unknown_field("the generated workbook is not retained"),
        )
    )


def load_torchssl_bundle(root: str) -> Bundle:
    """Build the TorchSSL evidence bundle from the frozen archive at `root`."""
    bundle = Bundle(project="TorchSSL")
    bundle.root = os.path.abspath(root)
    logs_root = os.path.join(bundle.root, "downloads", "logs")
    _add_shared_transforms(bundle)
    _reported_cells(bundle, logs_root)
    _generated_workbook_cell(bundle)
    _seed_universe(bundle, logs_root)
    return bundle
