"""Evidence primitives.

Shape deliberately mirrors Experiment Doctor's `{value, source, note}` + grade idea,
re-implemented locally so Result Doctor stays independent of the upstream package.
Upstream provenance (seed / git / environment / resolved config) is referenced by id
only, never re-derived here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Grade(str, Enum):
    DIRECT = "DIRECT"
    DERIVED = "DERIVED"
    DECLARED = "DECLARED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceRef:
    """Where an evidence claim comes from: file:line, artifact, or paper locus."""

    path: str = ""
    key: str = ""
    line: int | str = ""
    artifact_id: str = ""
    note: str = ""

    def label(self) -> str:
        parts = [self.path]
        if self.line != "":
            parts.append(f":{self.line}")
        if self.key:
            parts.append(f" [{self.key}]")
        if self.artifact_id:
            parts.append(f" (artifact {self.artifact_id})")
        return "".join(p for p in parts if p)


@dataclass(frozen=True)
class EvidenceField:
    """One field of the schema: a value plus the grade it is held at."""

    value: Any = None
    grade: Grade = Grade.UNKNOWN
    sources: tuple[SourceRef, ...] = ()
    note: str = ""

    @property
    def is_known(self) -> bool:
        return self.grade is not Grade.UNKNOWN and self.value is not None


def _f(value: Any, grade: Grade, path: str, line: int | str, key: str, note: str) -> EvidenceField:
    return EvidenceField(value, grade, (SourceRef(path, key, line, note=note),), note)


def declared(value: Any, path: str, line: int | str = "", key: str = "", note: str = "") -> EvidenceField:
    return _f(value, Grade.DECLARED, path, line, key, note)


def direct(value: Any, path: str, line: int | str = "", key: str = "", note: str = "") -> EvidenceField:
    return _f(value, Grade.DIRECT, path, line, key, note)


def derived(value: Any, path: str = "", line: int | str = "", key: str = "", note: str = "") -> EvidenceField:
    return _f(value, Grade.DERIVED, path, line, key, note)


def unknown_field(note: str = "", path: str = "") -> EvidenceField:
    return EvidenceField(None, Grade.UNKNOWN, (SourceRef(path, note=note),) if path else (), note)
