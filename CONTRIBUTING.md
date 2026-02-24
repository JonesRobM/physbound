# Contributing to PhysBound

PhysBound validates physics claims against hard physical limits. Contributions that expand the set of validated physics domains are welcome.

## Getting Started

```bash
git clone https://github.com/JonesRobM/physbound.git
cd physbound
uv sync --all-extras
uv run pytest tests/ -v
```

## Architecture

```
src/physbound/
  server.py              # MCP tool definitions (entry points)
  errors.py              # PhysicalViolationError
  validators.py          # Input guard functions
  engines/
    constants.py         # CODATA constants via SciPy + Pint
    units.py             # Dimensional conversions
    link_budget.py       # FSPL, aperture gain, Friis transmission
    noise.py             # Thermal noise, Friis cascade, sensitivity
    shannon.py           # Shannon-Hartley capacity
  models/
    common.py            # PhysBoundResult base class
    link_budget.py       # LinkBudgetInput/Output
    noise.py             # NoiseFloorInput/Output
    shannon.py           # ShannonInput/Output
```

## Adding a New Physics Validator

1. **Create the engine** in `src/physbound/engines/`. Use existing constants from `constants.py` — never hardcode physical constants. All formulas should cite their source law.

2. **Create Pydantic models** in `src/physbound/models/` for input validation and structured output. Extend `PhysBoundResult` for the output.

3. **Add guard functions** to `validators.py` if your domain introduces new physical constraints (e.g., positive pressure, valid wavelength range).

4. **Expose the MCP tool** in `server.py`. Follow the existing pattern: validate via the model, compute via the engine, catch `PhysicalViolationError`, return serialized output.

5. **Write tests** covering:
   - Known reference values (e.g., textbook examples with exact numbers)
   - Boundary conditions and edge cases
   - Violation detection (impossible inputs that should raise `PhysicalViolationError`)
   - At least one "hallucination case" in `test_marketing.py` showing a real LLM failure mode

6. **Document formulas** in `docs/formulas.md`.

## Error Design

All physics violations must raise `PhysicalViolationError` with:
- `law_violated`: The specific physical law (e.g., "Shannon-Hartley Theorem")
- `latex_explanation`: LaTeX formula showing why the violation occurs
- `computed_limit` and `claimed_value`: The numbers that conflict

Errors should explain what's wrong, not just that something is wrong.

## Code Standards

- **Linting**: `ruff check src/ tests/` and `ruff format --check src/ tests/`
- **Type checking**: `mypy src/physbound/`
- **Tests**: `pytest tests/ -v` — all tests must pass
- **Python**: 3.12+ (type union syntax `X | Y` is used throughout)
- **Line length**: 100 characters
- **Constants**: Always from SciPy CODATA via `constants.py`, never raw floats
- **Units**: Use Pint quantities where dimensional correctness matters

## Pull Request Process

1. Fork the repository and create a feature branch
2. Ensure `ruff check`, `ruff format --check`, `mypy`, and `pytest` all pass
3. Add or update tests — aim for >90% coverage of new code
4. Update `docs/formulas.md` if adding new physics
5. Add a hallucination example to `test_marketing.py` if applicable
6. Submit a PR with a clear description of the physics being validated
