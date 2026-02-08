# PhysBound

**Physical Layer Linter** — An MCP server that validates RF and physics calculations against hard physical limits. Catches AI hallucinations in engineering workflows.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-107%20passed-brightgreen.svg)]()

---

## What LLMs Get Wrong

LLMs routinely hallucinate physics. PhysBound catches it:

| # | Category | LLM Hallucination | PhysBound Truth | Verdict |
|---|----------|-------------------|-----------------|---------|
| 1 | Shannon-Hartley | "20 MHz 802.11n at 15 dB SNR achieves 500 Mbps" | Shannon limit: **100.6 Mbps** | CAUGHT |
| 2 | Shannon-Hartley | "100 MHz 5G channel at 20 dB SNR delivers 2 Gbps" | Shannon limit: **665.8 Mbps** | CAUGHT |
| 3 | Antenna Aperture | "30 cm dish at 1 GHz provides 45 dBi gain" | Aperture limit: **7.4 dBi** | CAUGHT |
| 4 | Thermal Noise | "Noise floor of -180 dBm/Hz at room temperature" | Actual: **-174.0 dBm/Hz** at 290K | CAUGHT |
| 5 | Link Budget | "Wi-Fi at 2.4 GHz reaches 10 km at -40 dBm" | Actual RX power: **-94.1 dBm** | CAUGHT |
| 6 | Link Budget | "1W to GEO with 0 dBi antennas at -80 dBm" | Actual RX power: **-175.1 dBm** | CAUGHT |

*Generated automatically by `pytest tests/test_marketing.py -s`*

---

## Quick Start

### Install

```bash
pip install physbound
```

### Use with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "physbound": {
      "command": "uv",
      "args": ["run", "--from", "physbound", "physbound"]
    }
  }
}
```

That's it. Claude now has access to physics-validated RF calculations.

---

## Tools

### `rf_link_budget`

Computes a full RF link budget using the Friis transmission equation. Validates antenna gains against aperture limits.

**Example:** *"What's the received power for a 2.4 GHz link at 100 m with 20 dBm TX, 10 dBi TX gain, 3 dBi RX gain?"*

Returns: FSPL, received power, wavelength, and optional aperture limit checks. Rejects antenna gains that violate `G_max = eta * (pi * D / lambda)^2`.

### `shannon_hartley`

Computes Shannon-Hartley channel capacity `C = B * log2(1 + SNR)` and validates throughput claims.

**Example:** *"Can a 20 MHz channel with 15 dB SNR support 500 Mbps?"*

Returns: Theoretical capacity, spectral efficiency, and whether the claim is physically possible. Flags violations with the exact percentage by which the claim exceeds the Shannon limit.

### `noise_floor`

Computes thermal noise power `N = k_B * T * B`, cascades noise figures through multi-stage receivers using the Friis noise formula, and calculates receiver sensitivity.

**Example:** *"What's the noise floor for a 1 MHz receiver at 290K with a two-stage LNA chain?"*

Returns: Thermal noise in dBm and watts, cascaded noise figure, system noise temperature, and receiver sensitivity.

---

## Physics Guarantees

Every calculation is validated against hard physical limits:

- **Speed of light:** `c = 299,792,458 m/s` — no exceptions
- **Thermal noise floor:** `N = -174 dBm/Hz` at 290K — the IEEE standard reference
- **Shannon limit:** `C = B * log2(1 + SNR)` — no throughput claim exceeds this
- **Aperture limit:** `G_max = eta * (pi * D / lambda)^2` — antenna gain is bounded by physics

Violations return structured `PhysicalViolationError` responses with LaTeX explanations, not silent failures.

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

## License

MIT License. See [LICENSE](LICENSE).
