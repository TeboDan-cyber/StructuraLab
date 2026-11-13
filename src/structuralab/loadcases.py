"""Load combinations, self-weight generation, and member-force diagrams."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from structuralab.model import FrameModel
from structuralab.solver import AnalysisResult, solve_linear_static

STANDARD_GRAVITY = 9.80665


@dataclass(frozen=True)
class LoadCombination:
    """Linear combination of named load cases and their dimensionless factors."""

    name: str
    factors: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Load combination name must not be empty.")
        if not self.factors:
            raise ValueError("A load combination must contain at least one load case.")
        if any(not key.strip() for key in self.factors):
            raise ValueError("Load case names in a combination must not be empty.")
        if not np.isfinite(list(self.factors.values())).all():
            raise ValueError("Load combination factors must be finite.")


@dataclass(frozen=True)
class MemberDiagram:
    """Local-axis member actions sampled from i-end to j-end.

    Axial force N, shear V, and moment M use the section-cut convention
    N(x)=-N_i-qx*x, V(x)=-V_i-qy*x, M(x)=-M_i-V_i*x-qy*x^2/2.
    Units are N, N, and N.m; x is metres.
    """

    x: np.ndarray
    axial: np.ndarray
    shear: np.ndarray
    moment: np.ndarray


def _element_geometry(model: FrameModel, element_id: int) -> tuple[float, float, float]:
    element = model.elements[element_id]
    ni, nj = model.nodes[element.i_node], model.nodes[element.j_node]
    dx, dy = nj.x - ni.x, nj.y - ni.y
    length = float(np.hypot(dx, dy))
    return length, dx / length, dy / length


def _combined_model(
    model: FrameModel, combination: LoadCombination, gravity: float
) -> FrameModel:
    unknown = set(combination.factors) - ({"default"} | set(model.load_cases))
    if unknown:
        raise ValueError(f"Unknown load cases in combination: {sorted(unknown)}")
    # Rebuild the model through its public API to avoid mutating the source model.
    combined = FrameModel(
        nodes=dict(model.nodes), materials=dict(model.materials),
        sections=dict(model.sections), elements=dict(model.elements),
        restraints=dict(model.restraints),
    )
    cases = {"default": (model.nodal_loads, model.uniform_element_loads, False)}
    cases.update({
        name: (case.nodal_loads, case.uniform_element_loads, case.include_self_weight)
        for name, case in model.load_cases.items()
    })
    for case_name, factor in combination.factors.items():
        nodal, member, self_weight = cases[case_name]
        for node_id, vector in nodal.items():
            combined.add_nodal_load(node_id, factor * vector)
        for element_id, vector in member.items():
            combined.add_uniform_distributed_load(
                element_id, qx=factor * vector[0], qy=factor * vector[1]
            )
        if self_weight:
            for element_id, element in model.elements.items():
                material = model.materials[element.material]
                section = model.sections[element.section]
                if material.density <= 0:
                    raise ValueError(
                        f"Self-weight requested for load case {case_name!r}, but "
                        f"material {material.name!r} has no positive density."
                    )
                _, c, s = _element_geometry(model, element_id)
                weight_per_length = material.density * section.area * gravity
                # Global gravity (0, -w) transformed to local member axes.
                qx, qy = -s * weight_per_length, -c * weight_per_length
                combined.add_uniform_distributed_load(
                    element_id, qx=factor * qx, qy=factor * qy
                )
    return combined


def member_force_diagrams(
    model: FrameModel, result: AnalysisResult, points_per_element: int = 21
) -> dict[int, MemberDiagram]:
    """Recover local N/V/M diagrams from end actions and uniform member loads."""
    if points_per_element < 2:
        raise ValueError("points_per_element must be at least 2.")
    diagrams: dict[int, MemberDiagram] = {}
    for element_id, end in result.element_end_forces_local.items():
        length, _, _ = _element_geometry(model, element_id)
        qx, qy = model.uniform_element_loads.get(element_id, np.zeros(2))
        x = np.linspace(0.0, length, points_per_element)
        axial = -end[0] - qx * x
        shear = end[1] + qy * x
        moment = -end[2] + end[1] * x + 0.5 * qy * x**2
        diagrams[element_id] = MemberDiagram(x, axial, shear, moment)
    return diagrams


@dataclass(frozen=True)
class CombinationResult:
    combination: LoadCombination
    analysis: AnalysisResult
    diagrams: dict[int, MemberDiagram]


@dataclass(frozen=True)
class LoadAnalysisResults:
    combinations: dict[str, CombinationResult] = field(default_factory=dict)


def analyze_combinations(
    model: FrameModel,
    combinations: list[LoadCombination],
    *,
    gravity: float = STANDARD_GRAVITY,
    points_per_element: int = 21,
) -> LoadAnalysisResults:
    """Analyze each linear combination independently and recover diagrams."""
    model.validate()
    if not combinations:
        raise ValueError("At least one load combination is required.")
    if not np.isfinite(gravity) or gravity <= 0:
        raise ValueError("Gravity must be finite and positive.")
    results: dict[str, CombinationResult] = {}
    for combination in combinations:
        if combination.name in results:
            raise ValueError(f"Duplicate load combination {combination.name!r}.")
        combined_model = _combined_model(model, combination, gravity)
        analysis = solve_linear_static(combined_model)
        diagrams = member_force_diagrams(combined_model, analysis, points_per_element)
        results[combination.name] = CombinationResult(combination, analysis, diagrams)
    return LoadAnalysisResults(results)
