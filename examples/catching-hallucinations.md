# Catching LLM Hallucinations with PhysBound

This walkthrough shows PhysBound correcting five common LLM physics hallucinations in real time via the MCP protocol.

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
  "message": "TX antenna claimed gain 45.0 dBi exceeds the physical limit 12.1 dBi for a 0.3 m antenna at 1.000 GHz (Harrington bound (ka)^2 + 2ka with ka = 3.144; eta = 1 aperture value 9.9 dBi); it would require aperture efficiency eta = 3199.63 > 1 (typical eta = 0.55 gives 7.4 dBi)",
  "latex": "$G_{\\max} = (ka)^2 + 2ka = 3.144^2 + 2 \\times 3.144 = 12.1\\,\\text{dBi}$ with $ka = \\pi D / \\lambda = \\pi \\times 0.3 / 0.2998$ (Harrington); the $\\eta = 1$ aperture value $(\\pi D/\\lambda)^2 = 9.9\\,\\text{dBi}$ (since $A_e \\leq A_{\\text{phys}}$). Claimed $45.0\\,\\text{dBi}$ requires $\\eta = 3199.63 > 1$.",
  "computed_limit": 12.087,
  "claimed_value": 45.0,
  "unit": "dBi"
}
```

A 30 cm dish at 1 GHz has a wavelength of ~30 cm — the dish is only about one wavelength across. A perfectly illuminated planar aperture (efficiency eta = 1) gives **9.9 dBi**; the rigorous bound for *any* antenna that fits in a 30 cm sphere is Harrington's `(ka)^2 + 2ka` = **12.1 dBi**; a realistic 55%-efficient dish gives **7.4 dBi**. 45 dBi would need an aperture efficiency of 3200, i.e. an effective area 3200 times the physical dish.

PhysBound distinguishes the thresholds: a claim above the physical limit `max((pi D/lambda)^2, (ka)^2 + 2ka)` is a hard error, while a claim between the typical (eta = 0.55) value and the physical limit is accepted with a warning that it requires an unusually efficient (or non-planar, electrically small) antenna. The Harrington term matters for small antennas: a 2.15 dBi half-wave dipole in a 0.1 m footprint at 900 MHz has an eta = 1 aperture value of −0.5 dBi and would have been *falsely* rejected by the aperture formula alone; against the 4.4 dBi Harrington bound it is correctly accepted (`limiting_bound: "harrington"`).

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
  "thermal_noise_watts": 4.004e-14,
  "cascaded_noise_figure_db": 1.66,
  "system_noise_temp_k": 135.03,
  "receiver_sensitivity_dbm": -92.31,
  "human_readable": "Thermal Noise Floor:\n  Temperature: 290.0 K\n  Bandwidth:   10.000 MHz\n  Noise Power: -103.98 dBm (4.004e-14 W)\n  Cascaded NF: 1.66 dB\n  T_e = T_0(F-1): 135.03 K\n  Sensitivity: -92.31 dBm"
}
```

The Friis noise cascade shows that the LNA's low noise figure dominates — the 8 dB mixer NF is suppressed by the LNA's 20 dB gain to contribute only ~0.16 dB to the system NF. This is why **LNA-first order matters** in receiver design.

`system_noise_temp_k` is the receiver's effective input noise temperature `T_e = T_0 (F - 1) = 290 K x (1.466 - 1) = 135.0 K`. Noise figure is defined at `T_0 = 290 K`, so `T_e` is a property of the hardware and does not change if you point the antenna at a colder source: re-running with `temperature_k = 77` still reports `T_e = 135.0 K` (with a warning), and the sensitivity becomes `k_B (77 + 135) B x SNR` rather than the `N_floor(77 K) + NF` shortcut, which is only valid at 290 K.

---

## Scenario 5: Pulse-Doppler Radar Wants It All

> **User to LLM:** "My 10 GHz radar runs at 10 kHz PRF. Can it unambiguously measure a 500 m/s target?"
>
> **LLM (without PhysBound):** "Yes, 10 kHz PRF comfortably covers 500 m/s."

PhysBound's `radar_ambiguity` tool:

```json
{
  "frequency_hz": 10000000000,
  "prf_hz": 10000,
  "claimed_unambiguous_velocity_m_s": 500.0
}
```

**Response:**

```json
{
  "error": true,
  "violation_type": "PhysicalViolationError",
  "law_violated": "Radar Doppler Ambiguity",
  "message": "Claimed unambiguous velocity 500.00 m/s exceeds v_ua = lambda*PRF/4 = 74.95 m/s at 10.000 GHz, PRF 10000.0 Hz by 567.1%. The pulse train samples Doppler at PRF, so only |f_d| <= PRF/2 = 5000.0 Hz is unambiguous (first blind speed 149.90 m/s)",
  "latex": "$v_{ua} = \\frac{\\lambda\\,\\text{PRF}}{4} = \\frac{0.0300 \\times 10000.0}{4} = 74.95\\,\\text{m/s}$; claimed $500.00\\,\\text{m/s}$ exceeds this by $567.1\\%$",
  "computed_limit": 74.948,
  "claimed_value": 500.0,
  "unit": "m/s"
}
```

At X-band (lambda = 3 cm) a 10 kHz PRF gives an unambiguous velocity of only **+/-74.9 m/s** (first blind speed 149.9 m/s) and an unambiguous range of **15.0 km**. A 500 m/s target aliases: its 33.3 kHz Doppler folds into the +/-5 kHz Nyquist band. Raising the PRF to cover 500 m/s would shrink the unambiguous range to ~2.2 km — the **range-Doppler dilemma**: `R_ua * v_ua = c * lambda / 8 = 1.12e6 m^2/s` for any PRF at 10 GHz, so no single PRF can give both 150 km and +/-300 m/s (that would need 4.5e7 m^2/s, 40x too large).

---

## Key Takeaway

PhysBound doesn't just catch wrong numbers — it explains *why* they're wrong, citing the specific physical law violated and providing the LaTeX formula. This turns hallucination detection into a teaching moment.
