"""Deterministic recomputation used by RD001 / RD005 / RD006.

No tolerance is invented here: RD001 compares the *rendered strings*, because both
projects round the center and the spread independently (`fetch_exp3.py:64-71`,
`average_log.py:132`).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import cast

from .evidence import Grade
from .schema import SpreadForm, Transformation

#: A `k_sem` spread with k=1 equals `sem`; n=1 makes `std`, `sem` and `k_sem` coincide.
#: Those coincidences are recorded so RD005 can refuse to call them agreement.
STAGES = ("member", "center", "dispersion", "render")


def std(values: Iterable[float], ddof: int = 0) -> float:
    vals = list(values)
    n = len(vals)
    if n - ddof <= 0:
        return float("nan")
    m = sum(vals) / n
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (n - ddof))


def dispersion(values: Iterable[float], form: SpreadForm) -> float:
    vals = list(values)
    n = len(vals)
    if form.kind.value == "none" or n == 0:
        return float("nan")
    if form.kind.value == "std":
        return std(vals, form.ddof)
    if form.kind.value == "sem":
        return std(vals, form.ddof) / math.sqrt(n)
    if form.kind.value == "k_sem":
        return std(vals, form.ddof) * form.k / math.sqrt(n)
    raise ValueError(f"unsupported spread kind {form.kind}")


def center(values: Iterable[float], how: str = "mean") -> float:
    vals = list(values)
    if not vals:
        return float("nan")
    if how == "mean":
        return sum(vals) / len(vals)
    if how == "median":
        s = sorted(vals)
        mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
    raise ValueError(f"unsupported center {how}")


def render(value: float, mode: str, digits: int = 2) -> str:
    if mode == "fixed":
        return f"{value:.{digits}f}"
    if mode == "str_round":
        return str(round(value, digits))
    raise ValueError(f"unsupported render mode {mode}")


def stage_transforms(chain: Iterable[Transformation], stage: str) -> list[Transformation]:
    return [t for t in chain if t.params.get("stage") == stage]


def apply_stage(value: float, trs: Iterable[Transformation]) -> float:
    out = value
    for t in trs:
        if t.step.value == "sign_flip":
            out = -out
        elif t.step.value == "scale":
            out = out * float(cast("float", t.params.get("factor", 1)))
        elif t.step.value == "sum_of_part":
            parts = t.params.get("parts")
            #: With no explicit part list the step asserts "sum over the parts this member
            #: contributes", which for a one-element list (fetch_exp3.py:103) is the identity.
            if isinstance(parts, (list, tuple)) and parts:
                out = float(sum(parts))
        elif t.step.value in ("identity", "round", "format", "delta", "best_of_n", "truncate_window"):
            continue
        else:  # pragma: no cover - enum is closed
            raise ValueError(f"cannot apply step {t.step}")
    return out


def declared_vs_observed_conflict(tr: Transformation) -> bool:
    """FM11's TorchSSL case: a declared quantity is replaced by a different one."""
    declared = tr.params.get("declared_source")
    observed = tr.params.get("observed_source")
    return declared is not None and observed is not None and declared != observed


def is_unrecorded(tr: Transformation) -> bool:
    return tr.grade is Grade.UNKNOWN or tr.applied_at.value == "unknown"
