import numpy as np
import pytest

from structuralab.model import FrameModel, Material, Section
from structuralab.solver import StructuralInstabilityError, solve_linear_static


def cantilever_model() -> FrameModel:
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 4.0, 0.0)
    model.add_material(Material("steel", 200e9))
    model.add_section(Section("section", 0.01, 8.0e-6))
    model.add_frame_element(1, 1, 2, "steel", "section")
    model.fix_node(1)
    model.add_nodal_load(2, np.array([0.0, -10_000.0, 0.0]))
    return model


def test_cantilever_tip_deflection_matches_euler_bernoulli_solution():
    model = cantilever_model()
    result = solve_linear_static(model)
    e = 200e9
    i = 8e-6
    length = 4.0
    load = 10_000.0
    expected = load * length**3 / (3 * e * i)
    assert result.displacements[2][1] == pytest.approx(-expected, rel=1e-10)


def test_cantilever_fixed_end_reactions_equilibrate_applied_load():
    result = solve_linear_static(cantilever_model())
    reaction = result.reactions[1]
    assert reaction[0] == pytest.approx(0.0, abs=1e-8)
    assert reaction[1] == pytest.approx(10_000.0, rel=1e-10)
    assert reaction[2] == pytest.approx(40_000.0, rel=1e-10)


def test_unrestrained_frame_is_reported_as_unstable():
    model = cantilever_model()
    model.restraints.clear()
    with pytest.raises(StructuralInstabilityError):
        solve_linear_static(model)


def test_duplicate_node_is_rejected():
    model = FrameModel()
    model.add_node(1, 0, 0)
    with pytest.raises(ValueError):
        model.add_node(1, 1, 0)


def test_cantilever_uniform_member_load_matches_closed_form_deflection():
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 4.0, 0.0)
    model.add_material(Material("steel", 200e9))
    model.add_section(Section("section", 0.01, 8.0e-6))
    model.add_frame_element(1, 1, 2, "steel", "section")
    model.fix_node(1)
    model.add_uniform_distributed_load(1, qy=-2_000.0)

    result = solve_linear_static(model)
    expected = (-2_000.0) * 4.0**4 / (8.0 * 200e9 * 8.0e-6)
    assert result.displacements[2][1] == pytest.approx(expected, rel=1e-10)
    assert result.reactions[1][1] == pytest.approx(8_000.0, rel=1e-10)
    assert result.reactions[1][2] == pytest.approx(16_000.0, rel=1e-10)


def test_uniform_axial_member_load_is_included_in_global_equilibrium():
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 3.0, 0.0)
    model.add_material(Material("steel", 200e9))
    model.add_section(Section("section", 0.01, 8.0e-6))
    model.add_frame_element(1, 1, 2, "steel", "section")
    model.fix_node(1)
    model.fix_node(2)
    model.add_uniform_distributed_load(1, qx=1_000.0)

    result = solve_linear_static(model)
    assert result.reactions[1][0] == pytest.approx(-1_500.0)
    assert result.reactions[2][0] == pytest.approx(-1_500.0)


def test_distributed_load_rejects_unknown_element_and_non_finite_values():
    model = FrameModel()
    with pytest.raises(ValueError, match="does not exist"):
        model.add_uniform_distributed_load(99, qy=-1_000.0)

    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 1.0, 0.0)
    model.add_material(Material("steel", 200e9))
    model.add_section(Section("section", 0.01, 8.0e-6))
    model.add_frame_element(1, 1, 2, "steel", "section")
    with pytest.raises(ValueError, match="finite"):
        model.add_uniform_distributed_load(1, qy=float("nan"))
