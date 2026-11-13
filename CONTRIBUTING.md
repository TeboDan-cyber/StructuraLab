# Contributing

- Keep engineering equations in domain/analysis/design modules, not UI code.
- State units in names or docstrings where ambiguity is possible.
- Add tests for normal, boundary, invalid and failure cases.
- Add an analytical benchmark before claiming a solver feature is verified.
- Record assumptions and limitations in documentation.
- Do not claim ACI compliance without edition-specific traceability and review.
- Run `pytest` and `ruff check .` before submitting changes.
