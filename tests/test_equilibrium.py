
"""Tests for global force and moment equilibrium auditing."""

import numpy as np
import pytest

from structuralab.equilibrium import audit_global_equilibrium
from structuralab.model import FrameModel, Material, Section
from structuralab.solver import solve_linear_static


def build_cantilever_model() -> FrameModel:
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 4.0, 0.0)

    model.add_material(Material("Steel", 200e9, 7850.0))
    model.add_section(Section("Section", 0.01, 8.0e-6))

    model.add_frame_element(1, 1, 2, "Steel", "Section")
    model.fix_node(1)
    return model


def test_cantilever_nodal_load_passes_global_equilibrium_audit() -> None:
    model = build_cantilever_model()
    model.add_nodal_load(2, np.array([0.0, -10_000.0, 0.0]))

    result = solve_linear_static(model)
    audit = audit_global_equilibrium(model, result)

    assert audit.is_equilibrated
    assert abs(audit.horizontal_force_residual) < audit.horizontal_force_tolerance
    assert abs(audit.vertical_force_residual) < audit.vertical_force_tolerance
    assert abs(audit.moment_residual) < audit.moment_tolerance


def test_inclined_member_distributed_load_passes_global_equilibrium_audit() -> None:
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 4.0, 3.0)

    model.add_material(Material("Steel", 200e9, 7850.0))
    model.add_section(Section("Section", 0.01, 8.0e-6))

    model.add_frame_element(1, 1, 2, "Steel", "Section")
    model.fix_node(1)

    model.add_uniform_distributed_load(1, qx=0.0, qy=-2_000.0)

    result = solve_linear_static(model)
    audit = audit_global_equilibrium(model, result)

    assert audit.is_equilibrated
    assert abs(audit.horizontal_force_residual) < audit.horizontal_force_tolerance
    assert abs(audit.vertical_force_residual) < audit.vertical_force_tolerance
    assert abs(audit.moment_residual) < audit.moment_tolerance


def test_audit_detects_corrupted_load_vector() -> None:
    model = build_cantilever_model()
    model.add_nodal_load(2, np.array([0.0, -10_000.0, 0.0]))

    result = solve_linear_static(model)
    corrupted_load = result.global_load_vector.copy()
    corrupted_load[3] += 1_000.0

    corrupted_result = type(result)(
        node_order=result.node_order,
        displacements=result.displacements,
        reactions=result.reactions,
        global_stiffness=result.global_stiffness,
        global_load_vector=corrupted_load,
        element_end_forces_local=result.element_end_forces_local,
    )

    audit = audit_global_equilibrium(model, corrupted_result)
    assert not audit.is_equilibrated


@pytest.mark.parametrize(
    ("absolute_tolerance", "relative_tolerance"),
    [
        (-1.0, 1e-8),
        (1e-8, -1.0),
        (float("nan"), 1e-8),
        (1e-8, float("inf")),
        (True, 1e-8),
    ],
)
def test_invalid_tolerances_are_rejected(
    absolute_tolerance: float,
    relative_tolerance: float,
) -> None:
    model = build_cantilever_model()
    model.add_nodal_load(2, np.array([0.0, -10_000.0, 0.0]))
    result = solve_linear_static(model)

    with pytest.raises(ValueError):
        audit_global_equilibrium(
            model,
            result,
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
        )


def test_wrong_node_order_is_rejected() -> None:
    model = build_cantilever_model()
    model.add_nodal_load(2, np.array([0.0, -10_000.0, 0.0]))
    result = solve_linear_static(model)

    corrupted_result = type(result)(
        node_order=tuple(reversed(result.node_order)),
        displacements=result.displacements,
        reactions=result.reactions,
        global_stiffness=result.global_stiffness,
        global_load_vector=result.global_load_vector,
        element_end_forces_local=result.element_end_forces_local,
    )

    with pytest.raises(ValueError):
        audit_global_equilibrium(model, corrupted_result)
