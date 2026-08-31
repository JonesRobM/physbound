<!-- mcp-name: io.github.JonesRobM/physbound -->
<!-- keywords: MCP server, physics validation, RF link budget, Shannon-Hartley, thermal noise, antenna gain, aperture limit, Harrington bound, AI hallucination detection, physical layer linter, Friis equation, FSPL, signal processing, telecommunications, radar range equation, radar cross section, RCS, radar ambiguity, pulse-Doppler, Doppler shift, unambiguous range, blind speed, range-Doppler dilemma -->

<p align="center">
  <img src="Avatar.png" alt="PhysBound" width="200">
</p>

<h1 align="center">PhysBound</h1>

**Physical Layer Linter** — An [MCP server](https://modelcontextprotocol.io) that validates RF and physics calculations against hard physical limits. Catches AI hallucinations in engineering workflows.

[![CI](https://github.com/JonesRobM/physbound/actions/workflows/ci.yml/badge.svg)](https://github.com/JonesRobM/physbound/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/JonesRobM/physbound/graph/badge.svg)](https://codecov.io/gh/JonesRobM/physbound)
[![PyPI](https://img.shields.io/pypi/v/physbound.svg)](https://pypi.org/project/physbound/)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-listed-green.svg)](https://registry.modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP Badge](https://lobehub.com/badge/mcp/jonesrobm-physbound)](https://lobehub.com/mcp/jonesrobm-physbound)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20PhysBound-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/jonesrobm)

---

## What LLMs Get Wrong

LLMs routinely hallucinate physics. PhysBound catches it:

| # | Category | LLM Hallucination | PhysBound Truth | Verdict |
|---|----------|-------------------|-----------------|---------|
| 1 | Shannon-Hartley | A 20 MHz 802.11n channel with 15 dB SNR can achieve 500 Mbps | Shannon limit: 100.6 Mbps (not 500 Mbps) | CAUGHT |
| 2 | Shannon-Hartley | A 100 MHz 5G channel with 20 dB SNR delivers 2 Gbps | Shannon limit: 665.8 Mbps (not 2000 Mbps) | CAUGHT |
| 3 | Antenna Aperture | A 30 cm dish antenna at 1 GHz provides 45 dBi gain | Physical limit: 12.1 dBi (Harrington); aperture eta=1: 9.9 dBi; typical dish: 7.4 dBi (eta=0.55) (not 45 dBi) | CAUGHT |
| 4 | Thermal Noise | Receiver noise floor of -180 dBm/Hz at room temperature | Thermal noise floor: -174.0 dBm/Hz at 290K (not -180 dBm/Hz) | CAUGHT |
| 5 | Link Budget / FSPL | Wi-Fi at 2.4 GHz with 20 dBm TX reaches 10 km with -40 dBm RX power | Actual RX power at 10 km: -94.1 dBm (not -40 dBm) | CAUGHT |
| 6 | Link Budget / FSPL | A 1W transmitter at 12 GHz with 0 dBi antennas reaches GEO at -80 dBm | Actual RX power at GEO: -175.1 dBm (not -80 dBm) | CAUGHT |
| 7 | Link Budget / FSPL | Bluetooth at 2.4 GHz with 0 dBm TX and 0 dBi antennas reaches 1 km at -60 dBm | Actual RX power at 1 km: -100.1 dBm (not -60 dBm) | CAUGHT |
| 8 | Shannon-Hartley | A 10 MHz LTE channel at 10 dB SNR supports 1 Gbps | Shannon limit: 34.6 Mbps (not 1000 Mbps) | CAUGHT |
| 9 | Noise Cascade | Receiver NF is the same regardless of stage order: LNA(20dB/1.5dB) + Mixer(10dB/8dB) | LNA first: 1.66 dB vs mixer first: 8.03 dB (penalty: 6.4 dB) | CAUGHT |
| 10 | Antenna Aperture | A 10 cm patch antenna at 900 MHz provides 20 dBi gain | Physical limit: 4.4 dBi (Harrington, D < lambda); aperture eta=1: -0.5 dBi; typical: -3.1 dBi (eta=0.55) (not 20 dBi) | CAUGHT |
| 11 | Radar Range Equation | Doubling transmit power doubles radar detection range | Range increases by factor 1.189 (2^(1/4) = 1.189), not 2.0 | CAUGHT |
| 12 | Radar Range Equation | Small drone (0.01 m^2 RCS) detectable at 200 km by 1 kW X-band radar with 30 dBi gain | Max range: 2.7 km for 0.01 m^2 RCS at 1 kW X-band (not 200 km) | CAUGHT |
| 13 | Antenna Gain | A 0.5 m user-terminal dish at 12 GHz gives 50 dBi gain | Physical limit: 36.1 dBi (Harrington); typical dish: 33.4 dBi (eta=0.55) (not 50 dBi) | CAUGHT |
| 14 | Antenna Gain | A 3 m dish at 10 GHz is in its far field at 10 m, so gain can be measured there | Far-field distance 2D^2/lambda = 600 m; 10 m is in the near field | CAUGHT |
| 15 | Radar Ambiguity | A 10 GHz radar at 10 kHz PRF unambiguously measures 500 m/s | v_ua = lambda*PRF/4 = +/-74.9 m/s (blind speed 149.9 m/s); 500 m/s aliases (not 500 m/s) | CAUGHT |
| 16 | Radar Ambiguity | A 10 GHz pulse-Doppler radar can unambiguously cover 150 km and +/-300 m/s at once | R_ua*v_ua = c*lambda/8 = 1.123e+06 m^2/s for any PRF; claimed 4.5e+07 m^2/s (40x too large) | CAUGHT |

*Generated automatically by `pytest tests/test_marketing.py -s`*

---

## Quick Start

### Install

```bash
pip install physbound
```

### MCP Client Configuration

Add PhysBound to any MCP-compatible client. For example, in Claude Desktop (`claude_desktop_config.json`), Cursor, or Windsurf:

```json
{
  "mcpServers": {
    "physbound": {
      "command": "uvx",
      "args": ["physbound"]
    }
  }
}
```

> **First run:** `uvx` downloads ~60 MB of dependencies (scipy, numpy) on first launch. Run `uvx physbound` once in your terminal to pre-cache them — subsequent starts will be instant.

Your AI assistant now has access to physics-validated RF calculations.

---

## Tools

### `rf_link_budget`

Computes a full RF link budget using the Friis transmission equation. Validates antenna gains against aperture limits.

**Example:** *"What's the received power for a 2.4 GHz link at 100 m with 20 dBm TX, 10 dBi TX gain, 3 dBi RX gain?"*

Returns: FSPL, received power, wavelength, and optional antenna gain limit checks. The hard limit is `G_max = max((pi * D / lambda)^2, (ka)^2 + 2ka)` with `k = 2pi/lambda`, `a = D/2` — the larger of the eta = 1 aperture value and Harrington's bound for an antenna enclosed in a sphere of diameter D (the two agree for D >> lambda; Harrington governs for electrically small antennas, D < lambda). Gains above it are rejected; gains above the typical-efficiency value `0.55 * (pi * D / lambda)^2` are accepted with a warning. Also reports which bound applies (`limiting_bound`), warns inside the far-field distance `2D^2/lambda`, and rejects negative losses.

### `shannon_hartley`

Computes Shannon-Hartley channel capacity `C = B * log2(1 + SNR)` and validates throughput claims.

**Example:** *"Can a 20 MHz channel with 15 dB SNR support 500 Mbps?"*

Returns: Theoretical capacity, spectral efficiency, and whether the claim is physically possible. Flags violations with the exact percentage by which the claim exceeds the Shannon limit.

### `noise_floor`

Computes thermal noise power `N = k_B * T * B`, cascades noise figures through multi-stage receivers using the Friis noise formula, and calculates receiver sensitivity.

**Example:** *"What's the noise floor for a 1 MHz receiver at 290K with a two-stage LNA chain?"*

Returns: Thermal noise in dBm and watts, cascaded noise figure, effective input noise temperature `T_e = 290 K * (F - 1)`, and receiver sensitivity.

### `radar_range`

Computes the monostatic radar range equation `R_max = [P_t G^2 lambda^2 sigma / ((4pi)^3 S_min L)]^(1/4)` and validates detection range claims.

**Example:** *"Can a 1 kW X-band radar with 30 dBi gain detect a 0.01 m^2 drone at 200 km?"*

Returns: Maximum detection range, minimum detectable signal, wavelength, and intermediate values. Catches the common fourth-root fallacy where doubling power is incorrectly assumed to double range.

### `antenna_gain`

Computes aperture gain limits, beamwidth and far-field distance for a single antenna given its diameter or physical area, and validates gain claims against the eta = 1 aperture value `(pi * D / lambda)^2` and Harrington's bound `(ka)^2 + 2ka`.

**Example:** *"Can a 0.5 m dish at 12 GHz really give 50 dBi? What beamwidth should I expect?"*

Returns: Physical gain limit, eta = 1 aperture value, Harrington bound and which one governs, typical gain at the given efficiency (default 0.55), effective aperture, half-power beamwidth (`70 lambda/D` tapered, `58.4 lambda/D` uniform), far-field distance `2D^2/lambda`, and for a claimed gain the implied aperture efficiency and validity.

### `radar_ambiguity`

Computes pulse-Doppler radar ambiguity limits for a given carrier and PRF: maximum unambiguous range `R_ua = c / (2 PRF)`, unambiguous velocity `v_ua = lambda PRF / 4`, first blind speed `lambda PRF / 2`, target Doppler shift `f_d = 2 v_r / lambda` and aliasing, range resolution `c tau / 2` (or `c / 2B` with pulse compression), and the range-Doppler dilemma invariant `R_ua v_ua = c lambda / 8`.

**Example:** *"Can a 10 GHz radar at 10 kHz PRF unambiguously measure a 500 m/s target out to 150 km?"*

Returns: Unambiguous range and velocity, blind speed, Doppler shift and apparent (aliased) velocity, range resolution, minimum range, duty cycle, and the `c lambda / 8` invariant. Rejects unambiguous range, velocity or resolution claims that the PRF or pulse cannot support.

---

## Physics Guarantees

Every calculation is validated against hard physical limits:

- **Speed of light:** `c = 299,792,458 m/s` — no exceptions
- **Thermal noise floor:** `N = -174 dBm/Hz` at 290K — the IEEE standard reference
- **Shannon limit:** `C = B * log2(1 + SNR)` — no throughput claim exceeds this
- **Antenna gain limit:** `G_max = max((pi * D / lambda)^2, (ka)^2 + 2ka)` — the eta = 1 aperture value for planar apertures and Harrington's bound for any antenna in a sphere of diameter D; eta = 0.55 is a warning threshold, not a limit
- **Radar range equation:** `R_max = [P_t G^2 lambda^2 sigma / ((4pi)^3 S_min)]^(1/4)` — range obeys the fourth-root law
- **Receiver sensitivity:** `S_min = k (T_A + T_0 (F - 1)) B * SNR` with `T_e = T_0 (F - 1)` referenced to 290 K
- **Unambiguous range:** `R_ua = c / (2 PRF)` — echoes beyond it fold into a later pulse interval
- **Unambiguous velocity:** `v_ua = lambda PRF / 4` — Doppler is sampled at the PRF, so `|f_d| <= PRF/2`
- **Range-Doppler dilemma:** `R_ua * v_ua = c lambda / 8` — no PRF choice beats it for a given carrier

Violations return structured `PhysicalViolationError` responses with LaTeX explanations, not silent failures.

---

## Examples

See PhysBound catching hallucinations in real time:

- **[Catching Hallucinations](examples/catching-hallucinations.md)** — walkthrough of five real LLM failure modes with full JSON responses
- **[Interactive Demo Notebook](examples/physbound-demo.ipynb)** — hands-on Jupyter notebook calling the physics engines directly

---

## Development

```bash
# Clone and install
git clone https://github.com/JonesRobM/physbound.git
cd physbound
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Print hallucination delta table
uv run pytest tests/test_marketing.py -s

# Start MCP server locally
uv run physbound
```

## Why PhysBound?

AI coding assistants are increasingly used in RF engineering, telecommunications, radar and signal processing workflows. But LLMs have no intrinsic understanding of physics. They generate plausible-sounding numbers that can violate fundamental laws like Shannon-Hartley, thermodynamic noise limits, antenna gain bounds and pulse-Doppler ambiguity limits.

PhysBound acts as a **physics guardrail** for any MCP-compatible AI assistant. Every calculation is checked against CODATA physical constants via SciPy, with dimensional analysis enforced through Pint. Violations return structured errors with LaTeX explanations, not silent failures.

### Use cases

- **RF system design review** — validate link budgets, receiver sensitivity, and noise cascades
- **Telecom proposal vetting** — catch impossible throughput claims before they reach a customer
- **Educational tools** — teach Shannon-Hartley, Friis transmission, and thermal noise with verified calculations
- **CI/CD for physics** — integrate as a validation step in engineering pipelines

## Support

If PhysBound is useful in your work, consider [buying me a coffee](https://ko-fi.com/jonesrobm).

## License

MIT License. See [LICENSE](LICENSE).

## Related

- [Model Context Protocol](https://modelcontextprotocol.io) — the open standard for AI tool integration
- [MCP Server Registry](https://registry.modelcontextprotocol.io) — official directory of MCP servers
- [FastMCP](https://github.com/jlowin/fastmcp) — Python framework for building MCP servers
