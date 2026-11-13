
import numpy as np
import pytest

from structuralab.model import (
    FrameElement,
    FrameModel,
    LoadCase,
    Material,
    Node,
    Section,
)


def valid_model() -> FrameModel:
    """Build a valid two-node frame model."""
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, 4.0, 0.0)
    model.add_material(Material("steel", 200e9, 7850.0))
    model.add_section(Section("section", 0.01, 8.0e-6))
    model.add_frame_element(1, 1, 2, "steel", "section")
    model.fix_node(1)
    model.add_nodal_load(2, np.array([0.0, -10_000.0, 0.0]))
    return model


def test_valid_model_passes_validation():
    model = valid_model()
    model.validate()


def test_model_without_restraints_is_still_valid():
    model = valid_model()
    model.restraints.clear()

    # Structural instability is the solver's responsibility.
    model.validate()


def test_node_dictionary_key_must_match_node_id():
    model = valid_model()
    model.nodes[3] = Node(4, 5.0, 0.0)

    with pytest.raises(ValueError, match="does not match"):
        model.validate()


def test_non_finite_node_coordinates_are_rejected():
    model = valid_model()
    model.nodes[2] = Node(2, float("nan"), 0.0)

    with pytest.raises(ValueError, match="coordinates must be finite"):
        model.validate()


def test_element_with_missing_node_is_rejected():
    model = valid_model()
    model.elements[1] = FrameElement(1, 1, 99, "steel", "section")

    with pytest.raises(ValueError, match="node that does not exist"):
        model.validate()


def test_element_with_unknown_material_is_rejected():
    model = valid_model()
    model.elements[1] = FrameElement(1, 1, 2, "unknown", "section")

    with pytest.raises(ValueError, match="unknown material"):
        model.validate()


def test_element_with_unknown_section_is_rejected():
    model = valid_model()
    model.elements[1] = FrameElement(1, 1, 2, "steel", "unknown")

    with pytest.raises(ValueError, match="unknown section"):
        model.validate()


def test_zero_length_element_is_rejected():
    model = valid_model()
    model.nodes[2] = Node(2, 0.0, 0.0)

    with pytest.raises(ValueError, match="zero or negligible length"):
        model.validate()


def test_invalid_material_properties_are_rejected():
    model = valid_model()
    object.__setattr__(model.materials["steel"], "elastic_modulus", float("nan"))

    with pytest.raises(ValueError, match="elastic modulus"):
        model.validate()


def test_invalid_section_properties_are_rejected():
    model = valid_model()
    object.__setattr__(model.sections["section"], "area", -0.01)

    with pytest.raises(ValueError, match="area must be finite and positive"):
        model.validate()


def test_restraint_for_unknown_node_is_rejected():
    model = valid_model()
    model.restraints[99] = (True, True, True)

    with pytest.raises(ValueError, match="unknown node"):
        model.validate()


def test_restraints_must_contain_three_values():
    model = valid_model()
    model.restraints[1] = (True, True)

    with pytest.raises(ValueError, match="exactly three"):
        model.validate()


def test_restraints_must_be_boolean():
    model = valid_model()
    model.restraints[1] = (True, 1, False)

    with pytest.raises(ValueError, match="must be boolean"):
        model.validate()


def test_nodal_load_for_unknown_node_is_rejected():
    model = valid_model()
    model.nodal_loads[99] = np.zeros(3)

    with pytest.raises(ValueError, match="unknown node"):
        model.validate()


def test_nodal_load_with_invalid_shape_is_rejected():
    model = valid_model()
    model.nodal_loads[2] = np.zeros(2)

    with pytest.raises(ValueError, match="shape"):
        model.validate()


def test_non_finite_nodal_load_is_rejected():
    model = valid_model()
    model.nodal_loads[2] = np.array([0.0, float("inf"), 0.0])

    with pytest.raises(ValueError, match="finite"):
        model.validate()


def test_distributed_load_for_unknown_element_is_rejected():
    model = valid_model()
    model.uniform_element_loads[99] = np.zeros(2)

    with pytest.raises(ValueError, match="unknown element"):
        model.validate()


def test_distributed_load_with_invalid_shape_is_rejected():
    model = valid_model()
    model.uniform_element_loads[1] = np.zeros(3)

    with pytest.raises(ValueError, match="shape"):
        model.validate()


def test_non_finite_distributed_load_is_rejected():
    model = valid_model()
    model.uniform_element_loads[1] = np.array([0.0, float("nan")])

    with pytest.raises(ValueError, match="finite"):
        model.validate()


def test_load_case_dictionary_name_must_match_case_name():
    model = valid_model()
    model.load_cases["dead"] = LoadCase("live")

    with pytest.raises(ValueError, match="does not match its name"):
        model.validate()


def test_load_case_with_unknown_node_load_is_rejected():
    model = valid_model()
    model.add_load_case("dead")
    model.load_cases["dead"].nodal_loads[99] = np.zeros(3)

    with pytest.raises(ValueError, match="unknown node"):
        model.validate()


def test_reserved_default_load_case_cannot_be_added_directly():
    model = valid_model()
    model.load_cases["default"] = LoadCase("default")

    with pytest.raises(ValueError, match="reserved load case"):
        model.validate()
