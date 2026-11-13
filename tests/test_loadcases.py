import numpy as np
import pytest

from structuralab.loadcases import (
    LoadCombination,
    analyze_combinations,
    member_force_diagrams,
)
from structuralab.model import FrameModel, Material, Section
from structuralab.solver import solve_linear_static


def cantilever() -> FrameModel:
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 4.0, 0.0)
    model.add_material(Material("concrete", 25e9, density=2400.0))
    model.add_section(Section("beam", 0.15, 0.003))
    model.add_frame_element(1, 1, 2, "concrete", "beam")
    model.fix_node(1)
    return model


def test_dead_and_live_cases_are_combined_with_independent_factors():
    model = cantilever()
    model.add_load_case("D")
    model.add_load_case("L")
    model.add_nodal_load(2, np.array([0.0, -10_000.0, 0.0]), load_case="D")
    model.add_nodal_load(2, np.array([0.0, -5_000.0, 0.0]), load_case="L")
    results = analyze_combinations(
        model, [LoadCombination("ULS", {"D": 1.2, "L": 1.6})]
    )
    reaction = results.combinations["ULS"].analysis.reactions[1]
    assert reaction[1] == pytest.approx(20_000.0)
    assert reaction[2] == pytest.approx(80_000.0)
    assert model.nodal_loads == {}  # combination did not mutate source model


def test_self_weight_is_generated_from_density_area_and_gravity():
    model = cantilever()
    model.add_load_case("D", include_self_weight=True)
    result = analyze_combinations(
        model, [LoadCombination("D-only", {"D": 1.0})]
    ).combinations["D-only"].analysis
    expected = 2400.0 * 0.15 * 9.80665 * 4.0
    assert result.reactions[1][1] == pytest.approx(expected)
    assert result.reactions[1][2] == pytest.approx(expected * 2.0)


def test_self_weight_requires_material_density():
    model = cantilever()
    model.materials["concrete"] = type(model.materials["concrete"])("concrete", 25e9)
    model.add_load_case("D", include_self_weight=True)
    with pytest.raises(ValueError, match="positive density"):
        analyze_combinations(model, [LoadCombination("D", {"D": 1.0})])


def test_uniform_load_diagram_has_zero_free_end_shear_and_moment():
    model = cantilever()
    model.add_uniform_distributed_load(1, qy=-2_000.0)
    result = solve_linear_static(model)
    diagram = member_force_diagrams(model, result, points_per_element=5)[1]
    assert diagram.x[0] == pytest.approx(0.0)
    assert diagram.x[-1] == pytest.approx(4.0)
    assert diagram.shear[-1] == pytest.approx(0.0, abs=1e-8)
    assert diagram.moment[-1] == pytest.approx(0.0, abs=1e-8)
    assert diagram.moment[0] == pytest.approx(-16_000.0)


def test_unknown_case_and_invalid_diagram_resolution_are_rejected():
    model = cantilever()
    with pytest.raises(ValueError, match="Unknown load cases"):
        analyze_combinations(model, [LoadCombination("bad", {"X": 1.0})])
    with pytest.raises(ValueError, match="at least 2"):
        member_force_diagrams(model, solve_linear_static(model), points_per_element=1)


def test_fixed_fixed_uniform_load_diagram_matches_both_end_actions():
    model = cantilever()
    model.fix_node(2)
    model.add_uniform_distributed_load(1, qy=-2_000.0)
    result = solve_linear_static(model)
    diagram = member_force_diagrams(model, result, points_per_element=9)[1]
    end = result.element_end_forces_local[1]
    assert diagram.axial[0] == pytest.approx(-end[0])
    assert diagram.axial[-1] == pytest.approx(end[3])
    assert diagram.shear[0] == pytest.approx(end[1])
    assert diagram.shear[-1] == pytest.approx(-end[4])
    assert diagram.moment[0] == pytest.approx(-end[2])
    assert diagram.moment[-1] == pytest.approx(end[5])


def test_inclined_member_self_weight_equilibrates_global_gravity():
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 3.0, 4.0)
    model.add_material(Material("concrete", 25e9, density=2500.0))
    model.add_section(Section("column", 0.20, 0.004))
    model.add_frame_element(1, 1, 2, "concrete", "column")
    model.fix_node(1)
    model.fix_node(2)
    model.add_load_case("D", include_self_weight=True)
    result = analyze_combinations(
        model, [LoadCombination("D", {"D": 1.0})]
    ).combinations["D"].analysis
    expected_weight = 2500.0 * 0.20 * 5.0 * 9.80665
    assert result.reactions[1][1] + result.reactions[2][1] == pytest.approx(expected_weight)
    assert result.reactions[1][0] + result.reactions[2][0] == pytest.approx(0.0, abs=1e-8)
