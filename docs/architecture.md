# StructuraLab architecture

## Architectural boundaries

1. **Domain model** — units, geometry, materials, sections, supports, loads and
   structural entities. It must not depend on the API or user interface.
2. **Analysis engine** — element formulations, matrix assembly, solution
   strategies and result recovery. Solver assumptions are explicit.
3. **Design-code engine** — edition-specific ACI provisions, applicability
   rules, strength calculations and detailing checks. It consumes analysis
   demands but does not alter solver results.
4. **Verification layer** — unit tests, analytical solutions, published
   benchmarks where licensing permits, regression fixtures and independent
   cross-checks.
5. **Application layer** — API, persistence, project management, visualisation
   and reporting. It orchestrates domain services but contains no engineering
   equations.
6. **Interoperability** — import/export adapters and optional OpenSeesPy
   comparison workflows. External solvers are comparison tools, not silent
   authorities.

## Initial data flow

Project input -> validated domain model -> load case -> analysis solver ->
equilibrium and stability checks -> result object -> design demand extraction
-> ACI design checks -> report with assumptions and traceable references.

## Initial solver

The first solver is a 2D, first-order, linear-elastic Euler-Bernoulli frame
formulation. Each node has [ux, uy, rz]. Element stiffness is formed in local
coordinates and transformed into global coordinates. Essential restraints are
applied by partitioning the global system into free and restrained DOFs.

The solver accepts nodal actions and constant member loads in local element
axes. Uniform member loads are converted to consistent equivalent nodal loads
for global assembly; local member-end actions are recovered after solution.
Member point loads, partial-span or varying loads, releases, support
settlements, P-Delta effects, shear deformation, nonlinear response, and 3D
behaviour remain outside this milestone.

## Planned package layout

- `domain/`: canonical model entities and units
- `analysis/`: elements, assembly, solvers and result recovery
- `loads/`: load cases, patterns and combinations
- `design/aci318/`: edition-pinned design provisions
- `verification/`: analytical and benchmark cases
- `reporting/`: traceable engineering reports
- `api/` and `web/`: application interfaces

The current scaffold uses a smaller layout; packages will be split as features
are introduced rather than creating empty directories prematurely.

## Load-case and combination layer (v0.3.0)

`FrameModel` stores independently named load cases. The existing top-level nodal
and member-load dictionaries are retained as the reserved `default` case for
backward compatibility. `LoadCombination` is a linear mapping from case names to
user-supplied factors. `analyze_combinations` assembles each combination into a
separate temporary model, solves it independently, and returns analysis results
and sampled local member-force diagrams. The source model is not mutated.

Self-weight is generated per element from `density * area * gravity`. The global
gravity vector is transformed into the member's local axes, so inclined members
receive both local axial and transverse components. A missing/zero density is a
hard error when self-weight is requested. No code-prescribed load factors are
embedded in this generic combination mechanism.
