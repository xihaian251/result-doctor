"""Unit tests for the arithmetic core RD001/RD005 depend on."""

from __future__ import annotations

import math

import pytest

from result_doctor.compute import (
    STAGES,
    apply_stage,
    center,
    declared_vs_observed_conflict,
    dispersion,
    render,
    stage_transforms,
    std,
)
from result_doctor.evidence import declared
from result_doctor.schema import (
    AppliedAt,
    SpreadForm,
    SpreadKind,
    Transformation,
    TransformStep,
)

VALUES = (-29.456942, -21.497114, -27.786345, -21.37039)


def test_std_and_dispersion_families_on_the_frozen_chain_a_values() -> None:
    assert std(VALUES, 0) == pytest.approx(3.6424323, abs=1e-6)
    assert std(VALUES, 1) == pytest.approx(4.2059189, abs=1e-6)
    k3 = SpreadForm(SpreadKind.K_SEM, k=3.0, ddof=0, n=4)
    assert dispersion(VALUES, k3) == pytest.approx(5.4636485, abs=1e-6)
    assert dispersion(VALUES, SpreadForm(SpreadKind.SEM, ddof=0, n=4)) == pytest.approx(1.8212162, abs=1e-6)
    assert dispersion(VALUES, SpreadForm(SpreadKind.STD, ddof=1, n=4)) == pytest.approx(4.2059189, abs=1e-6)
    #: the locked counterexample: ddof=1 under the same 3*SE formula prints 6.31, not 5.46
    assert render(dispersion(VALUES, SpreadForm(SpreadKind.K_SEM, k=3.0, ddof=1, n=4)), "fixed") == "6.31"


def test_center_and_empty_inputs() -> None:
    assert center([10.0, 12.0, 14.0]) == 12.0
    assert center([1.0, 2.0, 3.0, 4.0], "median") == 2.5
    assert math.isnan(center([]))
    assert math.isnan(std([1.0], 1))
    assert math.isnan(dispersion([1.0], SpreadForm(SpreadKind.NONE)))


def test_the_two_rendering_modes_differ_on_trailing_zeroes() -> None:
    assert render(95.13666, "fixed") == "95.14"
    assert render(78.005478, "fixed") == "78.01"
    assert render(95.1, "str_round") == "95.1"
    assert render(95.1, "fixed") == "95.10"
    with pytest.raises(ValueError):
        render(1.0, "hex")


def test_stage_order_is_the_frozen_four() -> None:
    assert STAGES == ("member", "center", "dispersion", "render")


def _t(step: TransformStep, stage: str, **params: object) -> Transformation:
    return Transformation(
        transform_id=f"t:{step.value}:{stage}",
        step=step,
        applied_at=AppliedAt.CODE,
        params={"stage": stage, **params},
        condition=declared("always", "x.py", 1),
    )


def test_member_stage_scale_and_sign_flip_compose_in_order() -> None:
    chain = [_t(TransformStep.SCALE, "member", factor=100), _t(TransformStep.SIGN_FLIP, "center")]
    assert apply_stage(0.9516, stage_transforms(chain, "member")) == pytest.approx(95.16)
    assert apply_stage(95.16, stage_transforms(chain, "center")) == pytest.approx(-95.16)
    assert stage_transforms(chain, "render") == []


def test_sum_of_part_with_no_explicit_parts_is_the_identity() -> None:
    """fetch_exp3.py:103 sums a one-element list, so it must not erase the value."""
    tr = _t(TransformStep.SUM_OF_PART, "member", parts=())
    assert apply_stage(-25.03, [tr]) == pytest.approx(-25.03)
    assert apply_stage(-25.03, [_t(TransformStep.SUM_OF_PART, "member", parts=(1.0, 2.0))]) == 3.0


def test_declared_source_conflict_is_the_only_fm11_signal() -> None:
    ok = _t(TransformStep.SCALE, "member", factor=100)
    bad = _t(
        TransformStep.SUM_OF_PART,
        "center",
        declared_source="eval/top-5-acc",
        observed_source="rolling mean of eval/top-1-acc",
    )
    same = _t(TransformStep.SUM_OF_PART, "center", declared_source="eval/top-1-acc", observed_source="eval/top-1-acc")
    assert not declared_vs_observed_conflict(ok)
    assert declared_vs_observed_conflict(bad)
    assert not declared_vs_observed_conflict(same)
