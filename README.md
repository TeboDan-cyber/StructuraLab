
# StructuraLab

**An integrated, auditable structural engineering analysis and design platform.**

StructuraLab is an early-stage structural engineering software project. Version
0.5.0 provides a transparent 2D linear-elastic frame solver, independent load
cases, user-defined linear load combinations, automatic member self-weight,
sampled local member-force diagrams, structural model validation, global
equilibrium auditing, and independent OpenSeesPy verification benchmarks.

> **Engineering-use notice:** This project is not approved for design, permitting,
> or construction use. Results require independent verification by a qualified
> structural engineer. The load combinations are user-defined; no jurisdictional
> or ACI load-factor set is asserted by the software.

## Current implementation (v0.5.0)

### Structural analysis

- 2D Euler-Bernoulli frame elements with `ux`, `uy`, and `rz` at each node.
- Local/global stiffness transformation and direct-stiffness assembly.
- Nodal loads and constant local-axis member loads (`qx`, `qy`).
- Independent named load cases; the legacy unlabelled load interface remains as
  the reserved `default` case.
- Linear combinations with user-supplied factors.
- Automatic member self-weight from material density, section area, and gravity.
- Reactions, displacements, and local member-end actions for each combination.
- Sampled local axial-force, shear-force, and bending-moment diagram ordinates.

### Validation and verification

- Structural model validation for node, element, material, section, restraint,
  and load references and properties.
- Numerical input checks for invalid shapes and non-finite values.
- Global horizontal-force, vertical-force, and moment equilibrium auditing.
- Configurable absolute and relative equilibrium tolerances.
- Independent OpenSeesPy comparison benchmarks for:
  - Cantilever tip point loading.
  - Uniformly distributed member loading.
  - Inclined cantilever members under combined global horizontal and vertical
    tip loading.
- Analytical comparisons against closed-form cantilever solutions.

### Units and conventions

- SI units: m, N, Pa, kg/m³.
- Rotations in radians.
- Global +X is right and global +Y is up.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

To run the independent OpenSeesPy verification tests as well, install the
optional verification dependency:

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

The factors above are illustrative user inputs, **not** a claim that they are
appropriate for a particular code, occupancy, jurisdiction, or design situation.

## Global equilibrium auditing

The equilibrium auditing module checks whether the applied global load vector
and support reactions balance in:

- Horizontal force.
- Vertical force.
- Moment about the global origin.

Example:

```python
from structuralab.equilibrium import audit_global_equilibrium
from structuralab.solver import solve_linear_static

result = solve_linear_static(model)
audit = audit_global_equilibrium(model, result)

print(audit.horizontal_force_residual)
print(audit.vertical_force_residual)
print(audit.moment_residual)
print(audit.is_equilibrated)
```

The audit uses configurable absolute and relative tolerances. Passing the audit
indicates numerical global equilibrium within those tolerances; it does not
establish structural adequacy, stability, code compliance, or design safety.

## Engineering conventions and limitations

- Global +X is right, global +Y is up, and positive nodal rotation is
  counter-clockwise.
- Local element +x points from i-node to j-node; local +y is 90 degrees
  counter-clockwise.
- `qx` and `qy` are constant local-axis loads in N/m and accumulate within a case.
- Material density is kg/m³. Density defaults to zero; requesting self-weight
  without a positive density raises an error rather than assuming a material value.
- Self-weight acts in global negative Y and is transformed into each member's local
  axes. `gravity` defaults to 9.80665 m/s² and can be overridden explicitly.
- Combination factors are finite, dimensionless user inputs. The same case may be
  used in multiple combinations; each combination is solved independently.
- Member diagram arrays are sampled from i to j. Their local sign convention is
  documented in `MemberDiagram`; diagram ordinates are not global-axis plots.
- The solver remains first-order, small-displacement, and linear elastic.
- Not implemented: 3D elements, member point/partial-span/varying loads, releases,
  imposed support movements, P-Delta/geometric nonlinearity, material nonlinearity,
  automated code load combinations, or ACI member design.
- Singular free-DOF stiffness systems raise `StructuralInstabilityError`.

## Development roadmap

1. Foundation: 2D frame model, direct-stiffness solver, analytical tests.
2. Loading/results: load cases, combinations, self-weight, N/V/M diagrams.
3. Verification: expanded frame benchmarks, independent solver comparisons,
   equilibrium auditing, and documented numerical tolerances.
4. ACI design: edition-pinned concrete beam flexure/shear checks, then column P-M
   interaction and detailing checks.
5. Application: API, persistence, browser-based modelling, and reporting.
6. Advanced analysis: 3D frames, second-order effects, nonlinear materials, and
   OpenSeesPy interoperability.

## ACI governance

ACI calculations will be isolated in edition-specific modules. Before implementing
code checks, the project must pin the exact ACI 318 edition and applicable local
amendments. Every check will expose its source reference, assumptions, units,
applicability, intermediate values, and benchmark tests. The analysis solver does
not certify code compliance.
