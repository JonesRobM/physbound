# Pull Request

## Summary

<!-- What does this PR change, and why? For a new validator: what physics is being validated? -->

## Checklist

<!-- See CONTRIBUTING.md for details on each item. Delete lines that don't apply
     (e.g. the physics items for a pure tooling/docs change). -->

### Code quality

- [ ] `uv run ruff check src/ tests/` passes
- [ ] `uv run ruff format --check src/ tests/` passes
- [ ] `uv run mypy src/physbound/` passes
- [ ] `uv run pytest tests/ -v` passes (new code has >90% coverage)

### Physics

- [ ] Every formula cites its source law (textbook chapter, standard, or paper)
- [ ] Physical constants come from SciPy CODATA via `constants.py` — no hardcoded floats
- [ ] Violations raise `PhysicalViolationError` with `law_violated`, `computed_limit`, `claimed_value`, and a `latex_explanation`
- [ ] A hallucination case is added to `tests/test_marketing.py` (a real LLM failure mode this change catches)
- [ ] `docs/formulas.md` is updated with the new formulas, sources, and a worked example

### Tests

- [ ] Known reference values (textbook examples with exact numbers)
- [ ] Boundary conditions and edge cases
- [ ] Violation detection (impossible inputs that raise `PhysicalViolationError`)

## Notes for the reviewer

<!-- Anything unusual: trade-offs, follow-ups, open questions. -->
