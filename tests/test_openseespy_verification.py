
"""Independent verification of StructuraLab against OpenSeesPy."""

import numpy as np
import pytest

from structuralab.model import FrameModel, Material, Section
from structuralab.solver import solve_linear_static

ops = pytest.importorskip("openseespy.opensees")

LENGTH = 4.0
ELASTIC_MODULUS = 200e9
AREA = 0.01
INERTIA = 8.0e-6


def build_structuralab_model() -> FrameModel:
    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(2, LENGTH, 0.0)
    model.add_material(Material("steel", ELASTIC_MODULUS))
    model.add_section(Section("section", AREA, INERTIA))
    model.add_frame_element(1, 1, 2, "steel", "section")
    model.fix_node(1)
    return model


def build_inclined_structuralab_model(angle_degrees: float) -> FrameModel:
    """Build a cantilever whose member is inclined to the global X-axis."""
    angle = np.radians(angle_degrees)

    model = FrameModel()
    model.add_node(1, 0.0, 0.0)
    model.add_node(
        2,
        LENGTH * np.cos(angle),
        LENGTH * np.sin(angle),
    )
    model.add_material(Material("steel", ELASTIC_MODULUS))
    model.add_section(Section("section", AREA, INERTIA))
    model.add_frame_element(1, 1, 2, "steel", "section")
    model.fix_node(1)

    return model


def run_opensees_point_load(load: float) -> tuple[np.ndarray, np.ndarray]:
    """Analyse a horizontal cantilever with a vertical tip load."""
    ops.wipe()
    try:
        ops.model("basic", "-ndm", 2, "-ndf", 3)
        ops.node(1, 0.0, 0.0)
        ops.node(2, LENGTH, 0.0)

        ops.fix(1, 1, 1, 1)
        ops.geomTransf("Linear", 1)
        ops.element(
            "elasticBeamColumn",
            1,
            1,
            2,
            AREA,
            ELASTIC_MODULUS,
            INERTIA,
            1,
        )

        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        ops.load(2, 0.0, -load, 0.0)

        ops.system("BandGeneral")
        ops.numberer("Plain")
        ops.constraints("Plain")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")

        assert ops.analyze(1) == 0

        ops.reactions()
        displacement = np.asarray(ops.nodeDisp(2), dtype=float)
        reaction = np.asarray(ops.nodeReaction(1), dtype=float)

        return displacement, reaction
    finally:
        ops.wipe()


def run_opensees_uniform_load(
    load_per_length: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Analyse a cantilever with a uniform local transverse member load."""
    ops.wipe()
    try:
        ops.model("basic", "-ndm", 2, "-ndf", 3)
        ops.node(1, 0.0, 0.0)
        ops.node(2, LENGTH, 0.0)

        ops.fix(1, 1, 1, 1)
        ops.geomTransf("Linear", 1)
        ops.element(
            "elasticBeamColumn",
            1,
            1,
            2,
            AREA,
            ELASTIC_MODULUS,
            INERTIA,
            1,
        )

        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        ops.eleLoad("-ele", 1, "-type", "-beamUniform", load_per_length)

        ops.system("BandGeneral")
        ops.numberer("Plain")
        ops.constraints("Plain")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")

        assert ops.analyze(1) == 0

        ops.reactions()
        displacement = np.asarray(ops.nodeDisp(2), dtype=float)
        reaction = np.asarray(ops.nodeReaction(1), dtype=float)

        return displacement, reaction
    finally:
        ops.wipe()


def run_opensees_inclined_point_load(
    angle_degrees: float,
    horizontal_load: float,
    vertical_load: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Analyse an inclined cantilever with a global-coordinate tip load."""
    angle = np.radians(angle_degrees)
    end_x = LENGTH * np.cos(angle)
    end_y = LENGTH * np.sin(angle)

    ops.wipe()
    try:
        ops.model("basic", "-ndm", 2, "-ndf", 3)
        ops.node(1, 0.0, 0.0)
        ops.node(2, end_x, end_y)

        ops.fix(1, 1, 1, 1)
        ops.geomTransf("Linear", 1)
        ops.element(
            "elasticBeamColumn",
            1,
            1,
            2,
            AREA,
            ELASTIC_MODULUS,
            INERTIA,
            1,
        )

        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        ops.load(2, horizontal_load, vertical_load, 0.0)

        ops.system("BandGeneral")
        ops.numberer("Plain")
        ops.constraints("Plain")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")

        assert ops.analyze(1) == 0

        ops.reactions()
        displacement = np.asarray(ops.nodeDisp(2), dtype=float)
        reaction = np.asarray(ops.nodeReaction(1), dtype=float)

        return displacement, reaction
    finally:
        ops.wipe()


def test_point_load_matches_openseespy_and_analytical_solution():
    load = 10_000.0

    model = build_structuralab_model()
    model.add_nodal_load(2, np.array([0.0, -load, 0.0]))
    result = solve_linear_static(model)

    reference_displacement, reference_reaction = run_opensees_point_load(load)

    np.testing.assert_allclose(
        result.displacements[2],
        reference_displacement,
        rtol=1e-8,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        result.reactions[1],
        reference_reaction,
        rtol=1e-8,
        atol=1e-6,
    )

    analytical_tip_displacement = (
        -load * LENGTH**3 / (3.0 * ELASTIC_MODULUS * INERTIA)
    )
    analytical_support_moment = load * LENGTH

    assert result.displacements[2][1] == pytest.approx(
        analytical_tip_displacement, rel=1e-10
    )
    assert result.reactions[1][1] == pytest.approx(load, rel=1e-10)
    assert result.reactions[1][2] == pytest.approx(
        analytical_support_moment, rel=1e-10
    )


def test_uniform_load_matches_openseespy_and_analytical_solution():
    load_per_length = -2_000.0

    model = build_structuralab_model()
    model.add_uniform_distributed_load(1, qy=load_per_length)
    result = solve_linear_static(model)

    reference_displacement, reference_reaction = run_opensees_uniform_load(
        load_per_length
    )

    np.testing.assert_allclose(
        result.displacements[2],
        reference_displacement,
        rtol=1e-8,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        result.reactions[1],
        reference_reaction,
        rtol=1e-8,
        atol=1e-6,
    )

    analytical_tip_displacement = (
        load_per_length * LENGTH**4 / (8.0 * ELASTIC_MODULUS * INERTIA)
    )
    total_load = abs(load_per_length) * LENGTH
    analytical_support_moment = total_load * LENGTH / 2.0

    assert result.displacements[2][1] == pytest.approx(
        analytical_tip_displacement, rel=1e-10
    )
    assert result.reactions[1][1] == pytest.approx(total_load, rel=1e-10)
    assert result.reactions[1][2] == pytest.approx(
        analytical_support_moment, rel=1e-10
    )


def test_inclined_member_point_load_matches_openseespy():
    angle_degrees = 30.0
    horizontal_load = 5_000.0
    vertical_load = -10_000.0

    model = build_inclined_structuralab_model(angle_degrees)
    model.add_nodal_load(
        2,
        np.array([horizontal_load, vertical_load, 0.0]),
    )
    result = solve_linear_static(model)

    reference_displacement, reference_reaction = (
        run_opensees_inclined_point_load(
            angle_degrees,
            horizontal_load,
            vertical_load,
        )
    )

    np.testing.assert_allclose(
        result.displacements[2],
        reference_displacement,
        rtol=1e-8,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        result.reactions[1],
        reference_reaction,
        rtol=1e-8,
        atol=1e-6,
    )

    assert result.reactions[1][0] == pytest.approx(
        -horizontal_load, rel=1e-10
    )
    assert result.reactions[1][1] == pytest.approx(
        -vertical_load, rel=1e-10
    )
