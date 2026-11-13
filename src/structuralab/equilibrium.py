
"""Global force and moment equilibrium auditing for 2D frame analyses."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from structuralab.model import FrameModel
from structuralab.solver import AnalysisResult


@dataclass(frozen=True)
class EquilibriumAudit:
    """Global equilibrium residuals and acceptance tolerances."""

    horizontal_force_residual: float
    vertical_force_residual: float
    moment_residual: float
    horizontal_force_tolerance: float
    vertical_force_tolerance: float
    moment_tolerance: float
    is_equilibrated: bool


def _validate_tolerance(value: float, name: str) -> float:
    """Return a finite, non-negative tolerance."""
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(
            f"{name} must be a finite, non-negative number."
        )

    try:
        tolerance = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"{name} must be a finite, non-negative number."
        ) from exc

    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError(
            f"{name} must be a finite, non-negative number."
        )

    return tolerance


def audit_global_equilibrium(
    model: FrameModel,
    result: AnalysisResult,
    *,
    absolute_tolerance: float = 1e-8,
    relative_tolerance: float = 1e-8,
) -> EquilibriumAudit:
    """Audit global horizontal, vertical, and moment equilibrium.

    The assembled global load vector includes applied nodal loads and
    equivalent nodal loads from uniformly distributed member loads.

    Only restrained reaction components are included. Moment equilibrium
    is evaluated about the global origin.

    The tolerance for each balance is:

        absolute_tolerance + relative_tolerance * sum(abs(contributions))

    Args:
        model: The model used for the analysis.
        result: The corresponding linear static analysis result.
        absolute_tolerance: Absolute force and moment tolerance.
        relative_tolerance: Relative tolerance based on contribution scale.

    Returns:
        An EquilibriumAudit containing residuals, tolerances, and status.

    Raises:
        ValueError: If the result does not match the model or contains
            malformed or non-finite global load or reaction data.
    """
    model.validate()

    atol = _validate_tolerance(
        absolute_tolerance,
        "absolute_tolerance",
    )
    rtol = _validate_tolerance(
        relative_tolerance,
        "relative_tolerance",
    )

    expected_node_order = tuple(sorted(model.nodes))

    if result.node_order != expected_node_order:
        raise ValueError(
            "Analysis result node order does not match the model."
        )

    ndof = 3 * len(expected_node_order)

    global_load = np.asarray(
        result.global_load_vector,
        dtype=float,
    )

    if global_load.shape != (ndof,):
        raise ValueError(
            f"Global load vector must have shape ({ndof},)."
        )

    if not np.all(np.isfinite(global_load)):
        raise ValueError(
            "Global load vector must contain only finite values."
        )

    expected_reaction_nodes = {
        node_id
        for node_id, flags in model.restraints.items()
        if any(flags)
    }

    if set(result.reactions) != expected_reaction_nodes:
        raise ValueError(
            "Analysis result reaction nodes do not match the model restraints."
        )

    reaction_vectors: dict[int, np.ndarray] = {}

    for node_id, vector in result.reactions.items():
        reaction = np.asarray(vector, dtype=float)

        if reaction.shape != (3,):
            raise ValueError(
                f"Reaction vector for node {node_id} must have shape (3,)."
            )

        if not np.all(np.isfinite(reaction)):
            raise ValueError(
                f"Reaction vector for node {node_id} "
                "must contain only finite values."
            )

        reaction_vectors[node_id] = reaction

    applied_fx: list[float] = []
    applied_fy: list[float] = []
    applied_mz: list[float] = []

    reaction_fx: list[float] = []
    reaction_fy: list[float] = []
    reaction_mz: list[float] = []

    for index, node_id in enumerate(expected_node_order):
        start = 3 * index

        fx, fy, mz = global_load[start:start + 3]
        node = model.nodes[node_id]

        applied_fx.append(float(fx))
        applied_fy.append(float(fy))

        applied_mz.append(
            float(mz + node.x * fy - node.y * fx)
        )

        if node_id in reaction_vectors:
            reaction = reaction_vectors[node_id]
            restrained = model.restraints[node_id]

            rx = float(reaction[0]) if restrained[0] else 0.0
            ry = float(reaction[1]) if restrained[1] else 0.0
            rmz = float(reaction[2]) if restrained[2] else 0.0

            reaction_fx.append(rx)
            reaction_fy.append(ry)

            reaction_mz.append(
                float(rmz + node.x * ry - node.y * rx)
            )

    horizontal_contributions = applied_fx + reaction_fx
    vertical_contributions = applied_fy + reaction_fy
    moment_contributions = applied_mz + reaction_mz

    horizontal_residual = float(
        sum(horizontal_contributions)
    )
    vertical_residual = float(
        sum(vertical_contributions)
    )
    moment_residual = float(
        sum(moment_contributions)
    )

    horizontal_tolerance = atol + rtol * sum(
        abs(value) for value in horizontal_contributions
    )

    vertical_tolerance = atol + rtol * sum(
        abs(value) for value in vertical_contributions
    )

    moment_tolerance = atol + rtol * sum(
        abs(value) for value in moment_contributions
    )

    equilibrated = (
        abs(horizontal_residual) <= horizontal_tolerance
        and abs(vertical_residual) <= vertical_tolerance
        and abs(moment_residual) <= moment_tolerance
    )

    return EquilibriumAudit(
        horizontal_force_residual=horizontal_residual,
        vertical_force_residual=vertical_residual,
        moment_residual=moment_residual,
        horizontal_force_tolerance=horizontal_tolerance,
        vertical_force_tolerance=vertical_tolerance,
        moment_tolerance=moment_tolerance,
        is_equilibrated=equilibrated,
    )
