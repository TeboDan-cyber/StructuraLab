
"""Validated data model for a small-displacement 2D frame analysis."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np


def _is_finite_number(value: object) -> bool:
    """Return whether value is a finite real numeric scalar."""
    return (
        isinstance(value, (int, float, np.integer, np.floating))
        and not isinstance(value, (bool, np.bool_))
        and bool(np.isfinite(value))
    )


def _is_integer_id(value: object) -> bool:
    """Return whether value is a valid integer identifier."""
    return isinstance(value, (int, np.integer)) and not isinstance(
        value, (bool, np.bool_)
    )


def _validate_vector(
    vector: object,
    shape: tuple[int, ...],
    description: str,
) -> None:
    """Validate a numeric vector's shape and finite values."""
    try:
        values = np.asarray(vector, dtype=float)
    except (TypeError, ValueError):
        raise ValueError(f"{description} must contain numeric values.") from None

    if values.shape != shape:
        raise ValueError(f"{description} must have shape {shape}.")

    if not np.isfinite(values).all():
        raise ValueError(f"{description} must contain only finite values.")


@dataclass(frozen=True)
class Material:
    name: str
    elastic_modulus: float
    density: float = 0.0  # kg/m^3; zero means self-weight is unavailable.

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Material name must not be empty.")
        if not _is_finite_number(self.elastic_modulus) or self.elastic_modulus <= 0:
            raise ValueError("Elastic modulus must be finite and positive.")
        if not _is_finite_number(self.density) or self.density < 0:
            raise ValueError("Material density must be finite and non-negative.")


@dataclass(frozen=True)
class Section:
    name: str
    area: float
    inertia: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Section name must not be empty.")
        if not _is_finite_number(self.area) or self.area <= 0:
            raise ValueError("Area must be finite and positive.")
        if not _is_finite_number(self.inertia) or self.inertia <= 0:
            raise ValueError("Second moment of area must be finite and positive.")


@dataclass(frozen=True)
class Node:
    id: int
    x: float
    y: float


@dataclass(frozen=True)
class FrameElement:
    id: int
    i_node: int
    j_node: int
    material: str
    section: str


@dataclass
class LoadCase:
    """Independent action set. Loads use the model SI sign conventions."""

    name: str
    include_self_weight: bool = False
    nodal_loads: dict[int, np.ndarray] = field(default_factory=dict)
    uniform_element_loads: dict[int, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Load case name must not be empty.")
        if not isinstance(self.include_self_weight, bool):
            raise ValueError("include_self_weight must be a boolean.")


@dataclass
class FrameModel:
    nodes: dict[int, Node] = field(default_factory=dict)
    materials: dict[str, Material] = field(default_factory=dict)
    sections: dict[str, Section] = field(default_factory=dict)
    elements: dict[int, FrameElement] = field(default_factory=dict)
    restraints: dict[int, tuple[bool, bool, bool]] = field(default_factory=dict)
    nodal_loads: dict[int, np.ndarray] = field(default_factory=dict)
    # Uniform member loads in local element axes: [qx, qy] in N/m.
    uniform_element_loads: dict[int, np.ndarray] = field(default_factory=dict)
    load_cases: dict[str, LoadCase] = field(default_factory=dict)

    def add_load_case(self, name: str, include_self_weight: bool = False) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Load case name must not be empty.")
        if name == "default":
            raise ValueError("The reserved load case name 'default' cannot be redefined.")
        if name in self.load_cases:
            raise ValueError(f"Load case {name!r} already exists.")
        self.load_cases[name] = LoadCase(name, include_self_weight)

    def _case(self, name: str) -> LoadCase:
        if name == "default":
            return LoadCase("default", False, self.nodal_loads, self.uniform_element_loads)
        if name not in self.load_cases:
            raise ValueError(f"Load case {name!r} does not exist.")
        return self.load_cases[name]

    def add_node(self, node_id: int, x: float, y: float) -> None:
        if node_id in self.nodes:
            raise ValueError(f"Node {node_id} already exists.")
        if not _is_integer_id(node_id):
            raise ValueError("Node ID must be an integer.")
        if not _is_finite_number(x) or not _is_finite_number(y):
            raise ValueError("Node coordinates must be finite.")
        self.nodes[node_id] = Node(node_id, float(x), float(y))

    def add_material(self, material: Material) -> None:
        if not isinstance(material, Material):
            raise ValueError("Material must be a Material instance.")
        if material.name in self.materials:
            raise ValueError(f"Material {material.name!r} already exists.")
        self.materials[material.name] = material

    def add_section(self, section: Section) -> None:
        if not isinstance(section, Section):
            raise ValueError("Section must be a Section instance.")
        if section.name in self.sections:
            raise ValueError(f"Section {section.name!r} already exists.")
        self.sections[section.name] = section

    def add_frame_element(
        self, element_id: int, i_node: int, j_node: int, material: str, section: str
    ) -> None:
        if not _is_integer_id(element_id):
            raise ValueError("Element ID must be an integer.")
        if element_id in self.elements:
            raise ValueError(f"Element {element_id} already exists.")
        if i_node == j_node:
            raise ValueError("A frame element must connect two different nodes.")
        if i_node not in self.nodes or j_node not in self.nodes:
            raise ValueError("Both element nodes must exist before adding the element.")
        if material not in self.materials or section not in self.sections:
            raise ValueError("Element material and section must exist.")
        self.elements[element_id] = FrameElement(
            element_id, i_node, j_node, material, section
        )

    def fix_node(
        self,
        node_id: int,
        restrained: Iterable[bool] = (True, True, True),
    ) -> None:
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} does not exist.")
        try:
            flags = tuple(restrained)
        except TypeError:
            raise ValueError("Restraints must contain three boolean values.") from None
        if len(flags) != 3:
            raise ValueError("A 2D frame node requires restraints for ux, uy, rz.")
        if not all(isinstance(value, (bool, np.bool_)) for value in flags):
            raise ValueError("Restraints must contain three boolean values.")

        self.restraints[node_id] = (
            bool(flags[0]),
            bool(flags[1]),
            bool(flags[2]),
        )

    def add_nodal_load(
        self, node_id: int, load: np.ndarray, load_case: str = "default"
    ) -> None:
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} does not exist.")
        _validate_vector(load, (3,), "Nodal load")
        vector = np.asarray(load, dtype=float)
        case = self._case(load_case)
        case.nodal_loads[node_id] = case.nodal_loads.get(node_id, np.zeros(3)) + vector

    def add_uniform_distributed_load(
        self,
        element_id: int,
        qx: float = 0.0,
        qy: float = 0.0,
        load_case: str = "default",
    ) -> None:
        """Add a constant load per unit length in an element's local axes.

        Positive qx acts from i to j; positive qy acts along the element's
        local positive transverse axis (90 degrees counter-clockwise from i->j).
        Loads are specified in N/m and accumulate when added more than once.
        """
        if element_id not in self.elements:
            raise ValueError(f"Element {element_id} does not exist.")
        if not _is_finite_number(qx) or not _is_finite_number(qy):
            raise ValueError("Distributed loads must be finite.")
        vector = np.asarray([qx, qy], dtype=float)
        case = self._case(load_case)
        case.uniform_element_loads[element_id] = (
            case.uniform_element_loads.get(element_id, np.zeros(2)) + vector
        )

    def validate(self) -> None:
        """Validate model consistency before structural analysis."""
        if not self.nodes:
            raise ValueError("Model contains no nodes.")
        if not self.elements:
            raise ValueError("Model contains no frame elements.")

        for node_id, node in self.nodes.items():
            if not _is_integer_id(node_id) or not isinstance(node, Node):
                raise ValueError("Model contains an invalid node entry.")
            if node.id != node_id:
                raise ValueError(
                    f"Node dictionary key {node_id!r} does not match its ID."
                )
            if not _is_finite_number(node.x) or not _is_finite_number(node.y):
                raise ValueError(f"Node {node_id} coordinates must be finite.")

        for material_name, material in self.materials.items():
            if not isinstance(material_name, str) or not isinstance(material, Material):
                raise ValueError("Model contains an invalid material entry.")
            if material.name != material_name:
                raise ValueError(
                    f"Material dictionary key {material_name!r} does not match its name."
                )
            if not material_name.strip():
                raise ValueError("Material name must not be empty.")
            if (
                not _is_finite_number(material.elastic_modulus)
                or material.elastic_modulus <= 0
            ):
                raise ValueError(
                    f"Material {material_name!r} elastic modulus must be finite and positive."
                )
            if not _is_finite_number(material.density) or material.density < 0:
                raise ValueError(
                    f"Material {material_name!r} density must be finite and non-negative."
                )

        for section_name, section in self.sections.items():
            if not isinstance(section_name, str) or not isinstance(section, Section):
                raise ValueError("Model contains an invalid section entry.")
            if section.name != section_name:
                raise ValueError(
                    f"Section dictionary key {section_name!r} does not match its name."
                )
            if not section_name.strip():
                raise ValueError("Section name must not be empty.")
            if not _is_finite_number(section.area) or section.area <= 0:
                raise ValueError(
                    f"Section {section_name!r} area must be finite and positive."
                )
            if not _is_finite_number(section.inertia) or section.inertia <= 0:
                raise ValueError(
                    f"Section {section_name!r} second moment of area must be finite and positive."
                )

        for element_id, element in self.elements.items():
            if not _is_integer_id(element_id) or not isinstance(element, FrameElement):
                raise ValueError("Model contains an invalid frame element entry.")
            if element.id != element_id:
                raise ValueError(
                    f"Element dictionary key {element_id!r} does not match its ID."
                )
            if not _is_integer_id(element.i_node) or not _is_integer_id(element.j_node):
                raise ValueError(
                    f"Element {element_id} node references must be integer IDs."
                )
            if element.i_node == element.j_node:
                raise ValueError(
                    f"Element {element_id} must connect two different nodes."
                )
            if element.i_node not in self.nodes or element.j_node not in self.nodes:
                raise ValueError(
                    f"Element {element_id} references a node that does not exist."
                )
            if element.material not in self.materials:
                raise ValueError(f"Element {element_id} references an unknown material.")
            if element.section not in self.sections:
                raise ValueError(f"Element {element_id} references an unknown section.")

            ni = self.nodes[element.i_node]
            nj = self.nodes[element.j_node]
            length = float(np.hypot(nj.x - ni.x, nj.y - ni.y))
            if not np.isfinite(length) or length <= 1e-12:
                raise ValueError(
                    f"Element {element_id} has zero or negligible length."
                )

        for node_id, restraints in self.restraints.items():
            if node_id not in self.nodes:
                raise ValueError(
                    f"Restraint references unknown node {node_id!r}."
                )
            if not isinstance(restraints, (tuple, list)) or len(restraints) != 3:
                raise ValueError(
                    f"Node {node_id} restraints must contain exactly three values."
                )
            if not all(
                isinstance(value, (bool, np.bool_)) for value in restraints
            ):
                raise ValueError(
                    f"Node {node_id} restraints must be boolean values."
                )

        self._validate_loads(
            self.nodal_loads,
            self.uniform_element_loads,
            "default",
        )

        for case_name, case in self.load_cases.items():
            if not isinstance(case_name, str) or not isinstance(case, LoadCase):
                raise ValueError("Model contains an invalid load case entry.")
            if case_name == "default":
                raise ValueError(
                    "The reserved load case name 'default' cannot be redefined."
                )
            if case.name != case_name or not case.name.strip():
                raise ValueError(
                    f"Load case dictionary key {case_name!r} does not match its name."
                )
            if not isinstance(case.include_self_weight, bool):
                raise ValueError(
                    f"Load case {case_name!r} include_self_weight must be boolean."
                )
            self._validate_loads(
                case.nodal_loads,
                case.uniform_element_loads,
                case_name,
            )

    def _validate_loads(
        self,
        nodal_loads: dict[int, np.ndarray],
        uniform_element_loads: dict[int, np.ndarray],
        load_case_name: str,
    ) -> None:
        """Validate nodal and distributed loads for one load case."""
        if not isinstance(nodal_loads, dict):
            raise ValueError(
                f"Load case {load_case_name!r} nodal loads must be a dictionary."
            )
        if not isinstance(uniform_element_loads, dict):
            raise ValueError(
                f"Load case {load_case_name!r} distributed loads must be a dictionary."
            )

        for node_id, load in nodal_loads.items():
            if node_id not in self.nodes:
                raise ValueError(
                    f"Load case {load_case_name!r} references unknown node {node_id!r}."
                )
            _validate_vector(
                load,
                (3,),
                f"Load case {load_case_name!r} nodal load at node {node_id}",
            )

        for element_id, load in uniform_element_loads.items():
            if element_id not in self.elements:
                raise ValueError(
                    f"Load case {load_case_name!r} references unknown element {element_id!r}."
                )
            _validate_vector(
                load,
                (2,),
                f"Load case {load_case_name!r} distributed load on element {element_id}",
            )
