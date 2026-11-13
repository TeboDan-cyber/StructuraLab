"""Validated data model for a small-displacement 2D frame analysis."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Material:
    name: str
    elastic_modulus: float
    density: float = 0.0  # kg/m^3; zero means self-weight is unavailable.

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Material name must not be empty.")
        if not np.isfinite(self.elastic_modulus) or self.elastic_modulus <= 0:
            raise ValueError("Elastic modulus must be finite and positive.")
        if not np.isfinite(self.density) or self.density < 0:
            raise ValueError("Material density must be finite and non-negative.")


@dataclass(frozen=True)
class Section:
    name: str
    area: float
    inertia: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Section name must not be empty.")
        if not np.isfinite(self.area) or self.area <= 0:
            raise ValueError("Area must be finite and positive.")
        if not np.isfinite(self.inertia) or self.inertia <= 0:
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
        if not self.name.strip():
            raise ValueError("Load case name must not be empty.")


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
        if not np.isfinite([x, y]).all():
            raise ValueError("Node coordinates must be finite.")
        self.nodes[node_id] = Node(node_id, float(x), float(y))

    def add_material(self, material: Material) -> None:
        if material.name in self.materials:
            raise ValueError(f"Material {material.name!r} already exists.")
        self.materials[material.name] = material

    def add_section(self, section: Section) -> None:
        if section.name in self.sections:
            raise ValueError(f"Section {section.name!r} already exists.")
        self.sections[section.name] = section

    def add_frame_element(
        self, element_id: int, i_node: int, j_node: int, material: str, section: str
    ) -> None:
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
        flags = tuple(bool(v) for v in restrained)
        if len(flags) != 3:
            raise ValueError("A 2D frame node requires restraints for ux, uy, rz.")
        self.restraints[node_id] = flags  # True means restrained.

    def add_nodal_load(
        self, node_id: int, load: np.ndarray, load_case: str = "default"
    ) -> None:
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} does not exist.")
        vector = np.asarray(load, dtype=float)
        if vector.shape != (3,) or not np.isfinite(vector).all():
            raise ValueError("Nodal load must be a finite [Fx, Fy, Mz] vector.")
        case = self._case(load_case)
        case.nodal_loads[node_id] = case.nodal_loads.get(node_id, np.zeros(3)) + vector

    def add_uniform_distributed_load(
        self, element_id: int, qx: float = 0.0, qy: float = 0.0,
        load_case: str = "default",
    ) -> None:
        """Add a constant load per unit length in an element's local axes.

        Positive qx acts from i to j; positive qy acts along the element's
        local positive transverse axis (90 degrees counter-clockwise from i->j).
        Loads are specified in N/m and accumulate when added more than once.
        """
        if element_id not in self.elements:
            raise ValueError(f"Element {element_id} does not exist.")
        vector = np.asarray([qx, qy], dtype=float)
        if not np.isfinite(vector).all():
            raise ValueError("Distributed loads must be finite.")
        case = self._case(load_case)
        case.uniform_element_loads[element_id] = (
            case.uniform_element_loads.get(element_id, np.zeros(2)) + vector
        )

    def validate(self) -> None:
        if not self.nodes:
            raise ValueError("Model contains no nodes.")
        if not self.elements:
            raise ValueError("Model contains no frame elements.")
        for element in self.elements.values():
            ni, nj = self.nodes[element.i_node], self.nodes[element.j_node]
            length = float(np.hypot(nj.x - ni.x, nj.y - ni.y))
            if length <= 1e-12:
                raise ValueError(f"Element {element.id} has zero or negligible length.")
