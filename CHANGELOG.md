# Changelog

All notable changes to PhysBound are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [0.1.2] - 2025-02-24

### Added
- Project logo in README header
- Ko-fi donation link and GitHub Sponsor button
- SEO metadata, badges, keywords, and PyPI classifiers for discoverability

## [0.1.1] - 2025-02-24

### Added
- MCP registry metadata (`server.json`) for official MCP server listing
- Smithery CLI configuration (`smithery.yaml`)

### Changed
- Genericized MCP client configuration in README (supports Claude Desktop, Cursor, Windsurf)

## [0.1.0] - 2025-02-24

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

[0.1.3]: https://github.com/JonesRobM/physbound/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/JonesRobM/physbound/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/JonesRobM/physbound/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/JonesRobM/physbound/releases/tag/v0.1.0
