"""Frozen GMMVI archive loader.

Not a discovery engine: it maps the evidence frozen in
`phase0/RESULT_DOCTOR_PHASE0_REPORT.md` §5.1-§5.3 onto the Result Doctor schema. Paths,
column names and paper cell values are pinned to what Phase 0 read off the archive, and
every number is recomputed from the archive on each run. Nothing is auto-detected.

Upstream (Experiment Doctor) provenance - seed, git, environment, resolved config,
termination - is referenced by path only and never re-derived here.
"""

from __future__ import annotations

import csv
import os

import yaml

from ..bundle import Bundle
from ..evidence import Grade, SourceRef, declared, direct, unknown_field
from ..schema import (
    Aggregation,
    AggregationMember,
    AppliedAt,
    CandidateKind,
    CandidateSet,
    ComparisonSet,
    Exclusion,
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
from ..status import UniverseStatus

SCRIPT = "repo/evaluations/fetch_exp3.py"
RESULTS = "extracted/evaluations/results"
README = "repo/README.rst"
PAPER8 = "paper Table 8 (p.29)"
PAPER5 = "paper Table 5 (p.12)"
GRID_DIR = "repo/evaluations/configs/exp3 (hyperopt)"
DISCARDED_DIR = f"{GRID_DIR}/previously_tried_grids"

#: environment -> (evaluation family directory, `-elbo` column, group name suffix)
ENVIRONMENT = {
    "PlanarRobot": ("Planar4_EVAL", "_planar_4"),
    "TALOS": ("TALOS_EVAL", "_talos"),
    "STM300": ("STM300_EVAL", "_stm300"),
    "BreastCancer": ("BC_EVAL", "_bc"),
}

#: Table 8 `-ELBO` cells, transcribed in `notes/paper_exp3_table_transcription.md` §3.
#: Only cells already frozen in text form are used: Phase 1 does not parse PDFs.
#: One line per paper cell, three cells per paper row, so each dict reads against the printed table.
# fmt: off
ELBO_CELLS: dict[str, dict[str, tuple[str, str]]] = {
    "PlanarRobot": {
        "samtrux": ("11.47", "0.05"), "samtrox": ("11.47", "0.04"), "samtron": ("11.47", "0.04"),
        "samyron": ("12.93", "0.13"), "samyrox": ("12.98", "0.09"), "samyrux": ("13.16", "0.20"),
        "sepyfux": ("17.26", "2.13"), "sepyrux": ("16.35", "0.65"), "zamtrux": ("11.48", "0.04"),
    },
    "TALOS": {
        "samtrux": ("-24.32", "0.22"), "samtrox": ("-24.30", "0.10"), "samtron": ("-24.43", "0.16"),
        "samyron": ("-24.00", "0.23"), "samyrox": ("-23.91", "0.13"), "samyrux": ("-24.13", "0.14"),
        "sepyfux": ("-16.64", "5.26"), "sepyrux": ("-19.00", "1.07"), "zamtrux": ("-23.69", "0.16"),
    },
    "STM300": {
        "samtrux": ("15.00", "0.38"), "samtrox": ("15.24", "0.36"), "samtron": ("14.96", "0.48"),
        "samyron": ("22.50", "0.15"), "samyrox": ("22.28", "0.13"), "samyrux": ("22.41", "0.23"),
        "sepyfux": ("26.69", "0.39"), "sepyrux": ("26.87", "0.45"), "zamtrux": ("N/A", ""),
    },
    # Phase 0 §5.2 froze these three BC cells in text; the remaining six need the PDF.
    "BreastCancer": {
        "samtron": ("78.00", "0.02"), "sepyfux": ("79.78", "0.40"), "sepyrux": ("79.91", "0.93"),
    },
}

#: Table 8 secondary-metric cells whose printed form is `%.2f` like `-ELBO`:
#: TALOS `H(q)` = `entropy`, STM300 `Modes` = `num_detected_modes`.
SECONDARY_CELLS: dict[str, dict[str, tuple[str, str]]] = {
    "TALOS": {
        "samtrux": ("-16.81", "0.07"), "samtrox": ("-16.88", "0.09"), "samtron": ("-16.82", "0.07"),
        "samyron": ("-17.25", "0.16"), "samyrox": ("-17.32", "0.16"), "samyrux": ("-17.26", "0.10"),
        "sepyfux": ("-25.03", "5.46"), "sepyrux": ("-22.34", "1.11"), "zamtrux": ("-16.91", "0.07"),
    },
    "STM300": {
        "samtrux": ("13.70", "1.80"), "samtrox": ("14.10", "1.50"), "samtron": ("14.30", "1.53"),
        "samyron": ("9.10", "0.99"), "samyrox": ("9.80", "1.58"), "samyrux": ("9.57", "1.73"),
        "sepyfux": ("0.90", "0.89"), "sepyrux": ("0.30", "0.43"), "zamtrux": ("N/A", ""),
    },
}
SECONDARY_COLUMN = {"TALOS": "entropy", "STM300": "num_detected_modes"}

#: Table 5 (p.12) `-ELBO` twins of the Table 8 cells, from the same note.
#: STM300/Sepyfux `26.87 ±0.45` is the FM13 conflict pair, recorded exactly as printed.
TABLE5_ELBO: dict[str, dict[str, tuple[str, str]]] = {
    "PlanarRobot": {
        "samtron": ("11.47", "0.04"), "samyron": ("12.93", "0.13"),
        "sepyfux": ("17.26", "2.13"), "zamtrux": ("11.48", "0.04"),
    },
    "TALOS": {
        "samtron": ("-24.43", "0.16"), "samyron": ("-24.00", "0.23"),
        "sepyfux": ("-16.64", "5.26"), "zamtrux": ("-23.69", "0.16"),
    },
    "STM300": {"sepyfux": ("26.87", "0.45")},
    "BreastCancer": {"samtron": ("78.00", "0.02")},
}
# fmt: on

#: The only wording in the paper that declares what the +/- is (Table 5 caption, p.12).
SPREAD_LABEL = "3\u03c3 confidence intervals based on the standard error of its mean using ten different seeds"

#: Chain C: search family -> (evaluation family, search metric column, group-name suffix).
#: The suffix is a naming convention, not a schema field: BC_MB's search groups `*_bcmb`
#: are evaluated under `*_bcmb2`, while GC_MB's keep the identical name.
SEARCH_FAMILIES = {
    "BC": ("BC_EVAL", "-elbo", ""),
    "BC_MB": ("BCMB_EVAL", "elbo_fb:", "2"),
    "GC": ("GC_EVAL", "-elbo", ""),
    "GC_MB": ("GCMB_EVAL", "elbo_fb:", ""),
    "GMM100": ("GMM100_EVAL", "-elbo", ""),
    "GMM20": ("GMM20_EVAL", "-elbo", ""),
    "Planar4": ("Planar4_EVAL", "-elbo", ""),
    "STM20": ("STM20_EVAL", "-elbo", ""),
    "STM300": ("STM300_EVAL", "-elbo", ""),
    "TALOS": ("TALOS_EVAL", "-elbo", ""),
    "WINE": ("WINE_EVAL", "-elbo", ""),
}


# ------------------------------------------------------------------ archive probes
def _csv_columns(path: str) -> tuple[str, ...]:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return tuple(next(csv.reader(fh)))
    except (OSError, StopIteration):
        return ()


def _last_value(path: str, column: str) -> float | None:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except OSError:
        return None
    if not rows:
        return None
    try:
        return float(rows[-1][column])
    except (KeyError, TypeError, ValueError):
        return None


def _search_objective(path: str, column: str) -> float | None:
    """`fetch_exp3.py:38-41`: last row of the metric column, negated for `elbo_fb:`."""
    v = _last_value(path, column)
    if v is None:
        return None
    return -v if column == "elbo_fb:" else v


def _leaves(node, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(_leaves(v, f"{prefix}.{k}" if prefix else str(k)))
    else:
        v = node[0] if isinstance(node, list) and len(node) == 1 else node
        #: The two dumps spell one number differently (`2000000` vs `[2000000]`, `1.` vs
        #: `1`), so the comparison is on the value denoted, not on the YAML shape.
        out[prefix] = round(float(v), 9) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    return out


def _grid_documents(path: str):
    with open(path, encoding="utf-8") as fh:
        for doc in yaml.safe_load_all(fh):
            if isinstance(doc, dict) and isinstance(doc.get("grid"), dict):
                yield doc


def _grid_census(root: str, rel_dir: str) -> dict[str, dict]:
    """{wandb group: {"points", "docs", "values": {leaf: value or [values]}}}.

    A group name can appear in several documents of several files - that reuse is the
    fact FM9 is about - so the counts are accumulated per name rather than overwritten.
    """
    census: dict[str, dict] = {}
    directory = os.path.join(root, rel_dir)
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".yml"):
            continue
        for doc in _grid_documents(os.path.join(directory, name)):
            group = str((doc.get("wandb") or {}).get("group") or doc.get("name", ""))
            entry = census.setdefault(group, {"points": 0, "docs": 0, "values": {}})
            entry["points"] += _expanded_points(doc["grid"])
            entry["docs"] += 1
            for key, value in _leaves(doc["grid"]).items():
                seen = entry["values"].setdefault(key, [])
                seen.append(value)
    for entry in census.values():
        for key, seen in entry["values"].items():
            entry["values"][key] = seen[0] if len(seen) == 1 else seen
    return census


def _expanded_points(node) -> int:
    points = 1
    for values in _leaf_lists(node):
        points *= max(1, len(values))
    return points


def _leaf_lists(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _leaf_lists(v)
    elif isinstance(node, list):
        yield node
    else:
        yield [node]


# ------------------------------------------------------------------ shared records
def _add_shared_transforms(bundle: Bundle) -> None:
    """The steps `fetch_exp3_eval` applies between a raw column and a printed cell."""
    bundle.add(
        Transformation(
            transform_id="t:elbo_last_row",
            step=TransformStep.IDENTITY,
            applied_at=AppliedAt.CODE,
            target="-elbo",
            params={"stage": "member", "selector": "last row of the history"},
            condition=declared("always", SCRIPT, 98, key="selector"),
            sources=(SourceRef(SCRIPT, "to_numpy()[-1]", 98, note="the last row, not the best row"),),
        )
    )
    bundle.add(
        Transformation(
            transform_id="t:secondary_sum",
            step=TransformStep.SUM_OF_PART,
            applied_at=AppliedAt.CODE,
            target="secondary metric",
            params={"stage": "member", "parts": ()},
            condition=declared("secondary_metrics are always summed", SCRIPT, 102, key="np.sum"),
            sources=(
                SourceRef(
                    SCRIPT, "np.sum(this_secondaries)", 103, note="one-element list here, so the sum is the identity"
                ),
            ),
        )
    )
    bundle.add(
        Transformation(
            transform_id="t:elbo_format",
            step=TransformStep.FORMAT,
            applied_at=AppliedAt.CODE,
            target="table cell",
            params={"stage": "render", "mode": "fixed", "digits": 2},
            condition=declared('format == "elbo_format"', SCRIPT, 64, key="branch"),
            sources=(
                SourceRef(SCRIPT, "elbo_format", 68, note="mean and \u00b1 are rounded by separate %.2f conversions"),
            ),
        )
    )


def _add_cell(
    bundle: Bundle,
    env: str,
    method: str,
    column: str,
    value: str,
    spread: str,
    table: str,
    secondary: bool = False,
) -> None:
    family, suffix = ENVIRONMENT[env]
    group = f"{method}{suffix}"
    rel_dir = f"{RESULTS}/{family}/{group}"
    abs_dir = os.path.join(bundle.root, rel_dir)
    refs = ["t:elbo_last_row", "t:elbo_format"] + (["t:secondary_sum"] if secondary else [])
    paper = PAPER8 if table == "Table 8" else PAPER5
    rid = f"{env}/{method}/{column}/{table}"
    if value == "N/A":
        bundle.add(
            ReportedResult(
                rid=rid,
                locus=Locus(
                    artifact=paper,
                    page="29" if table == "Table 8" else "12",
                    table=table,
                    row=method,
                    column=f"{env} / {column}",
                    quoted_text="N/A",
                    quantity_key=f"{env}/{method}/{column}",
                ),
                metric_name=direct(column, SCRIPT, 81, key="metric argument"),
                value=direct("N/A", paper, key=rid),
                spread=direct("", paper, key=rid),
                comparison_set_ref=f"cmp:{env}",
                not_aggregated_reason="the cell is printed as N/A in both tables, and the archive holds no "
                "evaluation group for this method and environment",
            )
        )
        return
    if not os.path.isdir(abs_dir):
        bundle.add(
            ReportedResult(
                rid=rid,
                locus=Locus(
                    artifact=paper,
                    table=table,
                    row=method,
                    column=f"{env} / {column}",
                    quoted_text=f"{value} \u00b1{spread}",
                    quantity_key=f"{env}/{method}/{column}",
                ),
                metric_name=direct(column, SCRIPT, 81, key="metric argument"),
                value=direct(value, paper, key=rid),
                spread=direct(spread, paper, key=rid),
                comparison_set_ref=f"cmp:{env}",
                spread_label=declared(SPREAD_LABEL, PAPER5, "12", key="caption"),
            )
        )
        return

    survivors = sorted(
        (f for f in os.listdir(abs_dir) if f.startswith("run_") and f.endswith(".csv")), key=lambda s: int(s[4:-4])
    )
    bads = sorted(
        (f for f in os.listdir(abs_dir) if f.startswith("run_") and f.endswith(".csv.bad")), key=lambda s: int(s[4:-8])
    )
    columns = _csv_columns(os.path.join(abs_dir, survivors[0])) if survivors else ()
    required = ("MMD:",) if family == "BC_EVAL" else ()
    bundle.add(
        ResultArtifact(
            path=rel_dir,
            columns=columns,
            produced_by=ProducedBy(
                script=SCRIPT,
                call_site="fetch_exp3_eval",
                invocation_args="the call whose output matches this directory is commented out at HEAD; the only "
                f"live call ({SCRIPT}:271-275) writes BCMB with bi_accuracy",
                grade=Grade.UNKNOWN,
            ),
            required_columns=required,
            note="two different calls in the script write the same directory name",
        )
    )
    agg_id = f"agg:{env}/{method}/{column}"
    member_ids = []
    for f in survivors:
        run = f[:-4]
        mid = f"{agg_id}/{run}"
        member_ids.append(mid)
        bundle.add(
            AggregationMember(
                member_id=mid,
                run_ref=RunRef(
                    project="gmmvi-exp3",
                    family_key=group,
                    run_name=run,
                    artifact_ref=rel_dir,
                    external_id=unknown_field("the run-index <-> wandb run-id binding is not in the artifacts", SCRIPT),
                ),
                selector=ObservationSelector(
                    kind=SelectorKind.LAST_ROW, column=column, grade=Grade.DIRECT, source=f"{SCRIPT}:98"
                ),
                observed_value=direct(
                    _last_value(os.path.join(abs_dir, f), column),
                    f"{rel_dir}/{f}",
                    key=column,
                    note=f"last row of {column}",
                ),
                artifact_ref=rel_dir,
            )
        )
    exclusions = tuple(
        Exclusion(
            member_id=f"{agg_id}/{f[:-8]}",
            listed=direct(
                len(bads), rel_dir, key="run_*.csv.bad", note="bad seeds are kept on disk under a .bad suffix"
            ),
            reason_grade=Grade.DECLARED,
            criterion_recomputable=False,
            note="the exclusion is executed from a hand-written run-id list, and the surviving "
            "final values of excluded runs lie inside the retained range",
        )
        for f in bads
    )
    for f in bads:
        run = f[:-8]
        bundle.add(
            AggregationMember(
                member_id=f"{agg_id}/{run}",
                run_ref=RunRef(
                    project="gmmvi-exp3",
                    family_key=group,
                    run_name=run,
                    artifact_ref=rel_dir,
                    external_id=unknown_field("the run-index <-> wandb run-id binding is not in the artifacts", SCRIPT),
                ),
                selector=ObservationSelector(
                    kind=SelectorKind.LAST_ROW, column=column, grade=Grade.DIRECT, source=f"{SCRIPT}:96-104"
                ),
                observed_value=direct(
                    _last_value(os.path.join(abs_dir, f), column),
                    f"{rel_dir}/{f}",
                    key=column,
                    note=f"last row of {column} in a .bad file",
                ),
                artifact_ref=rel_dir,
                excluded=True,
            )
        )
    all_ids = member_ids + [e.member_id for e in exclusions]
    bundle.add(
        Aggregation(
            aggregation_id=agg_id,
            center="mean",
            dispersion_expression=f"np.std(ddof=0) * 3 / sqrt({len(survivors)})",
            spread_form=SpreadForm(SpreadKind.K_SEM, k=3.0, ddof=0, n=len(survivors), grade=Grade.DIRECT),
            member_rule=MemberRule(
                kind=MemberRuleKind.BY_PATTERN,
                expression="include run_{i}.csv, exclude run_{i}.csv.bad",
                grade=Grade.DIRECT,
                source=f"{SCRIPT}:96-104",
            ),
            member_ids=tuple(all_ids),
            exclusions=exclusions,
        )
    )
    bundle.add(
        ReportedResult(
            rid=rid,
            locus=Locus(
                artifact=paper,
                page="29" if table == "Table 8" else "12",
                table=table,
                row=method,
                column=f"{env} / {column}",
                quoted_text=f"{value} \u00b1{spread}",
                quantity_key=f"{env}/{method}/{column}",
            ),
            metric_name=direct(column, SCRIPT, 81, key="metric argument"),
            direction_semantics=declared(
                "the table prints the negated ELBO; for TALOS entropy the secondary branch is larger_is_better",
                SCRIPT,
                120,
                key="larger_is_better",
            ),
            value=direct(value, paper, key=rid, note="transcribed cell"),
            spread=direct(spread, paper, key=rid, note="transcribed \u00b1"),
            spread_form=SpreadForm(SpreadKind.K_SEM, k=3.0, ddof=0, n=len(survivors), grade=Grade.DIRECT),
            aggregation_ref=agg_id,
            transformation_refs=tuple(refs),
            comparison_set_ref=f"cmp:{env}",
            spread_label=declared(SPREAD_LABEL, PAPER5, "12", key="caption"),
        )
    )


def _cells(bundle: Bundle) -> None:
    for env, methods in ELBO_CELLS.items():
        for method, (value, spread) in methods.items():
            _add_cell(bundle, env, method, "-elbo", value, spread, "Table 8")
            twin = TABLE5_ELBO.get(env, {}).get(method)
            if twin:
                _add_cell(bundle, env, method, "-elbo", twin[0], twin[1], "Table 5")
        if env in SECONDARY_CELLS:
            column = SECONDARY_COLUMN[env]
            for method, (value, spread) in SECONDARY_CELLS[env].items():
                _add_cell(bundle, env, method, column, value, spread, "Table 8", secondary=True)


# ------------------------------------------------------------------ chain C
def _chain_c(bundle: Bundle) -> None:
    """Hyperparameter search -> the config the 10-seed evaluation actually used (§5.3)."""
    for family, (eval_family, column, suffix) in SEARCH_FAMILIES.items():
        root_dir = os.path.join(bundle.root, RESULTS, family)
        if not os.path.isdir(root_dir):
            continue
        for group in sorted(os.listdir(root_dir)):
            sdir = os.path.join(root_dir, group)
            if not os.path.isdir(sdir):
                continue
            values: list[tuple[str, float]] = []
            configs: dict[str, dict] = {}
            for f in sorted(os.listdir(sdir)):
                if not f.endswith("_config.yml"):
                    continue
                run = f[: -len("_config.yml")]
                path = os.path.join(sdir, f)
                with open(path, encoding="utf-8") as fh:
                    configs[run] = _leaves(yaml.safe_load(fh))
                v = _search_objective(os.path.join(sdir, run + ".csv"), column)
                if v is not None:
                    values.append((run, v))
            rel_dir = f"{RESULTS}/{family}/{group}"
            first_csv = os.path.join(sdir, f"{sorted(configs)[0]}.csv") if configs else ""
            bundle.add(
                ResultArtifact(
                    path=rel_dir,
                    columns=_csv_columns(first_csv) if first_csv else (),
                    produced_by=ProducedBy(
                        script=SCRIPT,
                        call_site="fetch_exp3_hyperopt",
                        invocation_args="one call per group name list",
                        grade=Grade.DERIVED,
                    ),
                )
            )
            cs_id = f"candidates:hyperopt/{family}/{group}"
            bundle.add(
                CandidateSet(
                    candidate_set_id=cs_id,
                    kind=CandidateKind.HYPERPARAMETER,
                    universe_status=UniverseStatus.PARTIAL,
                    declared_size=declared(len(values), rel_dir, key="run_*_config.yml", note="surviving search runs"),
                    surviving_size=direct(len(values), rel_dir, key="run_*.csv", note="surviving search runs"),
                    generation="adopted",
                    unobservable_sources=(
                        UnobservableSource(
                            "fetch filter: get_runs() drops runs by name and by hand-written id list",
                            direct("get_runs", SCRIPT, 11, key="filter"),
                        ),
                    ),
                    promotion_evidence=direct(
                        False, SCRIPT, 44, key="print only", note="the champion is printed, never written to a file"
                    ),
                )
            )
            if not values:
                continue
            eval_group = group + suffix
            eval_dir = os.path.join(bundle.root, RESULTS, eval_family, eval_group)
            promoted = ""
            if os.path.isdir(eval_dir):
                ecfg_path = os.path.join(eval_dir, "run_0_config.yml")
                with open(ecfg_path, encoding="utf-8") as fh:
                    ecfg = _leaves(yaml.safe_load(fh))
                matches = [
                    r
                    for r, cfg in configs.items()
                    if set(cfg) & set(ecfg) and all(cfg[k] == ecfg[k] for k in set(cfg) & set(ecfg))
                ]
                if matches:
                    promoted = min(matches, key=lambda r: dict(values)[r])
            bundle.add(
                SelectionEvent(
                    selection_id=f"sel:hyperopt/{family}/{group}",
                    kind=SelectionKind.HYPERPARAMETER,
                    candidate_set_ref=cs_id,
                    criterion=SelectionCriterion(
                        metric=direct(column, SCRIPT, 38, key="last row of the search metric"),
                        split=declared(
                            "no held-out split: the search objective is the run's own ELBO bound",
                            SCRIPT,
                            30,
                            key="history scan",
                        ),
                        direction=direct("minimize", SCRIPT, 41, key="this_elbo < best_elbo"),
                        scope=direct(f"one search group ({group})", SCRIPT, 48, key="per-group loop"),
                        tie_break=direct("strict <, so the earliest run reaching the value wins", SCRIPT, 41),
                        timing=direct("fetch time, over the runs surviving in the archive", SCRIPT, 36),
                    ),
                    candidate_values=tuple(values),
                    promoted_ref=promoted,
                    declared_policy=declared(
                        "the best run's parameters are printed and copied into the 10-seed evaluation config",
                        README,
                        162,
                        key="hyperparameter search",
                    ),
                    tie_tolerance=1e-3,
                    is_recorded=direct(False, SCRIPT, 44, key="print only"),
                    effect_on_report="decides which parameters the reported 10-seed cell is computed from",
                )
            )


def _grid_candidate_sets(bundle: Bundle) -> None:
    """Adopted vs discarded grid census, and the group-name collision between them (FM9)."""
    adopted = _grid_census(bundle.root, GRID_DIR)
    discarded = _grid_census(bundle.root, DISCARDED_DIR)
    shared = sorted(set(adopted) & set(discarded))
    samples = []
    for name in shared:
        a, d = adopted[name]["values"], discarded[name]["values"]
        common = sorted(set(a) & set(d))
        overlap = sorted(k for k in common if any(x == y for x in _flatten(a[k]) for y in _flatten(d[k])))
        samples.append(
            {
                "group": name,
                "adopted_points": adopted[name]["points"],
                "discarded_points": discarded[name]["points"],
                "adopted_key_count": len(a),
                "discarded_key_count": len(d),
                "common_key_count": len(common),
                "compared_over_common_keys": len(common) == min(len(a), len(d)),
                "value_overlap_on_common_keys": len(overlap),
                "keys_with_disjoint_values": len(common) - len(overlap),
                "overlapping_keys": overlap[:6],
            }
        )
    fully_compared = [s for s in samples if s["common_key_count"] == s["adopted_key_count"] == s["discarded_key_count"]]
    disjoint_any = [s for s in samples if s["keys_with_disjoint_values"]]
    partial_any = [s for s in samples if 0 < s["value_overlap_on_common_keys"] < s["common_key_count"]]
    collision = IdentityCollision(
        key_type="wandb.group",
        collision_count=len(shared),
        samples=tuple(samples),
        note=f"{len(shared)} of {len(discarded)} discarded group names are also adopted group names; "
        f"only {len(fully_compared)} pairs share the same key set, so the other "
        f"{len(samples) - len(fully_compared)} comparisons are taken over common keys only; "
        f"{len(disjoint_any)} pairs have a common key whose two value lists do not intersect at all and "
        f"{len(partial_any)} pairs overlap on only some of their common keys, so neither 'the same grid' "
        "nor 'an unrelated grid' is available as a conclusion",
    )
    for label, census, status, superseded in (
        ("adopted", adopted, UniverseStatus.RECOVERED, ""),
        ("discarded", discarded, UniverseStatus.PARTIAL, "adopted"),
    ):
        rel = GRID_DIR if label == "adopted" else DISCARDED_DIR
        points = sum(v["points"] for v in census.values())
        bundle.add(
            CandidateSet(
                candidate_set_id=f"candidates:exp3-{label}-grid",
                kind=CandidateKind.HYPERPARAMETER,
                universe_status=status,
                declared_size=direct(points, rel, key="grid expansion", note="parameter points"),
                surviving_size=direct(points, rel, key="grid expansion", note="parameter points"),
                generation=label,
                superseded_by=superseded,
                identity_collision=collision,
                unobservable_sources=(
                    UnobservableSource(
                        "runs discarded by the fetch filter and by wall-clock limits leave no product",
                        direct("get_runs", SCRIPT, 11, key="filter"),
                    ),
                ),
                promotion_evidence=declared(
                    "the discarded generation was abandoned after an accidental optimum at 300 components "
                    "and re-run from scratch",
                    README,
                    135,
                    key="hyperparameter search",
                ),
            )
        )


def _flatten(value):
    if isinstance(value, (list, tuple)):
        for v in value:
            yield from _flatten(v)
    else:
        yield value


# ------------------------------------------------------------------ comparison sets
def _comparison_sets(bundle: Bundle) -> None:
    """FM12 (presentation marks) and FM14 (external baseline origin)."""
    for env in ELBO_CELLS:
        members = tuple(
            (f"{env}/{m}/-elbo/Table 8", m) for m in sorted(ELBO_CELLS[env]) if ELBO_CELLS[env][m][0] != "N/A"
        )
        bundle.add(
            ComparisonSet(
                comparison_set_id=f"cmp:{env}",
                members=members,
                external_origin=direct("every member is computed inside this project", README, 132),
                presentation_rule=PresentationRule(
                    expression="bold iff a row's mean \u00b1 3\u00b7SE interval does not overlap the best row's, "
                    "using >= on the larger-is-better branch and < on the other",
                    operator=">= / <",
                    symmetric=False,
                    k_factor=3.0,
                    source=f"{SCRIPT}:55-63",
                ),
                # The printed bold spans live in the PDF layout and were never transcribed, and
                # Phase 1 does not parse PDFs: the mark is not recoverable, which is not "absent".
                observed_marks=unknown_field("the printed marks are not in the frozen text"),
            )
        )
    bundle.add(
        ComparisonSet(
            comparison_set_id="cmp:external-baselines",
            members=(("VIPS/vipsum/-elbo/Table 8", "vipsum"),),
            external_origin=declared(
                "converted from an external .mat export by a script whose input path is hardcoded to a "
                "machine that is not part of the bundle",
                "repo/evaluations/iBayesLR_results/mat_to_csv.py",
                6,
            ),
            observed_marks=unknown_field("no mark was recovered"),
        )
    )
    bundle.add(
        ResultArtifact(
            path="repo/evaluations/iBayesLR_results",
            produced_by=ProducedBy(
                script="repo/evaluations/iBayesLR_results/mat_to_csv.py",
                call_site="__main__",
                invocation_args="reads /home/oleg/... which is not in the bundle",
                grade=Grade.DECLARED,
            ),
            required_columns=("track_elbos", "track_n_fevals"),
            columns=(),
            note="external baseline conversion; the source .mat files are not in the archive",
        )
    )
    bundle.add(
        ReportedResult(
            rid="VIPS/vipsum/-elbo/Table 8",
            locus=Locus(
                artifact=PAPER8,
                page="29",
                table="Table 8",
                row="VIPS",
                column="-ELBO",
                quoted_text="external baseline column",
                quantity_key="VIPS/vipsum/-elbo",
            ),
            metric_name=direct("-elbo", "repo/evaluations/vips_comparison.py", 1),
            value=unknown_field("the baseline number is not in the frozen text transcription"),
            spread=unknown_field("the baseline interval is not in the frozen text transcription"),
            comparison_set_ref="cmp:external-baselines",
            not_aggregated_reason="the cell is an external baseline converted from a .mat export that is not "
            "part of the bundle, so no member of this project produces it",
        )
    )


def load_gmmvi_bundle(root: str) -> Bundle:
    """Build the GMMVI evidence bundle from the frozen archive at `root`."""
    bundle = Bundle(project="GMMVI")
    bundle.root = os.path.abspath(root)
    _add_shared_transforms(bundle)
    _cells(bundle)
    _chain_c(bundle)
    _grid_candidate_sets(bundle)
    _comparison_sets(bundle)
    return bundle
