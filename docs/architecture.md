
# StructuraLab Architecture

## 1. Project scope

StructuraLab is an auditable structural analysis and engineering software
platform. Its initial implementation focuses on transparent, testable
structural analysis rather than attempting to implement every engineering
workflow at once.

Version 0.5.0 builds on the 2D linear-elastic frame solver introduced in
earlier versions. It strengthens model validation, introduces global
equilibrium auditing, and expands independent verification.

The architecture is intended to evolve incrementally. Components should be
introduced when they have implemented functionality rather than creating
empty packages for features that are only planned.

## 2. Architectural boundaries

The long-term architecture is organised around the following responsibilities.

1. **Domain model** — structural geometry, nodes, materials, sections,
   elements, restraints, and applied loads. The model defines the structural
   system independently of user interfaces.

2. **Analysis engine** — element formulations, stiffness assembly, boundary
   conditions, solution procedures, and recovery of structural results.

3. **Load management** — independently named load cases, user-defined linear
   load combinations, and automatic generation of member self-weight.

4. **Validation and verification** — input validation, equilibrium auditing,
   analytical benchmarks, regression tests, and independent solver comparisons.

5. **Design-code engine** — future edition-specific design provisions,
   applicability checks, strength calculations, and detailing requirements.
   Design calculations must remain separate from the analysis solver.

6. **Application and reporting** — future project management, persistence,
   visualisation, APIs, and engineering reports.

7. **Interoperability** — import/export adapters and independent comparisons
   with external structural analysis tools such as OpenSeesPy.

External solver results are used as independent comparisons. They do not
silently replace StructuraLab's own analysis results.

## 3. Current implementation

The current source tree uses a compact Python package:

- `src/structuralab/model.py` — structural entities, model data, input
  validation, and load definitions.
- `src/structuralab/solver.py` — linear-static frame analysis, stiffness
  assembly, solution, reactions, and local member-end forces.
- `src/structuralab/loadcases.py` — load combinations and analysis of
  combinations, including sampled member-force diagrams.
- `src/structuralab/equilibrium.py` — global force and moment equilibrium
  auditing.
- `tests/` — model validation, solver, load-case, equilibrium, and independent
  verification tests.

This layout is deliberately smaller than the long-term architecture.
Responsibilities can be extracted into dedicated packages as the platform
grows.

## 4. Structural model and validation

`FrameModel` represents a two-dimensional structural frame.

Each node has three degrees of freedom:

- `ux` — global horizontal displacement.
- `uy` — global vertical displacement.
- `rz` — in-plane rotation.

The model stores nodes, frame elements, materials, sections, restraints,
nodal loads, and distributed member loads.

Model validation checks structural input consistency before analysis. This
includes:

- Node identifiers and finite coordinates.
- Material and section names and properties.
- Element identifiers and references to existing nodes, materials, and
  sections.
- Non-zero element lengths.
- Restraint definitions and their Boolean degrees of freedom.
- Load-case names, load references, vector dimensions, and finite values.

Validation checks input integrity. It does not establish that a structure is
stable or suitable for construction. A model with insufficient restraints
may pass input validation but still produce an unstable analysis system.

## 5. Analysis solver

The initial analysis engine implements a two-dimensional, first-order,
small-displacement, linear-elastic Euler-Bernoulli frame formulation.

Element stiffness matrices are formed in local coordinates and transformed
into global coordinates. The solver assembles the global stiffness matrix
and load vector, applies essential restraints, and solves for the free
degrees of freedom.

The solver recovers:

- Nodal displacements.
- Support reactions.
- The assembled global stiffness matrix.
- The assembled global load vector.
- Local element-end forces.

The global load vector includes nodal loads and consistent equivalent nodal
loads generated from uniform member loads.

The current implementation supports nodal actions and constant distributed
member loads in local element axes.

The following capabilities are outside the current solver scope:

- Three-dimensional structural analysis.
- Geometric and material nonlinear analysis.
- P-Delta effects and other second-order analysis.
- Shear-deformable beam formulations.
- Member releases and connection flexibility.
- Support settlements.
- Member point loads and partial-span or varying distributed loads.
- Automated reinforced-concrete member design.

These features require separate implementation and verification.

## 6. Load cases, combinations, and self-weight

`FrameModel` supports independently named load cases.

The original top-level nodal and member-load dictionaries are retained as
the reserved `default` load case for backward compatibility.

`LoadCombination` represents a user-defined linear mapping of load-case
names to numerical factors.

`analyze_combinations` evaluates combinations independently by assembling
each combination into a temporary model and solving it separately. The
source model is not mutated.

The analysis workflow also supports sampled local member-force diagrams.

Automatic member self-weight is generated using:

`density * area * gravity`

The global gravity vector is transformed into each member's local axes.
Consequently, inclined members can receive both local axial and transverse
self-weight components.

A missing or zero material density is an error when self-weight is requested.

The generic load-combination mechanism does not embed code-prescribed load
factors. Factors are supplied by the user.

## 7. Global equilibrium auditing

Version 0.5.0 introduces a separate global equilibrium audit.

The audit evaluates the assembled global load vector and the support
reactions returned by the analysis result.

For a two-dimensional frame, it checks:

- Horizontal force equilibrium.
- Vertical force equilibrium.
- Moment equilibrium about the global origin.

The moment calculation accounts for the moment arms of horizontal and
vertical forces at their respective node coordinates.

The audit reports the residual for each equilibrium equation and its
corresponding tolerance.

The tolerances combine configurable absolute and relative components:

` tolerance = absolute_tolerance + relative_tolerance * sum(abs(contributions)) `

The result includes an `is_equilibrated` status indicating whether all three
residuals are within their calculated tolerances.

The audit also checks relevant result consistency, including node ordering,
global load-vector dimensions, and support-reaction references.

Equilibrium auditing is a numerical consistency check. It does not prove
that the structural model is correct, that the structure is stable, or that
the design satisfies an engineering code.

## 8. Verification strategy

StructuraLab uses multiple levels of verification.

### Unit and regression tests

Tests cover model construction, validation rules, load handling, solver
behaviour, load combinations, and equilibrium auditing.

Regression tests help ensure that changes to existing functionality do not
silently alter established results.

### Analytical comparisons

Selected frame problems are compared against known analytical solutions.
These provide independent checks for displacements, reactions, and member
response.

### OpenSeesPy comparisons

Where OpenSeesPy is installed, independent verification tests compare
StructuraLab results against separately constructed OpenSeesPy models.

The current verification suite includes:

- A horizontal cantilever with a tip point load.
- A horizontal cantilever with a uniform transverse load.
- An inclined cantilever subjected to combined global horizontal and
  vertical point loads.

These comparisons provide additional confidence in the implementation.
They do not constitute formal certification or proof of correctness for
every possible structural configuration.

OpenSeesPy is an optional verification dependency rather than a requirement
for using the core analysis package.

## 9. Units and conventions

The current implementation uses SI units:

- Length: metres (m).
- Force: newtons (N).
- Stress and elastic modulus: pascals (Pa).
- Density: kilograms per cubic metre (kg/m³).
- Rotation: radians.

The global coordinate system is two-dimensional. Nodal degrees of freedom
are ordered as horizontal displacement, vertical displacement, and
in-plane rotation.

Member distributed loads are defined in local element axes. Transformations
between local and global coordinates are performed by the analysis engine.

Users are responsible for supplying dimensionally consistent input data.

## 10. Future development

The following are architectural directions, not claims of implemented
functionality.

Potential future development includes:

- Additional element formulations and load types.
- More extensive stability and numerical diagnostics.
- Three-dimensional structural analysis.
- Second-order and nonlinear analysis.
- Edition-pinned ACI 318 reinforced-concrete design.
- Reinforcement detailing and design reporting.
- Project persistence and structured engineering reports.
- Visualisation and application interfaces.
- Additional independent analytical and published benchmark problems.

A future package layout may separate responsibilities into:

- `domain/` — structural entities and units.
- `analysis/` — elements, assembly, solvers, and result recovery.
- `loads/` — load cases, patterns, and combinations.
- `design/aci318/` — edition-specific design provisions.
- `verification/` — analytical and benchmark cases.
- `reporting/` — traceable engineering reports.
- `api/` and `web/` — application interfaces.

These packages should be introduced when their functionality is implemented.

## 11. Engineering limitations and responsibility

StructuraLab is an early-stage engineering software project.

It is not approved for structural design, permitting, construction, or
independent professional certification.

Analysis results must be independently checked by a qualified structural
engineer before being used in engineering decisions.

No ACI 318 compliance or automated reinforced-concrete design capability
is claimed by the current release.
