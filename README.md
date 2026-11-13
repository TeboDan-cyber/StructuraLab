# StructuraLab

**An integrated, auditable structural engineering analysis and design platform.**

StructuraLab is an early-stage engineering software project. Version 0.4.0 provides a transparent 2D linear-elastic frame solver, independent load cases, user-defined linear load combinations, automatic member self-weight, sampled local member-force diagrams, and independent OpenSeesPy verification benchmarks.

> **Engineering-use notice:** This project is not approved for design, permitting, or construction use. Results require independent verification by a qualified structural engineer. The load combinations are user-defined; no jurisdictional or ACI load-factor set is asserted by the software.

## Current implementation (v0.4.0)

- 2D Euler-Bernoulli frame elements with `ux`, `uy`, and `rz` at each node.
- Local/global stiffness transformation and direct-stiffness assembly.
- Nodal loads and constant local-axis member loads (`qx`, `qy`).
- Independent named load cases and user-defined linear combinations.
- Automatic member self-weight from material density, section area, and gravity.
- Reactions, displacements, and local member-end actions.
- Sampled local axial-force, shear-force, and bending-moment diagrams.
- Independent OpenSeesPy verification for cantilever point-load and uniform-load benchmarks.
- Analytical checks for displacement and support reactions.
- SI units: m, N, Pa, kg/m³; rotations in radians.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
pytest
```

To install the optional independent verification dependency:

```bash
python -m pip install -e ".[dev,verification]"
python -m pytest -v
```

## Load cases and combinations

```python
import numpy as np
from structuralab.model import FrameModel, Material, Section
from structuralab.loadcases import LoadCombination, analyze_combinations

model = FrameModel()
model.add_node(1, 0.0, 0.0)
model.add_node(2, 4.0, 0.0)
model.add_material(Material("concrete", 25e9, density=2400.0))
model.add_section(Section("beam", area=0.15, inertia=0.003))
model.add_frame_element(1, 1, 2, "concrete", "beam")
model.fix_node(1)

model.add_load_case("D", include_self_weight=True)
model.add_load_case("L")
model.add_nodal_load(2, np.array([0.0, -10_000.0, 0.0]), load_case="L")
model.add_uniform_distributed_load(1, qy=-2_000.0, load_case="D")

combinations = [
    LoadCombination("D-only", {"D": 1.0}),
    LoadCombination("user-ULS", {"D": 1.2, "L": 1.6}),
]
results = analyze_combinations(model, combinations)
uls = results.combinations["user-ULS"]
print(uls.analysis.reactions[1])
print(uls.diagrams[1].shear)
print(uls.diagrams[1].moment)
```

The factors above are illustrative user inputs, not a claim that they are appropriate for a particular code, occupancy, jurisdiction, or design situation.

## Independent verification (v0.4.0)

The optional verification suite uses OpenSeesPy as an independent reference implementation for selected linear-elastic 2D frame benchmarks.

The initial benchmarks are:

1. A cantilever with a vertical point load at its free end.
2. A cantilever with a constant transverse uniform member load.

For each benchmark, the suite compares nodal displacement vectors and fixed-support reaction vectors between StructuraLab and OpenSeesPy. Selected vertical displacement, vertical reaction, and support moment values are also checked against closed-form Euler-Bernoulli beam solutions.

Cross-solver comparisons use `rtol=1e-8`, with absolute tolerances of `1e-10` for displacements and `1e-6` for reactions. Analytical checks use `rel=1e-10`.

OpenSeesPy is optional and is not required by the core solver.

These benchmarks verify only the stated model configurations and assumptions. They do not establish universal solver correctness, code compliance, or suitability for design, permitting, or construction.

## Engineering conventions and limitations

- Global +X is right, global +Y is up, and positive nodal rotation is counter-clockwise.
- Local element +x points from i-node to j-node; local +y is 90° counter-clockwise.
- `qx` and `qy` are constant local-axis loads in N/m.
- Material density is kg/m³.
- Self-weight acts in global negative Y.
- Combination factors are finite, dimensionless user inputs.
- Member diagram arrays are sampled from i to j.
- The solver remains first-order, small-displacement, and linear elastic.
- Not implemented: 3D elements, member point/partial-span/varying loads, releases, imposed support movements, P-Delta/geometric nonlinearity, material nonlinearity, automated code load combinations, or ACI member design.
- Singular free-DOF stiffness systems raise `StructuralInstabilityError`.

## Development roadmap

1. Foundation: 2D frame model, direct-stiffness solver, analytical tests.
2. Loading/results: load cases, combinations, self-weight, N/V/M diagrams.
3. Verification: independent OpenSeesPy comparisons, additional frame benchmarks, mesh/refinement studies, and broader loading verification.
4. ACI design: edition-pinned concrete beam flexure/shear checks, then column P-M interaction and detailing checks.
5. Application: API, persistence, browser-based modelling, and reporting.
6. Advanced analysis: 3D frames, second-order effects, nonlinear materials, and broader OpenSeesPy interoperability.

## ACI governance

ACI calculations will be isolated in edition-specific modules. Before implementing code checks, the project must pin the exact ACI 318 edition and applicable local amendments. Every check will expose its source reference, assumptions, units, applicability, intermediate values, and benchmark tests. The analysis solver does not certify code compliance.