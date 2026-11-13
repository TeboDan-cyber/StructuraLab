"""Direct-stiffness linear static solver for 2D Euler-Bernoulli frame elements."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from structuralab.model import FrameModel


@dataclass(frozen=True)
class AnalysisResult:
    """Linear analysis output; local end forces use [N_i, V_i, M_i, N_j, V_j, M_j]."""
    node_order: tuple[int, ...]
    displacements: dict[int, np.ndarray]
    reactions: dict[int, np.ndarray]
    global_stiffness: np.ndarray
    global_load_vector: np.ndarray
    element_end_forces_local: dict[int, np.ndarray]


class StructuralInstabilityError(RuntimeError):
    """Raised when the restrained global stiffness system is singular/unstable."""


def _element_matrices(
    model: FrameModel, element_id: int
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    element = model.elements[element_id]
    ni, nj = model.nodes[element.i_node], model.nodes[element.j_node]
    dx, dy = nj.x - ni.x, nj.y - ni.y
    length = float(np.hypot(dx, dy))
    c, s = dx / length, dy / length

    material = model.materials[element.material]
    section = model.sections[element.section]
    ea_l = material.elastic_modulus * section.area / length
    ei = material.elastic_modulus * section.inertia
    k_local = np.array([
        [ ea_l, 0, 0, -ea_l, 0, 0],
        [ 0, 12*ei/length**3, 6*ei/length**2, 0, -12*ei/length**3, 6*ei/length**2],
        [ 0, 6*ei/length**2, 4*ei/length, 0, -6*ei/length**2, 2*ei/length],
        [-ea_l, 0, 0, ea_l, 0, 0],
        [ 0, -12*ei/length**3, -6*ei/length**2, 0, 12*ei/length**3, -6*ei/length**2],
        [ 0, 6*ei/length**2, 2*ei/length, 0, -6*ei/length**2, 4*ei/length],
    ], dtype=float)

    # Maps global nodal DOFs to local axial/transverse/rotational DOFs.
    transform = np.array([
        [ c, s, 0, 0, 0, 0],
        [-s, c, 0, 0, 0, 0],
        [ 0, 0, 1, 0, 0, 0],
        [ 0, 0, 0, c, s, 0],
        [ 0, 0, 0, -s, c, 0],
        [ 0, 0, 0, 0, 0, 1],
    ], dtype=float)
    return transform.T @ k_local @ transform, transform, length, k_local


def solve_linear_static(model: FrameModel) -> AnalysisResult:
    """Solve K u = F with prescribed zero displacements at restrained DOFs.

    DOF ordering is [ux, uy, rz] for each node in ascending node-ID order.
    Supports nodal loads and constant member loads in local element axes.
    Imposed support movements and member releases are not yet implemented.
    """
    model.validate()
    node_order = tuple(sorted(model.nodes))
    node_index = {node_id: i for i, node_id in enumerate(node_order)}
    ndof = 3 * len(node_order)
    stiffness = np.zeros((ndof, ndof), dtype=float)
    load = np.zeros(ndof, dtype=float)

    for node_id, vector in model.nodal_loads.items():
        start = 3 * node_index[node_id]
        load[start:start + 3] += vector

    for element_id, element in model.elements.items():
        ke, transform, length, _ = _element_matrices(model, element_id)
        i = 3 * node_index[element.i_node]
        j = 3 * node_index[element.j_node]
        dofs = [i, i+1, i+2, j, j+1, j+2]
        stiffness[np.ix_(dofs, dofs)] += ke

        # Consistent nodal load vector for a constant local-axis member load.
        # DOF order: [u_i, v_i, rz_i, u_j, v_j, rz_j].
        qx, qy = model.uniform_element_loads.get(element_id, np.zeros(2))
        if qx != 0.0 or qy != 0.0:
            equivalent_local = np.array([
                qx * length / 2.0,
                qy * length / 2.0,
                qy * length**2 / 12.0,
                qx * length / 2.0,
                qy * length / 2.0,
                -qy * length**2 / 12.0,
            ])
            load[np.asarray(dofs)] += transform.T @ equivalent_local

    restrained: list[int] = []
    for node_id, flags in model.restraints.items():
        start = 3 * node_index[node_id]
        restrained.extend(start + dof for dof, is_fixed in enumerate(flags) if is_fixed)
    free = np.array([i for i in range(ndof) if i not in set(restrained)], dtype=int)

    if free.size == 0:
        displacement = np.zeros(ndof)
    else:
        kff = stiffness[np.ix_(free, free)]
        ff = load[free]
        try:
            displacement = np.zeros(ndof)
            displacement[free] = np.linalg.solve(kff, ff)
        except np.linalg.LinAlgError as exc:
            raise StructuralInstabilityError(
                "The free-DOF stiffness matrix is singular. Check supports, connectivity, "
                "member properties, and mechanisms."
            ) from exc

    residual = stiffness @ displacement - load
    displacements = {
        node_id: displacement[3*i:3*i+3].copy()
        for i, node_id in enumerate(node_order)
    }
    reactions = {
        node_id: residual[3*node_index[node_id]:3*node_index[node_id]+3].copy()
        for node_id in node_order
        if any(model.restraints.get(node_id, (False, False, False)))
    }
    element_end_forces: dict[int, np.ndarray] = {}
    for element_id, element in model.elements.items():
        _, transform, length, k_local = _element_matrices(model, element_id)
        i = 3 * node_index[element.i_node]
        j = 3 * node_index[element.j_node]
        dofs = [i, i + 1, i + 2, j, j + 1, j + 2]
        element_displacements_local = transform @ displacement[np.asarray(dofs)]
        qx, qy = model.uniform_element_loads.get(element_id, np.zeros(2))
        equivalent_local = np.array([
            qx * length / 2.0,
            qy * length / 2.0,
            qy * length**2 / 12.0,
            qx * length / 2.0,
            qy * length / 2.0,
            -qy * length**2 / 12.0,
        ])
        element_end_forces[element_id] = (
            k_local @ element_displacements_local - equivalent_local
        )

    return AnalysisResult(
        node_order, displacements, reactions, stiffness, load, element_end_forces
    )
