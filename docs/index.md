# PhysBound

**Physical Layer Linter** — an [MCP server](https://modelcontextprotocol.io) that validates RF and physics calculations against hard physical limits, catching AI hallucinations in engineering workflows.

LLMs generate plausible-sounding RF numbers that violate fundamental physics — throughput above the Shannon limit, antenna gains no aperture can produce, radar ranges the range equation forbids. PhysBound gives any MCP-compatible AI assistant six validated calculation tools, backed by CODATA constants (via SciPy) and dimensional analysis (via Pint). Impossible claims return structured `PhysicalViolationError` responses with the violated law, the computed limit, and a LaTeX explanation — not silent failures.

## The Six Tools

| Tool | What it validates |
|------|-------------------|
| `rf_link_budget` | Friis link budgets: FSPL, received power, antenna gains vs. aperture/Harrington limits |
| `shannon_hartley` | Throughput claims against channel capacity $C = B \log_2(1 + \mathrm{SNR})$ |
| `noise_floor` | Thermal noise $kTB$, Friis noise-figure cascades, receiver sensitivity |
| `radar_range` | Detection-range claims against the monostatic radar range equation |
| `antenna_gain` | Gain limits, beamwidth, and far-field distance for a single antenna |
| `radar_ambiguity` | Pulse-Doppler unambiguous range/velocity, Doppler aliasing, range resolution |

Every formula, constant, and validation guard is documented with sources in the [Formula Reference](formulas.md).

## How It Works

Ask your MCP-connected assistant an RF question — *"Can a 20 MHz channel with 15 dB SNR support 500 Mbps?"* — and it calls PhysBound instead of guessing. The answer comes back physics-validated:

- **Possible claims** return the full calculation: capacity, spectral efficiency, margins, and any applicability warnings.
- **Impossible claims** return a structured `PhysicalViolationError` naming the violated law (here, the Shannon–Hartley theorem: the 20 MHz / 15 dB channel caps out at 100.6 Mbps), the computed limit, the claimed value, and a LaTeX explanation of why.

## Physics Guarantees

Every calculation is checked against hard physical limits:

- **Speed of light:** $c = 299{,}792{,}458\ \mathrm{m/s}$ — no exceptions
- **Thermal noise floor:** $-174\ \mathrm{dBm/Hz}$ at 290 K — the IEEE standard reference
- **Shannon limit:** $C = B \log_2(1 + \mathrm{SNR})$ — no throughput claim exceeds this
- **Antenna gain limit:** $G_{\max} = \max\!\left[(\pi D/\lambda)^2,\ (ka)^2 + 2ka\right]$ — the $\eta = 1$ aperture value, or Harrington's bound for electrically small antennas
- **Radar range equation:** range obeys the fourth-root law — doubling power multiplies range by $2^{1/4} \approx 1.19$, not 2
- **Range–Doppler dilemma:** $R_{ua} \cdot v_{ua} = c\lambda/8$ — no PRF choice beats it for a given carrier

## Getting Started

- [Installation](install.md) — connect PhysBound to Claude Code, Claude Desktop, Cursor, Windsurf, or any MCP client
- [CLI](cli.md) — validate claims from the terminal or CI with `physbound check`
- [Formula Reference](formulas.md) — every formula with derivations and sources

PhysBound is MIT licensed and developed on [GitHub](https://github.com/JonesRobM/physbound). Contributions that expand the set of validated physics domains are welcome — see the [contributing guide](https://github.com/JonesRobM/physbound/blob/main/CONTRIBUTING.md).
