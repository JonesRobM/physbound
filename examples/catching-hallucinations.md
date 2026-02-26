# Catching LLM Hallucinations with PhysBound

This walkthrough shows PhysBound correcting three common LLM physics hallucinations in real time via the MCP protocol.

---

## Scenario 1: Impossible Wi-Fi Throughput

> **User to LLM:** "What throughput can I expect from a 20 MHz 802.11n channel with 15 dB SNR?"
>
> **LLM (without PhysBound):** "You can expect around 500 Mbps."

PhysBound's `shannon_hartley` tool is called automatically:

```json
{
  "bandwidth_hz": 20000000,
  "snr_db": 15.0,
  "claimed_throughput_bps": 500000000
}
```

**Response:**

```json
{
  "error": true,
  "violation_type": "PhysicalViolationError",
  "law_violated": "Shannon-Hartley Theorem",
  "message": "Claimed throughput 500000000.0 bps exceeds Shannon limit of 100556153.5 bps by 397.2%",
  "latex_explanation": "$C = B \\log_2(1 + \\text{SNR}) = 100.6\\,\\text{Mbps} < 500.0\\,\\text{Mbps}$",
  "computed_limit": 100556153.5,
  "claimed_value": 500000000.0,
  "unit": "bps"
}
```

The Shannon limit for a 20 MHz channel at 15 dB SNR is **100.6 Mbps** — not 500 Mbps. The LLM's claim exceeds the theoretical maximum by nearly 400%.

---

## Scenario 2: Impossible Antenna Gain

> **User to LLM:** "What gain does a 30 cm dish antenna provide at 1 GHz?"
>
> **LLM (without PhysBound):** "A 30 cm dish at 1 GHz gives about 45 dBi."

PhysBound's `rf_link_budget` tool catches this when aperture checking is enabled:

```json
{
  "tx_power_dbm": 20,
  "tx_antenna_gain_dbi": 45,
  "rx_antenna_gain_dbi": 0,
  "frequency_hz": 1000000000,
  "distance_m": 1000,
  "tx_antenna_diameter_m": 0.3
}
```

**Response:**

```json
{
  "error": true,
  "violation_type": "PhysicalViolationError",
  "law_violated": "Antenna Aperture Limit",
  "message": "TX antenna gain 45.0 dBi exceeds aperture limit of 7.4 dBi for 0.3 m dish at 1.00e+09 Hz",
  "latex_explanation": "$G_{\\max} = \\eta \\left(\\frac{\\pi D}{\\lambda}\\right)^2 = 7.4\\,\\text{dBi}$"
}
```

A 30 cm dish at 1 GHz has a wavelength of ~30 cm — meaning the dish is only about 1 wavelength across. The maximum achievable gain is **7.4 dBi**, not 45 dBi.

---

## Scenario 3: Wrong Noise Floor

> **User to LLM:** "What's the thermal noise floor at room temperature?"
>
> **LLM (without PhysBound):** "The noise floor is about -180 dBm/Hz at room temperature."

PhysBound's `noise_floor` tool returns the correct value:

```json
{
  "bandwidth_hz": 1.0,
  "temperature_k": 290.0
}
```

**Response:**

```json
{
  "thermal_noise_dbm": -173.98,
  "thermal_noise_watts": 3.99e-21,
  "human_readable": "Thermal Noise Floor:\n  Temperature: 290.0 K\n  Bandwidth:   0.000 MHz\n  Noise Power: -173.98 dBm (3.994e-21 W)"
}
```

The thermal noise floor at the IEEE standard reference temperature of 290K is **-174.0 dBm/Hz** (derived from the Boltzmann constant: N = kTB). The LLM's claim of -180 dBm/Hz would require a temperature of ~29 K — deep space, not room temperature.

---

## Scenario 4: Multi-Stage Receiver Design

> **User to LLM:** "I'm designing a receiver with an LNA (gain 20 dB, NF 1.5 dB) followed by a mixer (gain 10 dB, NF 8 dB). What's my system noise figure and sensitivity for 10 MHz bandwidth needing 10 dB SNR?"

PhysBound's `noise_floor` tool with cascading:

```json
{
  "bandwidth_hz": 10000000,
  "temperature_k": 290.0,
  "stages": [
    {"gain_db": 20.0, "noise_figure_db": 1.5},
    {"gain_db": 10.0, "noise_figure_db": 8.0}
  ],
  "required_snr_db": 10.0
}
```

**Response:**

```json
{
  "thermal_noise_dbm": -103.98,
  "thermal_noise_watts": 3.99e-14,
  "cascaded_noise_figure_db": 1.66,
  "system_noise_temp_k": 135.03,
  "receiver_sensitivity_dbm": -92.31,
  "human_readable": "Thermal Noise Floor:\n  Temperature: 290.0 K\n  Bandwidth:   10.000 MHz\n  Noise Power: -103.98 dBm (3.99e-14 W)\n  Cascaded NF: 1.66 dB\n  Sensitivity: -92.31 dBm"
}
```

The Friis noise cascade shows that the LNA's low noise figure dominates — the 8 dB mixer NF is suppressed by the LNA's 20 dB gain to contribute only ~0.16 dB to the system NF. This is why **LNA-first order matters** in receiver design.

---

## Key Takeaway

PhysBound doesn't just catch wrong numbers — it explains *why* they're wrong, citing the specific physical law violated and providing the LaTeX formula. This turns hallucination detection into a teaching moment.
