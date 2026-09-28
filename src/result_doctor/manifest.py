"""The generic manifest entry point: Phase 2 §7's contract, implemented.

A project Result Doctor has never seen enters through one YAML file plus the artifacts
it points at, and lands in the same eight-object bundle the frozen adapters build:

```text
result-doctor.yml -> Bundle -> RD001-RD008
```

Two doors only (Phase 2 §6). A fact is either read back through a locator inside the
project root (OBSERVED -> Grade.DIRECT) or asserted by the user in the manifest
(DECLARED). Everything else is UNKNOWN. This module assigns no grade the user did not
earn: it never reads a scientific fact out of a file name, a directory name, a group
name or a count of runs, and it never lowers an authored value to DIRECT.

Structural problems raise `ManifestError`; insufficient evidence never does (Phase 2
§12). A manifest that parses is auditable, even when almost everything in it is UNKNOWN.

Six shapes a first-time author always asks about (Phase 5, from the real onboarding):

* `aggregate:` carries only `center` / `reason` / `none` / `ref`. `members`, `member_rule`,
  `spread`, `exclusions` and `dispersion_statement` are its siblings at cell level.
* `observed:` is read back from a file inside `root:` and grades DIRECT; `declared:` is what
  the author asserts and grades DECLARED; `unknown:` (or the field being absent) grades
  UNKNOWN and is a normal thing to write, not an error.
* A printed cell is one fragment. `{path, line}` returns the whole line, so a value locator
  needs `text: "<the printed value>"`; the loader refuses instead of comparing the row label.
* A `quantity:` key is how RD008 finds the same quantity in two products. Two rows of one
  table may not share it: scope the key to the row (`acc/cifar-resnet10`, not `acc`).
* A member's `identity:` door may leave out `path:`; it is then read against that member's
  own file. The value, the SourceRef and the grade are exactly what quoting the path again
  produced, so this is shorter writing, not a stronger claim. Omitting `identity:` entirely
  still grades UNKNOWN.
* A size is `{value: N, statement: "what N counts"}` plus optional `note:` / `supported_by:`
  companions. Companions describe the number; they are not a second door.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from .bundle import Bundle
from .compute import STAGES
from .evidence import EvidenceField, Grade, SourceRef
from .schema import (
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
from .status import UniverseStatus

SCHEMA_VERSION = 1
MANIFEST_NAME = "result-doctor.yml"

HEADER_KEYS = ("schema_version", "project", "root")
SECTIONS = (
    "artifacts",
    "evidence",
    "transformations",
    "aggregations",
    "candidate_sets",
    "selection_events",
    "reported_results",
    "comparisons",
)

#: A printed cell is `center <sep> spread`; Phase 0 saw both spellings of the separator.
CELL_SEPARATORS = ("±", "+/-")

CENTERS = ("mean", "median")
SPREAD_KINDS = ("none", "std", "sem", "k_sem")
RENDER_MODES = ("fixed", "str_round")
UNIVERSE_TOKENS = ("unknown", "complete", "recovered", "partial", "declared_only", "unrecoverable")
#: Steps `compute.apply_stage` does not execute (Phase 2 §17). Letting one stand where it
#: would change a number is the false-pass risk, so the generic contract refuses it.
STEPS_COMPUTED = ("sign_flip", "scale", "sum_of_part", "identity")
STEPS_NOT_APPLIED = ("round", "delta", "best_of_n", "truncate_window")
CRITERION_FIELDS = ("metric", "split", "direction", "scope", "tie_break", "timing")
LOCATOR_KEYS = ("path", "line", "column", "row", "key", "text")
DOOR_KEYS = ("observed", "declared", "unknown")
#: A reference addresses a section by index or by id; the prefix is how the id is stored.
ID_PREFIX = {
    "aggregation": "agg",
    "transformation chain": "t",
    "candidate set": "cand",
    "selection event": "sel",
    "comparison set": "cmp",
}

E_YAML = "E_YAML"
E_ROOT = "E_ROOT"
E_SCHEMA_VERSION = "E_SCHEMA_VERSION"
E_TOP_LEVEL = "E_TOP_LEVEL"
E_UNKNOWN_KEY = "E_UNKNOWN_KEY"
E_MISSING_FIELD = "E_MISSING_FIELD"
E_DUPLICATE_ID = "E_DUPLICATE_ID"
E_UNRESOLVED_REF = "E_UNRESOLVED_REF"
E_BAD_ENUM = "E_BAD_ENUM"
E_BAD_FIELD = "E_BAD_FIELD"
E_BAD_DIRECTION = "E_BAD_DIRECTION"
E_STEP_NOT_APPLIED = "E_STEP_NOT_APPLIED"
E_RENDER_STEP = "E_RENDER_STEP"
E_PATH_OUTSIDE_ROOT = "E_PATH_OUTSIDE_ROOT"
E_ARTIFACT_MISSING = "E_ARTIFACT_MISSING"
E_LOCATOR_KEYS = "E_LOCATOR_KEYS"
E_LOCATOR_LINE = "E_LOCATOR_LINE"
E_LOCATOR_TEXT = "E_LOCATOR_TEXT"
E_LOCATOR_COLUMN = "E_LOCATOR_COLUMN"
E_LOCATOR_ROW = "E_LOCATOR_ROW"
E_LOCATOR_KEY = "E_LOCATOR_KEY"
E_NOT_A_NUMBER = "E_NOT_A_NUMBER"
E_TYPE = "E_TYPE"
E_UNIVERSE_EVIDENCE = "E_UNIVERSE_EVIDENCE"
E_MARK_DERIVATION = "E_MARK_DERIVATION"
E_CONFLICTING_REF = "E_CONFLICTING_REF"


class ManifestError(ValueError):
    """A manifest that cannot be read as a contract. Never raised for missing evidence."""

    def __init__(self, code: str, where: str, problem: str) -> None:
        super().__init__(f"{code} at {where}: {problem}")
        self.code = code
        self.where = where
        self.problem = problem


def _token(value: Any) -> str:
    return str(value).strip().lower()


def _split_cell(text: str) -> tuple[str, str]:
    """`"94.12 ± 0.24"` -> `("94.12", "0.24")`; a cell with no separator has no dispersion."""
    for sep in CELL_SEPARATORS:
        if sep in text:
            left, right = text.split(sep, 1)
            spread = right.strip()
            if spread.startswith("+"):
                spread = spread[1:]
            return left.strip(), spread
    return text.strip(), ""


class _Manifest:
    def __init__(self, path: str, data: dict[str, Any]) -> None:
        self.manifest = path
        self.data = data
        self.project = str(data.get("project") or "")
        directory = os.path.dirname(os.path.abspath(path)) or "."
        self.root = Path(os.path.abspath(os.path.join(directory, str(data.get("root") or "."))))
        self.bundle = Bundle(project=self.project, root=str(self.root))
        self.artifact_paths: set[str] = set()
        self.agg_ids: set[str] = set()
        self.agg_list: list[str] = []
        self.labels: set[str] = set()
        self.quantities: dict[str, list[list[str]]] = {}
        self.cand_ids: list[str] = []
        self.sel_ids: list[str] = []
        self.registry: dict[str, dict[str, Any]] = {}
        self.chains: dict[str, tuple[str, ...]] = {}
        self.members_of_agg: dict[str, list[str]] = {}
        self.comparison_ids: list[str] = []

    # ------------------------------------------------------------------ plumbing
    def err(self, code: str, where: str, problem: str) -> ManifestError:
        return ManifestError(code, where, problem)

    def mloc(self, where: str) -> str:
        """Phase 2 §9: every authored value points back into the manifest."""
        return f"{MANIFEST_NAME}#{where}"

    def check_keys(self, mapping: dict[str, Any], allowed: tuple[str, ...], where: str) -> None:
        extra = sorted(set(mapping) - set(allowed))
        if extra:
            raise self.err(
                E_UNKNOWN_KEY, where, f"key(s) {extra} are not part of the contract; allowed: {list(allowed)}"
            )

    def need(self, mapping: dict[str, Any], key: str, where: str) -> Any:
        if key not in mapping or mapping[key] is None:
            raise self.err(E_MISSING_FIELD, where, f"{key} is required")
        return mapping[key]

    def enum(self, value: Any, allowed: tuple[str, ...], where: str, name: str) -> str:
        token = _token(value)
        if token not in allowed:
            raise self.err(E_BAD_ENUM, where, f"{name}={value!r} is not one of {list(allowed)}")
        return token

    def number(self, value: Any, where: str, name: str, integer: bool = False) -> float | int:
        if isinstance(value, bool):
            raise self.err(E_NOT_A_NUMBER, where, f"{name}={value!r} is not a number")
        if isinstance(value, (int, float)):
            out: float | int = value
        else:
            try:
                out = int(str(value).strip()) if integer else float(str(value).strip())
            except (TypeError, ValueError):
                raise self.err(E_NOT_A_NUMBER, where, f"{name}={value!r} is not a number") from None
        return int(out) if integer else float(out)

    # ------------------------------------------------------------------ path boundary
    def under_root(self, rel: Any, where: str) -> Path:
        text = str(rel)
        if not text.strip():
            raise self.err(E_MISSING_FIELD, where, "an empty path is not an artifact reference")
        normalized = text.replace("\\", "/")
        if os.path.isabs(normalized) or re.match(r"^[A-Za-z]:", normalized) or normalized.startswith("~"):
            raise self.err(E_PATH_OUTSIDE_ROOT, where, f"{text!r} is absolute; artifact paths are relative to root")
        if ".." in normalized.split("/"):
            raise self.err(E_PATH_OUTSIDE_ROOT, where, f"{text!r} climbs out of root with '..'")
        target = (self.root / normalized).resolve()
        if target != self.root and self.root not in target.parents:
            raise self.err(E_PATH_OUTSIDE_ROOT, where, f"{text!r} resolves outside root {self.root}")
        if not target.is_file():
            raise self.err(E_ARTIFACT_MISSING, where, f"{text!r} does not exist under root")
        return target

    # ------------------------------------------------------------------ locators
    def read_locator(self, body: Any, where: str) -> tuple[Any, SourceRef]:
        """Deterministically read one value: column+row, json key, line, or quoted text."""
        if not isinstance(body, dict):
            raise self.err(E_LOCATOR_KEYS, where, "observed: must be a mapping of locator keys")
        self.check_keys(body, LOCATOR_KEYS, where)
        rel = str(self.need(body, "path", where))
        path = self.under_root(rel, where)
        if "column" in body:
            return self._read_csv(path, rel, body, where)
        if "key" in body:
            return self._read_json(path, rel, body, where)
        if "line" in body:
            return self._read_line(path, rel, body, where)
        if "text" in body:
            fragment = str(body["text"])
            content = path.read_text(encoding="utf-8")
            if fragment not in content:
                raise self.err(E_LOCATOR_TEXT, where, f"the quoted fragment {fragment!r} is not in {rel}")
            return fragment, SourceRef(rel, key=f'text:"{fragment}"')
        raise self.err(E_LOCATOR_KEYS, where, f"a locator needs one of column/key/line/text, got {sorted(body)}")

    def _read_csv(self, path: Path, rel: str, body: dict[str, Any], where: str) -> tuple[Any, SourceRef]:
        column = str(self.need(body, "column", where))
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = list(reader.fieldnames or ())
            if column not in header:
                raise self.err(E_LOCATOR_COLUMN, where, f"{rel} has no column {column!r}; header is {list(header)}")
            rows = list(reader)
        if not rows:
            raise self.err(E_LOCATOR_ROW, where, f"{rel} carries a header but no data rows")
        spec = self.need(body, "row", where)
        index = len(rows) - 1 if _token(spec) == "last" else int(self.number(spec, where, "row", integer=True)) - 1
        if not 0 <= index < len(rows):
            raise self.err(E_LOCATOR_ROW, where, f"row {spec!r} is outside {rel}, which has {len(rows)} data rows")
        return rows[index][column], SourceRef(rel, key=f"column:{column}", line=index + 1)

    def _read_json(self, path: Path, rel: str, body: dict[str, Any], where: str) -> tuple[Any, SourceRef]:
        pointer = str(self.need(body, "key", where))
        node: Any = json.loads(path.read_text(encoding="utf-8"))
        for part in [p for p in pointer.split("/") if p]:
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                raise self.err(E_LOCATOR_KEY, where, f"{rel} has no key {pointer!r}")
        return node, SourceRef(rel, key=f"key:{pointer}")

    def _read_line(self, path: Path, rel: str, body: dict[str, Any], where: str) -> tuple[Any, SourceRef]:
        line = int(self.number(self.need(body, "line", where), where, "line", integer=True))
        lines = path.read_text(encoding="utf-8").splitlines()
        if not 1 <= line <= len(lines):
            raise self.err(E_LOCATOR_LINE, where, f"{rel} has {len(lines)} lines, {line} is not one of them")
        text = lines[line - 1]
        if "text" in body:
            fragment = str(body["text"])
            if fragment not in text:
                raise self.err(
                    E_LOCATOR_TEXT,
                    where,
                    f"line {line} of {rel} is {text!r}, which does not contain {fragment!r}",
                )
            return fragment, SourceRef(rel, key=f'text:"{fragment}"', line=line)
        return text.strip(), SourceRef(rel, line=line)

    # ------------------------------------------------------------------ the two doors
    def field(self, raw: Any, where: str, name: str) -> EvidenceField:
        """OBSERVED, DECLARED, or UNKNOWN. There is no fourth shape and no other grade."""
        if raw is None:
            return EvidenceField(None, Grade.UNKNOWN, (SourceRef(self.mloc(where), note=f"no {name} is declared"),))
        if not isinstance(raw, dict):
            return self._declared(raw, where, name)
        if "via" in raw:
            entry = self.registry.get(str(raw["via"]))
            if entry is None:
                raise self.err(
                    E_UNRESOLVED_REF, where, f"{name} cites evidence id {raw['via']!r}, which is not declared"
                )
            raw = {**entry, **{k: v for k, v in raw.items() if k != "via"}}
        doors = [k for k in DOOR_KEYS if k in raw]
        extra = sorted(set(raw) - set(doors) - {"via", "supported_by", "note"})
        if extra:
            raise self.err(E_UNKNOWN_KEY, where, f"{name} carries unknown key(s) {extra}")
        if len(doors) != 1:
            raise self.err(
                E_BAD_FIELD,
                where,
                f"{name} must be exactly one of observed:/declared:/unknown:, got {sorted(raw) or 'nothing'}",
            )
        door = doors[0]
        body = raw[door]
        note = str(raw.get("note") or "")
        support: tuple[SourceRef, ...] = ()
        if "supported_by" in raw:
            _, src = self.read_locator(raw["supported_by"], f"{where}/supported_by")
            support = (src,)
        if door == "unknown":
            reason = body if isinstance(body, str) else note or f"{name} is not recorded"
            return EvidenceField(None, Grade.UNKNOWN, (SourceRef(self.mloc(where), note=str(reason)),), str(reason))
        if door == "declared":
            return self._declared(body, where, name, note, support)
        value, src = self.read_locator(body, f"{where}/observed")
        return EvidenceField(value, Grade.DIRECT, (src, *support), note)

    def _declared(
        self, body: Any, where: str, name: str, note: str = "", support: tuple[SourceRef, ...] = ()
    ) -> EvidenceField:
        value: Any = body
        by = ""
        if isinstance(body, dict):
            self.check_keys(body, ("by", "statement", "value", "note"), where)
            if not set(body) & {"value", "statement"}:
                raise self.err(E_BAD_FIELD, where, f"{name} declares nothing: declared: needs a value or a statement")
            by = str(body.get("by") or "")
            value = body.get("value", body.get("statement", ""))
            note = note or str(body.get("note") or "")
        sources = (SourceRef(self.mloc(where), key=f"declared:{name}", note=by or note), *support)
        return EvidenceField(value, Grade.DECLARED, sources, note)

    def door_of(self, mapping: dict[str, Any]) -> dict[str, Any] | None:
        """Pull the door keys (and their companions) out of a mixed section entry."""
        picked = {k: mapping[k] for k in mapping if k in (*DOOR_KEYS, "supported_by", "note", "via")}
        return picked or None

    def number_field(self, raw: Any, where: str, name: str, integer: bool = False) -> EvidenceField:
        ef = self.field(raw, where, name)
        if ef.grade is Grade.UNKNOWN:
            return ef
        return EvidenceField(self.number(ef.value, where, name, integer=integer), ef.grade, ef.sources, ef.note)

    # ------------------------------------------------------------------ printed cell
    def _cell_field(self, raw: Any, where: str) -> tuple[EvidenceField, EvidenceField]:
        if isinstance(raw, dict):
            body = raw.get("observed")
            if isinstance(body, dict) and "line" in body and "text" not in body:
                #: G1 (Phase 4 §11): a table row line is `label    value`; reading it whole would compare the
                #: label as the printed cell and turn a correct number into a false FAIL. Quote the fragment.
                raise self.err(
                    E_LOCATOR_TEXT,
                    f"{where}/observed",
                    f"a printed cell is one fragment, not the whole line it sits on: add "
                    f'text: "<the printed value>" to {{path: {body.get("path")!r}, line: {body["line"]}}}. '
                    "Without it the row label would enter the recomputation comparison.",
                )
        ef = self.field(raw, where, "value")
        if ef.grade is Grade.UNKNOWN:
            raise self.err(
                E_MISSING_FIELD, where, "value is required: a reported result without a printed cell is empty"
            )
        value_text = ef.value if isinstance(ef.value, str) else str(ef.value)
        center_text, spread_text = _split_cell(value_text)
        value = EvidenceField(center_text, ef.grade, ef.sources, ef.note)
        spread = (
            EvidenceField(None, Grade.UNKNOWN, (SourceRef(self.mloc(where), note="the printed cell carries no +/-"),))
            if not spread_text
            else EvidenceField(spread_text, ef.grade, ef.sources, ef.note)
        )
        return value, spread

    # ------------------------------------------------------------------ sections
    def run(self) -> Bundle:
        if not self.root.is_dir():
            raise self.err(E_ROOT, "root", f"{self.root} is not a directory")
        self._registry()
        self._collect_ids()
        self._artifacts()
        self._transformations()
        self._aggregations()
        self._candidate_sets()
        self._selection_events()
        self._cells()
        self._comparisons()
        return self.bundle

    def _collect_ids(self) -> None:
        """A cell may name its comparison set before that set is written (Phase 2 §7 order).

        Only the ids are collected here; the set itself is still built from its own entry.
        """
        for i, entry in enumerate(self._section("comparisons")):
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, f"comparisons[{i}]", "a comparison set must be a mapping")
            self.comparison_ids.append(f"cmp:{entry['id']}" if "id" in entry else f"cmp:{i}")

    def _registry(self) -> None:
        for i, entry in enumerate(self._section("evidence")):
            where = f"evidence[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, where, "an evidence entry must be a mapping")
            eid = str(self.need(entry, "id", where))
            if eid in self.registry:
                raise self.err(E_DUPLICATE_ID, where, f"evidence id {eid!r} is declared twice")
            self.check_keys(entry, ("id", *DOOR_KEYS, "supported_by", "note"), where)
            self.registry[eid] = {k: v for k, v in entry.items() if k != "id"}

    def _section(self, name: str) -> list[Any]:
        raw = self.data.get(name) or ()
        if isinstance(raw, dict):
            raise self.err(E_TYPE, name, f"{name} must be a list of entries, not a mapping")
        return list(raw)

    def _artifacts(self) -> None:
        for i, entry in enumerate(self._section("artifacts")):
            where = f"artifacts[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, where, "an artifact entry must be a mapping")
            self.check_keys(entry, ("path", "columns", "producer", "writes_columns", "supersedes", "note"), where)
            rel = str(self.need(entry, "path", where))
            if rel in self.artifact_paths:
                raise self.err(E_DUPLICATE_ID, where, f"artifact {rel!r} is declared twice")
            path = self.under_root(rel, where)
            columns: tuple[str, ...] = ()
            if path.suffix.lower() == ".csv":
                with open(path, newline="", encoding="utf-8-sig") as fh:
                    columns = tuple(csv.DictReader(fh).fieldnames or ())
            if "columns" in entry:
                authored = tuple(str(c) for c in entry["columns"] or ())
                if not columns:
                    columns = authored
                elif set(authored) != set(columns):
                    raise self.err(
                        E_TYPE,
                        where,
                        f"declared columns {list(authored)} are not the header read from {rel}: {list(columns)}",
                    )
            produced = ProducedBy()
            producer = entry.get("producer")
            if producer is not None:
                if not isinstance(producer, dict):
                    raise self.err(E_TYPE, f"{where}/producer", "producer must be a mapping")
                self.check_keys(
                    producer,
                    ("script", "call_site", "invocation_args", *DOOR_KEYS, "supported_by", "note", "via"),
                    where,
                )
                ef = self.field(self.door_of(producer), f"{where}/producer", "producer")
                produced = ProducedBy(
                    script=str(producer.get("script") or ef.value or ""),
                    call_site=str(producer.get("call_site") or ""),
                    invocation_args=str(producer.get("invocation_args") or ""),
                    grade=ef.grade,
                )
            self.artifact_paths.add(rel)
            self.bundle.add(
                ResultArtifact(
                    path=rel,
                    columns=columns,
                    produced_by=produced,
                    required_columns=tuple(str(c) for c in entry.get("writes_columns") or ()),
                    superseded_from=tuple(str(s) for s in entry.get("supersedes") or ()),
                    note=str(entry.get("note") or ""),
                )
            )

    def _steps(self, entries: list[Any], target: str, where: str, prefix: str = "") -> tuple[str, ...]:
        refs: list[str] = []
        for i, entry in enumerate(entries):
            step_where = f"{where}/steps[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, step_where, "a transformation step must be a mapping")
            self.check_keys(
                entry,
                (
                    "step",
                    "stage",
                    "applied_at",
                    "factor",
                    "mode",
                    "digits",
                    "parts",
                    "conditional",
                    "condition",
                    "declared_source",
                    "observed_source",
                    "statement",
                    *DOOR_KEYS,
                    "supported_by",
                    "note",
                    "via",
                ),
                step_where,
            )
            name = self.enum(
                self.need(entry, "step", step_where), tuple(t.value for t in TransformStep), step_where, "step"
            )
            stage = self.enum(self.need(entry, "stage", step_where), STAGES, step_where, "stage")
            if name in STEPS_NOT_APPLIED:
                raise self.err(
                    E_STEP_NOT_APPLIED,
                    step_where,
                    f"step {name!r} is not applied by the computation layer, so declaring it here would claim a "
                    "transformation that never happens (Phase 2 §17)",
                )
            if stage == "render" and name != "format":
                raise self.err(E_RENDER_STEP, step_where, f"only a format step can render a cell, got {name!r}")
            if name == "format" and stage != "render":
                raise self.err(
                    E_RENDER_STEP,
                    step_where,
                    f"a format step renders the printed cell; at stage {stage!r} it would claim a rounding the "
                    "computation layer does not perform (Phase 2 §17)",
                )
            params: dict[str, object] = {"stage": stage}
            if name == "format":
                params["mode"] = self.enum(
                    self.need(entry, "mode", step_where), RENDER_MODES, step_where, "format.mode"
                )
                params["digits"] = int(
                    self.number(self.need(entry, "digits", step_where), step_where, "format.digits", True)
                )
            elif name == "scale":
                params["factor"] = float(
                    self.number(self.need(entry, "factor", step_where), step_where, "scale.factor")
                )
            elif name == "sum_of_part":
                params["parts"] = [
                    float(self.number(v, step_where, "sum_of_part.part")) for v in (entry.get("parts") or ())
                ]
            if entry.get("conditional") is True:
                params["conditional"] = True
            for key in ("declared_source", "observed_source"):
                if key in entry:
                    params[key] = str(entry[key])
            applied = _token(entry.get("applied_at", "unknown"))
            if applied not in tuple(a.value for a in AppliedAt):
                raise self.err(
                    E_BAD_ENUM, step_where, f"applied_at={entry['applied_at']!r} is not code/script/manual/unknown"
                )
            door = self.door_of(entry)
            if door:
                ef = self.field(door, step_where, name)
                grade, sources = ef.grade, ef.sources
            else:
                grade, sources = Grade.DECLARED, (SourceRef(self.mloc(step_where), key=f"step:{name}"),)
            transform_id = f"{prefix}t:{target}:{i}"
            if transform_id in self.bundle.transformations:
                raise self.err(E_DUPLICATE_ID, step_where, f"transformation id {transform_id!r} already exists")
            self.bundle.add(
                Transformation(
                    transform_id=transform_id,
                    step=TransformStep(name),
                    applied_at=AppliedAt(applied),
                    target=target,
                    params=params,
                    condition=self.field(entry.get("condition"), f"{step_where}/condition", "condition"),
                    grade=grade,
                    sources=sources,
                    note=str(entry.get("statement") or entry.get("note") or ""),
                )
            )
            refs.append(transform_id)
        return tuple(refs)

    def _transformations(self) -> None:
        for i, entry in enumerate(self._section("transformations")):
            where = f"transformations[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, where, "a transformation entry must be a mapping")
            self.check_keys(entry, ("id", "target", "steps"), where)
            tid = str(entry["id"]) if "id" in entry else str(i)
            group_id = f"t:{tid}"
            if group_id in self.chains:
                raise self.err(E_DUPLICATE_ID, where, f"transformation chain id {tid!r} is declared twice")
            self.chains[group_id] = self._steps(
                list(entry.get("steps") or ()), str(entry.get("target") or f"chain:{tid}"), where, prefix=f"t{tid}:"
            )

    def _spread_form(self, entry: dict[str, Any], where: str, n: int) -> SpreadForm:
        raw = entry.get("spread")
        if raw is None:
            return SpreadForm(n=n)
        if not isinstance(raw, dict):
            raise self.err(E_TYPE, f"{where}/spread", "spread must be a mapping of kind/ddof/k")
        self.check_keys(raw, ("kind", "ddof", "k"), f"{where}/spread")
        kind = self.enum(self.need(raw, "kind", f"{where}/spread"), SPREAD_KINDS, f"{where}/spread", "spread.kind")
        ddof = int(self.number(raw.get("ddof", 0), f"{where}/spread", "spread.ddof", True))
        if ddof not in (0, 1):
            raise self.err(E_BAD_ENUM, f"{where}/spread", f"ddof={ddof} is not 0 or 1")
        if kind == "k_sem" and "k" not in raw:
            raise self.err(E_MISSING_FIELD, f"{where}/spread", "a k_sem spread must state k")
        k = float(self.number(raw.get("k", 1), f"{where}/spread", "spread.k"))
        return SpreadForm(SpreadKind(kind), k=k, ddof=ddof, n=n, grade=Grade.DECLARED)

    def _aggregation(self, entry: dict[str, Any], agg_id: str, where: str) -> str:
        if agg_id in self.bundle.aggregations:
            raise self.err(E_DUPLICATE_ID, where, f"aggregation id {agg_id!r} is declared twice")
        self._members(list(entry.get("members") or ()), agg_id, where)
        member_rule = MemberRule(MemberRuleKind.UNDECLARED)
        rule = entry.get("member_rule")
        if rule is not None:
            if not isinstance(rule, dict):
                raise self.err(E_TYPE, f"{where}/member_rule", "member_rule must be a mapping")
            self.check_keys(
                rule, ("kind", "statement", *DOOR_KEYS, "supported_by", "note", "via"), f"{where}/member_rule"
            )
            kind = self.enum(
                self.need(rule, "kind", f"{where}/member_rule"),
                tuple(m.value for m in MemberRuleKind),
                f"{where}/member_rule",
                "member_rule.kind",
            )
            ef = self.field(self.door_of(rule), f"{where}/member_rule", "member rule")
            member_rule = MemberRule(
                MemberRuleKind(kind),
                expression=str(rule.get("statement") or ef.value or ""),
                grade=ef.grade,
                source=ef.sources[0].path if ef.sources else self.mloc(f"{where}/member_rule"),
            )
        exclusions: list[Exclusion] = []
        for i, ex in enumerate(entry.get("exclusions") or ()):
            ex_where = f"{where}/exclusions[{i}]"
            if not isinstance(ex, dict):
                raise self.err(E_TYPE, ex_where, "an exclusion must be a mapping")
            self.check_keys(ex, ("member", "reason", "criterion_recomputable", "statement", "via"), ex_where)
            member_id = self._member_ref(agg_id, str(self.need(ex, "member", ex_where)), ex_where)
            door = self.door_of(ex)
            statement = str(ex.get("statement") or "")
            if door:
                listed = self.field(door, ex_where, "exclusion")
            else:
                listed = EvidenceField(
                    statement or None,
                    Grade.DECLARED if statement else Grade.UNKNOWN,
                    (SourceRef(self.mloc(ex_where), key="declared:exclusion", note=statement),),
                    statement,
                )
            reason = self.field(ex.get("reason"), f"{ex_where}/reason", "exclusion reason")
            exclusions.append(
                Exclusion(
                    member_id=member_id,
                    listed=listed,
                    reason_grade=reason.grade,
                    criterion_recomputable=bool(ex.get("criterion_recomputable") is True),
                    note=statement or reason.note,
                )
            )
        center = self.enum(self.need(entry, "center", f"{where}/aggregate"), CENTERS, f"{where}/aggregate", "center")
        n = len(self.members_of_agg.get(agg_id, ()))
        self.bundle.add(
            Aggregation(
                aggregation_id=agg_id,
                center=center,
                dispersion_expression=str(entry.get("dispersion_statement") or ""),
                spread_form=self._spread_form(entry, where, n),
                member_rule=member_rule,
                member_ids=tuple(self.members_of_agg.get(agg_id, ())),
                exclusions=tuple(exclusions),
            )
        )
        self.agg_ids.add(agg_id)
        self.agg_list.append(agg_id)
        return agg_id

    def _aggregations(self) -> None:
        for i, entry in enumerate(self._section("aggregations")):
            where = f"aggregations[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, where, "an aggregation entry must be a mapping")
            self.check_keys(
                entry, ("id", "center", "spread", "members", "member_rule", "exclusions", "dispersion_statement"), where
            )
            self._aggregation(entry, f"agg:{entry['id']}" if "id" in entry else f"agg:{i}", where)

    def _member_ref(self, agg_id: str, ref: str, where: str) -> str:
        for candidate in (f"{agg_id}/{ref}", ref):
            if candidate in self.bundle.members:
                return candidate
        known = sorted(m.split("/", 1)[-1] for m in self.members_of_agg.get(agg_id, ()))
        raise self.err(E_UNRESOLVED_REF, where, f"member {ref!r} is not one of the declared members {known}")

    def _inherit_member_path(self, raw: Any, member_path: str) -> Any:
        """UX1: an identity door that names no path is read against the member's own file."""
        if not member_path or not isinstance(raw, dict):
            return raw
        lowered = set(LOCATOR_KEYS) - {"path"}
        out: dict[str, Any] = {}
        for key, body in raw.items():
            if (
                key in (*DOOR_KEYS, "supported_by")
                and key != "unknown"
                and isinstance(body, dict)
                and "path" not in body
                and set(body) & lowered
            ):
                out[key] = {**body, "path": member_path}
            else:
                out[key] = body
        return out

    def _members(self, entries: list[Any], agg_id: str, where: str) -> None:
        ids: list[str] = []
        for i, entry in enumerate(entries):
            m_where = f"{where}/members[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, m_where, "a member must be a mapping")
            self.check_keys(
                entry, ("name", "value", "identity", "selector", "excluded", *LOCATOR_KEYS, "via", "note"), m_where
            )
            locator: tuple[Any, SourceRef] | None = None
            if "path" in entry:
                body = {k: v for k, v in entry.items() if k in LOCATOR_KEYS}
                locator = self.read_locator(body, m_where)
            if "value" in entry and locator is not None:
                raise self.err(
                    E_BAD_FIELD, m_where, "a member carries either an inline value: or a locator, never both"
                )
            if "value" in entry:
                ef = self.number_field(entry["value"], m_where, "member value")
            elif locator is not None:
                raw_value, src = locator
                ef = EvidenceField(self.number(raw_value, m_where, "member value"), Grade.DIRECT, (src,), "")
            else:
                raise self.err(
                    E_MISSING_FIELD,
                    m_where,
                    "a member needs a locator (path with column/row, key, line or text) or a value:",
                )
            name = str(entry.get("name") or f"m{i}")
            member_id = f"{agg_id}/{name}"
            if member_id in self.bundle.members:
                raise self.err(E_DUPLICATE_ID, m_where, f"member id {member_id!r} is declared twice")
            artifact = str(entry.get("path") or "")
            declared_artifact = artifact if artifact in self.artifact_paths else ""
            kind, grade = SelectorKind.UNKNOWN, Grade.UNKNOWN
            if locator is not None and _token(entry.get("row")) == "last":
                kind, grade = SelectorKind.LAST_ROW, Grade.DECLARED
            claimed = entry.get("selector")
            if claimed is not None:
                if not isinstance(claimed, dict):
                    raise self.err(E_TYPE, f"{m_where}/selector", "selector must be a mapping")
                self.check_keys(claimed, ("kind", *DOOR_KEYS, "supported_by", "note", "via"), f"{m_where}/selector")
                kind = SelectorKind(
                    self.enum(
                        self.need(claimed, "kind", f"{m_where}/selector"),
                        tuple(s.value for s in SelectorKind),
                        f"{m_where}/selector",
                        "selector.kind",
                    )
                )
                grade = self.field(self.door_of(claimed), f"{m_where}/selector", "selector").grade
            self.bundle.add(
                AggregationMember(
                    member_id=member_id,
                    run_ref=RunRef(
                        project=self.project,
                        family_key=agg_id,
                        run_name=name,
                        artifact_ref=declared_artifact,
                        external_id=self.field(
                            self._inherit_member_path(entry.get("identity"), artifact), m_where, "identity"
                        ),
                    ),
                    selector=ObservationSelector(
                        kind=kind,
                        column=str(entry.get("column") or ""),
                        grade=grade,
                        source=artifact or self.mloc(m_where),
                    ),
                    observed_value=ef,
                    artifact_ref=declared_artifact,
                    excluded=entry.get("excluded") is True,
                )
            )
            ids.append(member_id)
        self.members_of_agg[agg_id] = ids

    def _candidate_sets(self) -> None:
        for i, entry in enumerate(self._section("candidate_sets")):
            where = f"candidate_sets[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, where, "a candidate set entry must be a mapping")
            self.check_keys(
                entry,
                (
                    "id",
                    "kind",
                    "members",
                    "universe",
                    "universe_evidence",
                    "declared_size",
                    "surviving_size",
                    "unobservable",
                    "promotion",
                    "statement",
                ),
                where,
            )
            cid = f"cand:{entry['id']}" if "id" in entry else f"cand:{i}"
            if cid in self.bundle.candidate_sets:
                raise self.err(E_DUPLICATE_ID, where, f"candidate set id {entry['id']!r} is declared twice")
            self.cand_ids.append(cid)
            kind = CandidateKind(
                self.enum(
                    self.need(entry, "kind", where), tuple(k.value for k in CandidateKind), where, "candidate_sets.kind"
                )
            )
            refs = [str(r) for r in (entry.get("members") or ())]
            dupes = sorted({r for r in refs if refs.count(r) > 1})
            collision = (
                IdentityCollision(
                    key_type="manifest candidate ref",
                    collision_count=len(dupes),
                    samples=tuple({"ref": d, "listed_times": refs.count(d)} for d in dupes),
                    note=(
                        "the manifest lists the same candidate ref more than once; whether the listings are the same "
                        "candidate or two search generations is not determined here"
                    ),
                )
                if dupes
                else None
            )
            universe = _token(entry.get("universe", "unknown"))
            if universe not in UNIVERSE_TOKENS:
                raise self.err(
                    E_BAD_ENUM, where, f"universe={entry['universe']!r} is not one of {list(UNIVERSE_TOKENS)}"
                )
            evidence = self.field(entry.get("universe_evidence"), f"{where}/universe_evidence", "universe evidence")
            unobservable = tuple(
                self._unobservable(u, f"{where}/unobservable[{j}]")
                for j, u in enumerate(entry.get("unobservable") or ())
            )
            if universe == "unrecoverable" and not unobservable:
                raise self.err(
                    E_UNIVERSE_EVIDENCE,
                    where,
                    "universe: unrecoverable is an affirmative claim and needs unobservable: entries carrying evidence",
                )
            status = {
                "unknown": UniverseStatus.UNKNOWN,
                "complete": UniverseStatus.RECOVERED,
                "recovered": UniverseStatus.RECOVERED,
                "partial": UniverseStatus.PARTIAL,
                "declared_only": UniverseStatus.DECLARED_ONLY,
                "unrecoverable": UniverseStatus.UNRECOVERABLE,
            }[universe]
            if universe in ("complete", "recovered") and not evidence.is_known:
                status = UniverseStatus.DECLARED_ONLY
            declared_size = self._size(entry.get("declared_size"), f"{where}/declared_size")
            if declared_size.grade is Grade.UNKNOWN and refs:
                #: Listing members is never a size claim about the universe; the count of
                #: what was listed is recorded as a declaration, and RD004 keeps it apart
                #: from the surviving product count.
                declared_size = EvidenceField(
                    len(refs), Grade.DECLARED, (SourceRef(self.mloc(f"{where}/members")),), "listed candidates"
                )
            self.bundle.add(
                CandidateSet(
                    candidate_set_id=cid,
                    kind=kind,
                    universe_status=status,
                    declared_size=declared_size,
                    surviving_size=self._size(entry.get("surviving_size"), f"{where}/surviving_size"),
                    identity_collision=collision,
                    unobservable_sources=unobservable,
                    promotion_evidence=self.field(entry.get("promotion"), f"{where}/promotion", "promotion evidence"),
                )
            )

    def _unobservable(self, raw: Any, where: str) -> UnobservableSource:
        if not isinstance(raw, dict):
            raise self.err(E_TYPE, where, "an unobservable source must be a mapping")
        self.check_keys(raw, ("reason", *DOOR_KEYS, "supported_by", "note", "via"), where)
        reason = str(self.need(raw, "reason", where))
        ef = self.field(self.door_of(raw), where, "unobservable source")
        if not ef.is_known:
            raise self.err(E_UNIVERSE_EVIDENCE, where, f"the claim {reason!r} is asserted without evidence")
        return UnobservableSource(kind=reason, evidence=ef)

    def _size(self, raw: Any, where: str) -> EvidenceField:
        if raw is None:
            return EvidenceField(None, Grade.UNKNOWN, (SourceRef(self.mloc(where), note="no size is stated"),))
        if isinstance(raw, dict) and "value" in raw:
            self.check_keys(raw, ("value", "statement", *DOOR_KEYS, "supported_by", "note", "via"), where)
            #: A size written as {value, statement} with no door is an authored number. Companions such as
            #: `note` / `supported_by` describe that number; they are not a second door (Phase 5 UX2).
            companions = {k: raw[k] for k in ("supported_by", "note", "via") if k in raw}
            body: dict[str, Any] = {k: raw[k] for k in DOOR_KEYS if k in raw} or {
                "declared": {"value": raw["value"], **{k: raw[k] for k in ("statement", "note") if k in raw}}
            }
            ef = self.field({**body, **companions}, where, "size")
            note = str(raw.get("statement") or ef.note or "")
            return EvidenceField(self.number(raw["value"], where, "size", True), ef.grade, ef.sources, note)
        if isinstance(raw, dict) and not set(raw) & set(DOOR_KEYS) and "via" not in raw:
            #: Phase 4 §8: a size written as prose alone used to come back as "must be one of
            #: observed:/declared:/unknown:", which named the wrong problem.
            raise self.err(
                E_MISSING_FIELD,
                where,
                f"a size needs value: <integer>; prose alone ({sorted(set(raw) - {'value'})}) says nothing countable. "
                'Write {value: N, statement: "what N counts"} and attach evidence with supported_by:.',
            )
        ef = self.number_field(raw, where, "size", integer=True)
        return EvidenceField(ef.value, ef.grade, ef.sources, ef.note)

    def _selection_events(self) -> None:
        for i, entry in enumerate(self._section("selection_events")):
            where = f"selection_events[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, where, "a selection event must be a mapping")
            self.check_keys(
                entry,
                ("id", "kind", "over", "chosen", "values", "criterion", "tie_tolerance", "recorded", "policy"),
                where,
            )
            sid = f"sel:{entry['id']}" if "id" in entry else f"sel:{i}"
            if sid in self.bundle.selection_events:
                raise self.err(E_DUPLICATE_ID, where, f"selection id {entry['id']!r} is declared twice")
            self.sel_ids.append(sid)
            kind = SelectionKind(
                self.enum(
                    self.need(entry, "kind", where), tuple(k.value for k in SelectionKind), where, "selection kind"
                )
            )
            cs_ref = self._resolve(self.cand_ids, entry.get("over"), where, "over", "candidate set")
            crit_raw = entry.get("criterion")
            if crit_raw is not None and not isinstance(crit_raw, dict):
                raise self.err(E_TYPE, f"{where}/criterion", "criterion must be a mapping")
            crit_raw = crit_raw or {}
            self.check_keys(crit_raw, CRITERION_FIELDS, f"{where}/criterion")
            fields = {}
            for name in CRITERION_FIELDS:
                ef = self.field(crit_raw.get(name), f"{where}/criterion/{name}", name)
                if name == "direction" and ef.grade is not Grade.UNKNOWN:
                    token = _token(ef.value)
                    if not (token.startswith("min") or token.startswith("max")):
                        raise self.err(
                            E_BAD_DIRECTION,
                            f"{where}/criterion/direction",
                            f"direction={ef.value!r} must state min* or max*; a code comparison is not a direction, "
                            "and belongs in supported_by if it evidences one",
                        )
                fields[name] = ef
            values = self._candidate_values(entry.get("values"), where)
            promoted = entry.get("chosen")
            if isinstance(promoted, dict):
                promoted = self.field(promoted, f"{where}/chosen", "chosen").value
            policy = entry.get("policy")
            if policy is None and fields["direction"].grade is not Grade.UNKNOWN:
                #: The user stated a direction and promoted a member; that pairing is the
                #: policy RD003 checks, recorded as DECLARED rather than as an observation.
                policy = {
                    "declared": {
                        "by": "manifest",
                        "statement": f"{fields['direction'].value} {fields['metric'].value or 'the stated metric'}",
                    }
                }
            self.bundle.add(
                SelectionEvent(
                    selection_id=sid,
                    kind=kind,
                    candidate_set_ref=cs_ref or "",
                    criterion=SelectionCriterion(**fields),
                    candidate_values=values,
                    promoted_ref=str(promoted or ""),
                    declared_policy=self.field(policy, f"{where}/policy", "declared policy"),
                    tie_tolerance=float(self.number(entry.get("tie_tolerance", 0), where, "tie_tolerance")),
                    is_recorded=self.field(entry.get("recorded"), f"{where}/recorded", "recorded"),
                )
            )

    def _candidate_values(self, raw: Any, where: str) -> tuple[tuple[str, float], ...]:
        if raw is None:
            return ()
        ef = self.field(raw, f"{where}/values", "candidate values")
        if ef.grade is Grade.UNKNOWN:
            return ()
        if not isinstance(ef.value, dict):
            raise self.err(E_TYPE, f"{where}/values", "candidate values must be a mapping of ref to number")
        return tuple(
            (str(key), float(self.number(value, f"{where}/values/{key}", "candidate value")))
            for key, value in sorted(ef.value.items(), key=lambda kv: str(kv[0]))
        )

    def _check_quantity_identity(self, quantity: str, artifact: str, table: str, row: str, where: str) -> None:
        #: G2 (Phase 4 §11): RD008 groups cells by quantity key alone, so one key shared by two cells of one
        #: table would compare two different rows and report a conflict nobody declared.
        if not quantity:
            return
        seen = self.quantities.setdefault(quantity, [])
        for other in seen:
            if other[:2] != [artifact, table]:
                continue
            in_table = f"{artifact} (table {table})" if table else artifact
            raise self.err(
                E_MISSING_FIELD,
                f"{where}/quantity",
                f"quantity {quantity!r} is claimed by two cells of {in_table}, row {other[2]!r} and row {row!r}. "
                "RD008 groups cells by quantity key alone, so it would compare those two rows and report the "
                f"difference as a conflict. Make the key identify one cell, e.g. {quantity}/{row or 'row'}.",
            )
        seen.append([artifact, table, row])

    def _cells(self) -> None:
        for i, entry in enumerate(self._section("reported_results")):
            where = f"reported_results[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, where, "a reported result must be a mapping")
            self.check_keys(
                entry,
                (
                    "label",
                    "printed_in",
                    "quantity",
                    "value",
                    "spread",
                    "wording",
                    "aggregate",
                    "members",
                    "member_rule",
                    "exclusions",
                    "dispersion_statement",
                    "steps",
                    "selection",
                    "comparison",
                    "metric_name",
                    "direction_semantics",
                ),
                where,
            )
            label = str(self.need(entry, "label", where))
            if label in self.labels:
                raise self.err(E_DUPLICATE_ID, where, f"label {label!r} is declared twice")
            self.labels.add(label)
            value, spread = self._cell_field(entry.get("value"), f"{where}/value")
            agg_ref = self._cell_aggregation(entry, label, where)
            printed = entry.get("printed_in")
            if printed is not None and not isinstance(printed, dict):
                raise self.err(E_TYPE, f"{where}/printed_in", "printed_in must be a mapping")
            printed = printed or {}
            self.check_keys(
                printed, ("artifact", "page", "table", "row", "column", "quoted_text"), f"{where}/printed_in"
            )
            artifact = str(printed.get("artifact") or (value.sources[0].path if value.sources else self.mloc(where)))
            page = str(printed.get("page") or "")
            table = str(printed.get("table") or "")
            row = str(printed.get("row") or "")
            column = str(printed.get("column") or "")
            quoted = str(printed.get("quoted_text") or (value.sources[0].key if value.sources else ""))
            quantity = str(entry.get("quantity") or "")
            self._check_quantity_identity(quantity, artifact, table, row, where)
            aggregate = entry.get("aggregate")
            reason = str(aggregate.get("reason") or "") if isinstance(aggregate, dict) else ""
            form = (
                self.bundle.aggregations[agg_ref].spread_form
                if agg_ref in self.bundle.aggregations
                else self._spread_form(entry, where, 0)
            )
            self.bundle.add(
                ReportedResult(
                    rid=label,
                    locus=Locus(
                        artifact=artifact,
                        page=page,
                        table=table,
                        row=row,
                        column=column,
                        quoted_text=quoted,
                        quantity_key=quantity,
                    ),
                    metric_name=self.field(entry.get("metric_name"), f"{where}/metric_name", "metric name"),
                    direction_semantics=self.field(
                        entry.get("direction_semantics"), f"{where}/direction_semantics", "direction semantics"
                    ),
                    value=value,
                    spread=spread,
                    spread_form=form,
                    aggregation_ref=agg_ref,
                    transformation_refs=self._cell_steps(entry, label, where),
                    selection_refs=self._cell_selections(entry, where),
                    comparison_set_ref=self._resolve(
                        self.comparison_ids,
                        entry.get("comparison"),
                        f"{where}/comparison",
                        "comparison",
                        "comparison set",
                    )
                    or "",
                    spread_label=self.field(entry.get("wording"), f"{where}/wording", "spread wording"),
                    not_aggregated_reason=reason,
                )
            )

    def _cell_aggregation(self, entry: dict[str, Any], label: str, where: str) -> str:
        raw = entry.get("aggregate")
        if raw is None:
            if "members" in entry:
                raise self.err(
                    E_MISSING_FIELD,
                    f"{where}/aggregate",
                    "members are declared without an aggregation to attach them to",
                )
            return ""
        if not isinstance(raw, dict):
            raise self.err(
                E_TYPE, f"{where}/aggregate", "aggregate must be a mapping, or none: true to say it is absent"
            )
        if "none" in raw:
            extra = sorted(set(raw) - {"none", "reason"})
            if extra:
                raise self.err(E_UNKNOWN_KEY, f"{where}/aggregate", f"'none' cannot be combined with {extra}")
            if raw["none"] is not True:
                raise self.err(E_TYPE, f"{where}/aggregate", "aggregate: none must be the literal true")
            return ""
        if "ref" in raw:
            extra = sorted(set(raw) - {"ref"})
            if extra:
                raise self.err(E_UNKNOWN_KEY, f"{where}/aggregate", f"'ref' cannot be combined with {extra}")
            resolved = self._resolve(self.agg_list, raw["ref"], f"{where}/aggregate/ref", "ref", "aggregation")
            if resolved is None:
                raise self.err(
                    E_UNRESOLVED_REF, f"{where}/aggregate/ref", f"aggregation {raw['ref']!r} is not declared"
                )
            return resolved
        extra = sorted(set(raw) - {"center", "reason"})
        if extra:
            raise self.err(E_UNKNOWN_KEY, f"{where}/aggregate", f"unknown key(s) {extra}")
        return self._aggregation(
            {
                "center": raw.get("center"),
                "spread": entry.get("spread"),
                "members": entry.get("members"),
                "member_rule": entry.get("member_rule"),
                "exclusions": entry.get("exclusions"),
                "dispersion_statement": entry.get("dispersion_statement"),
            },
            f"agg:{label}",
            where,
        )

    def _cell_steps(self, entry: dict[str, Any], label: str, where: str) -> tuple[str, ...]:
        raw = entry.get("steps")
        if raw is None:
            return ()
        if isinstance(raw, dict) and "ref" in raw:
            group = f"t:{raw['ref']}"
            if group not in self.chains:
                raise self.err(
                    E_UNRESOLVED_REF, f"{where}/steps", f"transformation chain {raw['ref']!r} is not declared"
                )
            return self.chains[group]
        if not isinstance(raw, (list, tuple)):
            raise self.err(E_TYPE, f"{where}/steps", "steps must be a list, or a {ref: <chain>}")
        return self._steps(list(raw), label, where)

    def _cell_selections(self, entry: dict[str, Any], where: str) -> tuple[str, ...]:
        raw = entry.get("selection")
        if raw is None:
            return ()
        items = raw if isinstance(raw, (list, tuple)) else [raw]
        out = []
        for item in items:
            resolved = self._resolve(self.sel_ids, item, f"{where}/selection", "selection", "selection event")
            out.append(str(resolved))
        return tuple(out)

    def _resolve(self, pool: list[str], ref: Any, where: str, name: str, kind: str) -> str | None:
        """A reference addresses a section either by index or by the id the user wrote."""
        if ref is None:
            return None
        if isinstance(ref, int) and not isinstance(ref, bool):
            if not 0 <= ref < len(pool):
                raise self.err(
                    E_UNRESOLVED_REF, where, f"{name}={ref} is not one of the {len(pool)} declared {kind}(s)"
                )
            return pool[ref]
        text = str(ref)
        prefix = ID_PREFIX[kind]
        for candidate in (text, f"{prefix}:{text}"):
            if candidate in pool:
                return candidate
        raise self.err(E_UNRESOLVED_REF, where, f"{name}={ref!r} does not address a declared {kind} {sorted(pool)}")

    def _comparisons(self) -> None:
        for i, entry in enumerate(self._section("comparisons")):
            where = f"comparisons[{i}]"
            if not isinstance(entry, dict):
                raise self.err(E_TYPE, where, "a comparison set must be a mapping")
            self.check_keys(entry, ("id", "over", "origin", "marks", "marks_derivation", "rule"), where)
            cid = f"cmp:{entry['id']}" if "id" in entry else f"cmp:{i}"
            if cid in self.bundle.comparison_sets:
                raise self.err(E_DUPLICATE_ID, where, f"comparison id {entry['id']!r} is declared twice")
            members: list[tuple[str, str]] = []
            for ref in entry.get("over") or ():
                if isinstance(ref, int) and not isinstance(ref, bool):
                    raise self.err(E_TYPE, f"{where}/over", "comparison members address cells by label, not by index")
                label = str(ref)
                members.append((label, label.rsplit("/", 1)[-1]))
                #: A peer that is not declared in the manifest stays outside the bundle: the
                #: gap is recorded on the comparison set, never invented as a reported result.
                if label in self.labels:
                    rr = self.bundle.reported_results[label]
                    if rr.comparison_set_ref and rr.comparison_set_ref != cid:
                        raise self.err(
                            E_CONFLICTING_REF,
                            where,
                            f"cell {label!r} is already bound to {rr.comparison_set_ref!r}; "
                            "a cell has one comparison set",
                        )
                    self.bundle.reported_results[label] = dataclasses.replace(rr, comparison_set_ref=cid)
            rule = None
            raw_rule = entry.get("rule")
            if raw_rule is not None:
                if not isinstance(raw_rule, dict):
                    raise self.err(E_TYPE, f"{where}/rule", "rule must be a mapping")
                self.check_keys(raw_rule, ("expression", "operator", "symmetric", "k_factor"), f"{where}/rule")
                rule = PresentationRule(
                    expression=str(raw_rule.get("expression") or ""),
                    operator=str(raw_rule.get("operator") or ""),
                    symmetric=raw_rule.get("symmetric") is not False,
                    k_factor=float(self.number(raw_rule.get("k_factor", 1), f"{where}/rule", "k_factor")),
                    source=self.mloc(f"{where}/rule"),
                )
            marks = self._mark_field(entry.get("marks"), f"{where}/marks")
            derivation = self._mark_field(entry.get("marks_derivation"), f"{where}/marks_derivation")
            if marks.is_known and not derivation.is_known:
                raise self.err(
                    E_MARK_DERIVATION,
                    where,
                    "marks are declared without marks_derivation: the tool does not recompute presentation marks from "
                    "a rule (Phase 2 §18), so judging them needs both lists",
                )
            self.bundle.add(
                ComparisonSet(
                    comparison_set_id=cid,
                    members=tuple(members),
                    external_origin=self.field(entry.get("origin"), f"{where}/origin", "external origin"),
                    presentation_rule=rule,
                    observed_marks=marks,
                    recomputed_marks=tuple(str(x) for x in (derivation.value or ())) if derivation.is_known else (),
                )
            )

    def _mark_field(self, raw: Any, where: str) -> EvidenceField:
        """Presentation marks are always authored: a locator proves a fragment exists, it does
        not prove which member of a comparison it marks (Phase 2 §18)."""
        if raw is None:
            return EvidenceField(None, Grade.UNKNOWN, (SourceRef(self.mloc(where), note="no marks are declared"),))
        if isinstance(raw, (list, tuple)):
            return EvidenceField(
                tuple(str(x) for x in raw), Grade.DECLARED, (SourceRef(self.mloc(where), key="declared:marks"),), ""
            )
        if isinstance(raw, dict):
            self.check_keys(raw, ("shown", *DOOR_KEYS, "supported_by", "note", "via"), where)
            shown = tuple(str(x) for x in (raw.get("shown") or ()))
            ef = self.field(self.door_of(raw), where, "marks")
            if ef.grade is Grade.DIRECT:
                raise self.err(
                    E_BAD_FIELD,
                    where,
                    "a mark list cannot be OBSERVED through the manifest; quote the printed product in supported_by",
                )
            value = shown or (ef.value if isinstance(ef.value, (list, tuple)) else (str(ef.value),) if ef.value else ())
            return EvidenceField(tuple(str(x) for x in value), ef.grade, ef.sources, ef.note)
        raise self.err(E_TYPE, where, "marks must be a list or a mapping")


def bundle_from_manifest(path: str) -> Bundle:
    """Parse a ``result-doctor.yml`` into the same bundle the frozen adapters build."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ManifestError(E_ARTIFACT_MISSING, str(path), "the manifest file does not exist") from None
    except OSError as exc:  # pragma: no cover - unreadable media
        raise ManifestError(E_YAML, str(path), f"the manifest cannot be read: {exc}") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(E_YAML, str(path), f"the manifest is not valid YAML: {exc}") from None
    if not isinstance(data, dict):
        raise ManifestError(E_TOP_LEVEL, str(path), f"the top level must be a mapping, got {type(data).__name__}")
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ManifestError(
            E_SCHEMA_VERSION,
            "schema_version",
            f"this build reads schema_version {SCHEMA_VERSION}, the manifest says {version!r}",
        )
    extra = sorted(set(data) - set(HEADER_KEYS) - set(SECTIONS))
    if extra:
        raise ManifestError(
            E_UNKNOWN_KEY,
            "<top level>",
            f"section(s) {extra} are not part of the contract; a manifest carries only {list(SECTIONS)}",
        )
    return _Manifest(path, data).run()
