# Changelog

All notable changes to PhysBound are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **LLM demo harness** (`demo/llm/`): asks a real model an RF question through any OpenAI-compatible chat endpoint (stdlib HTTP only, no SDK), records every response verbatim with a conditions file (model, endpoint, exact prompt, sampling parameters, trial count, timestamp, SHA-256 of the responses), then lints each answer with the same physbound tool functions the CLI uses. `replay` (default) needs no network or key and shows trial 0 plus outcome counts across all trials; `summary` tabulates scenarios; `--list` shows every trial. Two scenarios (`wifi-throughput` on `shannon_hartley`, `dish-gain` on `antenna_gain`), a VHS tape (`demo/llm/demo.tape`), and `tests/test_llm_demo.py`

### Changed
- Ruff no longer lints Jupyter notebooks (`extend-exclude = ["*.ipynb"]`), so the demo notebook's long print lines do not fail pre-commit

## [0.3.0] - 2026-08-29

### Added
- **antenna_gain** tool (`engines/antenna.py`, `models/antenna.py`) — standalone aperture gain calculator: `D_0 = (pi D / lambda)^2`, `G = eta D_0`, effective aperture `A_e = eta A_phys`, half-power beamwidth (`70 lambda/D` tapered, `58.4 lambda/D` uniform), far-field distance `2 D^2 / lambda`, equivalent diameter from area, and gain-claim validation with implied efficiency
- **radar_ambiguity** tool (`engines/doppler.py`, `models/doppler.py`) — pulse-Doppler ambiguity limits: `R_ua = c / (2 PRF)`, `v_ua = lambda PRF / 4`, first blind speed `lambda PRF / 2`, Doppler shift `f_d = 2 v_r / lambda` with aliasing / apparent velocity, range resolution `c tau / 2` or `c / (2 B)`, eclipsing minimum range, duty cycle, and the range-Doppler dilemma invariant `R_ua v_ua = c lambda / 8`; rejects unambiguous range / velocity / resolution claims and invalid pulse timing (`PRF <= 0`, `tau <= 0`, `tau PRF >= 1`)
- **Harrington bound** for electrically small antennas: the hard antenna gain limit is now `max((pi D / lambda)^2, (ka)^2 + 2ka)` with `k = 2 pi / lambda`, `a = D / 2` (Harrington 1960; Balanis). New engine functions `harrington_gain_limit_dbi`, `physical_gain_limit_dbi`, `limiting_bound_for`; new output fields `aperture_limit_dbi`, `harrington_limit_dbi`, `limiting_bound` (`"harrington"` for `D < lambda`, `"aperture"` otherwise) on `antenna_gain`, and `tx_/rx_physical_limit_dbi`, `tx_/rx_limiting_bound` on `rf_link_budget`. A 2.15 dBi half-wave dipole in a 0.1 m footprint at 900 MHz is now accepted (limit 4.4 dBi) where the aperture-only rule (−0.5 dBi) falsely rejected it
- Far-field (Fraunhofer) warning in `rf_link_budget` when `d < 2 D^2 / lambda`
- Python 3.14 added to the CI test matrix and PyPI classifiers
- 4 new hallucination cases (Starlink dish 50 dBi, 3 m dish far field at 10 m, 500 m/s at 10 kHz PRF, 150 km + 300 m/s at once): README table now has 16 rows
- `tests/test_coverage_gaps.py` (diameter guard, >300 GHz warning, Shannon input validator branches, `server.main`), property tests for Harrington monotonicity / `2ka` gap / regime label, MCP integration tests for both new tools
- **Command-line interface**: `physbound check <tool>` (`link-budget`, `shannon`, `noise`, `radar-range`, `antenna`, `radar-ambiguity`) runs the same validation code paths as the MCP tools from the terminal or CI — human-readable output by default, `--json` for the structured result, exit code 0 for valid, **1 for a physics violation**, 2 for usage errors; plus `physbound --version` and `physbound serve --transport {stdio,http} [--host] [--port]`. Bare `physbound` still starts the stdio MCP server, so existing client configs are unaffected
- `py.typed` marker shipped in the wheel, making the `Typing :: Typed` classifier real for downstream type-checkers
- MCP **resource** `docs://physbound/formulas` serving the full formula reference (packaged into the wheel as `physbound/data/formulas.md`), and MCP **prompts** `review_link_budget` and `validate_physics_claims`
- Documentation site (mkdocs-material with MathJax) deployed to GitHub Pages via `.github/workflows/docs.yml`
- Release automation: PyPI Trusted Publishing (OIDC, no token), GitHub Release with CHANGELOG-derived notes, and MCP-registry publish on version tags; Dependabot (uv + github-actions, grouped); 95% coverage floor in CI
- Community files: `SECURITY.md`, issue templates (bug report, physics-domain request), PR template, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `CITATION.cff`; VHS demo tape (`demo/demo.tape`)
- Pre-commit `detect-secrets` baseline (`.secrets.baseline`) committed so the hook works for contributors

### Changed
- **Aperture limit semantics**: the hard limit is the physical bound (`eta = 1` aperture value, now superseded by `max(aperture, Harrington)`); `eta = 0.55` is a *warning* threshold ("unusually efficient"), no longer a rejection. `aperture_efficiency` is validated `0 < eta <= 1` and only moves the warning threshold. Before/after for README rows: row 3 (0.3 m @ 1 GHz) limit 7.4 dBi (eta 0.55) -> 9.9 dBi (eta 1) -> **12.1 dBi** (Harrington); row 10 (0.1 m @ 900 MHz) −3.1 dBi -> −0.5 dBi -> **4.4 dBi**; 1 m @ 10 GHz 40.41 -> 40.49 dBi (large dishes change by < 0.1 dB)
- `PhysicalViolationError.computed_limit` for "Antenna Aperture Limit" is now the Harrington value; messages and LaTeX report both bounds and the implied planar-aperture efficiency `G_claim / (pi D / lambda)^2`
- `noise_floor`: effective input noise temperature `T_e = T_0 (F − 1)` with `T_0 = 290 K` (was referenced to the user temperature); receiver sensitivity `S_min = k (T_A + T_0 (F − 1)) B · SNR`, so the `N_floor(T) + NF + SNR` shortcut is only used when `T_A = 290 K`
- `tests/test_server.py` refactored to the public FastMCP 3 API (`mcp.get_tool`, `mcp.list_tools`)
- `server.py` instructions string now lists all six tools; pyproject keywords add `doppler`, `pulse-doppler`, `antenna-gain`, `harrington-bound`

### Fixed
- Negative `tx_losses_db` / `rx_losses_db` in `rf_link_budget` are rejected (conservation of energy), matching `radar_range`
- `radar_range` rejects `system_temperature_k <= 0`
- `docs/formulas.md` worked example slip `G_phys = 9.88 -> 9.9 dBi` corrected to 9.95 dBi (the 9.88 is the linear value)
- Pre-commit `.secrets.baseline` regenerated; CONTRIBUTING architecture tree and CHANGELOG dates corrected

### Dependencies
Runtime and dev dependencies re-pinned with range specifiers (previous floors were older and largely unbounded):

| Package | 0.3.0 constraint | Locked |
|---------|------------------|--------|
| fastmcp | `>=3.4,<4` | 3.4.7 |
| scipy | `>=1.15` | 1.18.1 |
| numpy | `>=2.2` | 2.5.2 |
| pydantic | `>=2.10,<3` | 2.13.5 |
| pint | `>=0.25` | 0.25.3 |
| ruff (dev) | `>=0.16,<0.17` | 0.16.5 |
| mypy (dev) | `>=2.3,<3` | 2.3.1 |
| pytest / pytest-cov (dev) | `>=9.1,<10` / `>=7.1,<8` | 9.1.1 |
| hypothesis / pre-commit (dev) | `>=6.100,<7` / `>=4.6,<5` | 6.165.10 |

## [0.2.0] - 2026-02-26

### Added
- **radar_range** tool — monostatic radar range equation with R_max computation and detection range validation
- 2 new validators: `validate_positive_power`, `validate_positive_rcs`
- 2 new hallucination cases: fourth-root power fallacy, drone RCS detection range
- Property-based tests for radar range monotonicity invariants (7 tests)
- Radar range formula reference in `docs/formulas.md`
- MCP integration tests for radar_range tool

## [0.1.3] - 2026-02-26

### Added
- GitHub Actions CI: pytest (Python 3.12/3.13 matrix), mypy, ruff lint + format
- Codecov coverage reporting and badge
- Example usage: markdown walkthrough and Jupyter notebook (`examples/`)
- Formula reference documentation (`docs/formulas.md`)
- CONTRIBUTING.md with architecture guide and PR process
- CHANGELOG.md
- Property-based tests with Hypothesis (19 invariant tests)
- 4 new hallucination cases in marketing test suite (Bluetooth range, LTE capacity, noise cascade ordering, small antenna UHF)
- MCP integration tests using FastMCP Client (8 end-to-end round-trip tests)
- GitHub Sponsors funding option
- Automated PyPI publish workflow on git tags

### Fixed
- Version mismatch between `__init__.py` and `pyproject.toml`
- Hardcoded Boltzmann constant in server.py replaced with canonical import
- All mypy type errors resolved (scipy stubs, type narrowing, annotations)
- All ruff lint and format issues resolved

## [0.1.2] - 2026-02-24

### Added
- Project logo in README header
- Ko-fi donation link and GitHub Sponsor button
- SEO metadata, badges, keywords, and PyPI classifiers for discoverability

## [0.1.1] - 2026-02-24

### Added
- MCP registry metadata (`server.json`) for official MCP server listing
- Smithery CLI configuration (`smithery.yaml`)

### Changed
- Genericized MCP client configuration in README (supports Claude Desktop, Cursor, Windsurf)

## [0.1.0] - 2026-02-24

### Added
- Initial release
- **rf_link_budget** tool — Friis transmission equation with FSPL, aperture limit validation, and antenna gain checking
- **shannon_hartley** tool — Shannon-Hartley channel capacity computation and throughput claim validation
- **noise_floor** tool — thermal noise power (kTB), Friis noise cascade for multi-stage receivers, receiver sensitivity
- 5 input validators: frequency, distance, bandwidth, temperature, SNR
- Structured `PhysicalViolationError` responses with LaTeX explanations
- Pint-based dimensional analysis throughout
- CODATA physical constants via SciPy
- Pydantic input/output models with field validation
- 107 tests covering all engines, validators, server integration, and marketing hallucination cases
- Pre-commit hooks: ruff, detect-secrets, large file checks

[Unreleased]: https://github.com/JonesRobM/physbound/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/JonesRobM/physbound/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/JonesRobM/physbound/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/JonesRobM/physbound/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/JonesRobM/physbound/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/JonesRobM/physbound/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/JonesRobM/physbound/releases/tag/v0.1.0
