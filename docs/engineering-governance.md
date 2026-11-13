# Engineering governance and verification policy

## Safety boundary

StructuraLab is a research and development project, not a substitute for
engineering judgement, independent checking, peer review, or applicable
regulatory approval. Do not use its outputs for construction or permit
submissions unless and until a qualified engineer has independently validated
the software and its use for the specific project.

## Calculation traceability

Every design check must record:
- selected ACI 318 edition and jurisdictional amendments;
- clause/table/equation reference and source provenance;
- input values, units, assumptions and applicability limits;
- intermediate values and governing limit state;
- pass/fail/indeterminate outcome and reason;
- software version and calculation timestamp.

## Verification hierarchy

1. Dimensional and input-validation tests.
2. Unit tests for each mathematical function.
3. Analytical solutions for simple determinate structures.
4. Equilibrium checks: applied loads versus reactions.
5. Mesh/element refinement and convergence studies where relevant.
6. Independent comparison against trusted software or hand calculations.
7. Regression tests for previously verified cases.
8. Independent engineering review before any production claim.

A test passing is evidence only for the tested case and assumptions. It is not
proof that the program is generally correct or code-compliant.

## ACI implementation policy

Do not copy copyrighted code text or tables into the repository. Implement
equations from properly licensed/authorized references, cite clause identifiers
and document interpretation decisions. Pin one edition per module. Never
silently mix editions or invent missing factors.

## Load combination governance

Load combinations are deliberately user-defined at this stage. The software must
not label a factor set as ACI, ASCE, or jurisdictionally compliant until the exact
standard edition, amendments, load categories, limit state, and applicability
conditions are implemented and independently verified. Self-weight uses explicit
material density and a documented gravity constant; no density is silently
assumed. Force diagrams use documented local member sign conventions and are
subject to equilibrium and analytical benchmark tests.
