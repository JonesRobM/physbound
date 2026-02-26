# PhysBound Formula Reference

Every formula PhysBound uses to validate physics claims. All constants are CODATA 2018 exact values sourced from SciPy.

---

## Physical Constants

| Symbol | Value | Unit | Source |
|--------|-------|------|--------|
| c | 299,792,458 | m/s | Speed of light (SI exact) |
| k_B | 1.380649 x 10^-23 | J/K | Boltzmann constant (SI exact) |
| h | 6.62607015 x 10^-34 | J*s | Planck constant (SI exact) |
| T_ref | 290 | K | IEEE standard reference temperature |
| N_0 | -174.0 | dBm/Hz | Thermal noise floor at T_ref |

---

## Free-Space Path Loss (FSPL)

```
FSPL(dB) = 20*log10(d) + 20*log10(f) + 20*log10(4*pi/c)
```

- **d**: distance in meters
- **f**: frequency in Hz
- **c**: speed of light in m/s

Equivalent compact form: `FSPL(dB) = 32.45 + 20*log10(f_MHz) + 20*log10(d_km)`

Applicability: free-space (line-of-sight, no multipath). PhysBound warns above 300 GHz where atmospheric absorption invalidates the model.

---

## Friis Transmission Equation

```
P_rx = P_tx + G_tx + G_rx - FSPL - L_tx - L_rx
```

All values in dB/dBm/dBi:

- **P_tx**: transmit power (dBm)
- **G_tx**, **G_rx**: antenna gains (dBi)
- **FSPL**: free-space path loss (dB)
- **L_tx**, **L_rx**: miscellaneous losses (dB), e.g., cable, connector, mismatch

---

## Antenna Aperture Gain Limit

```
G_max = eta * (pi * D / lambda)^2
```

- **eta**: aperture efficiency (default: 0.55 for parabolic dishes)
- **D**: antenna diameter in meters
- **lambda**: wavelength = c / f

Returns gain in linear scale; converted to dBi via `10*log10(G_max)`.

Any claimed gain exceeding G_max for a given antenna size and frequency is a physics violation.

---

## Shannon-Hartley Channel Capacity

```
C = B * log2(1 + SNR)
```

- **C**: maximum channel capacity in bits per second
- **B**: channel bandwidth in Hz
- **SNR**: signal-to-noise ratio (linear, not dB)

### Spectral Efficiency

```
eta = C / B = log2(1 + SNR)    [bps/Hz]
```

### SNR Conversion

```
SNR_linear = 10^(SNR_dB / 10)
SNR_dB = 10 * log10(SNR_linear)
```

Any throughput claim exceeding C for a given bandwidth and SNR is a physics violation. PhysBound flags the exact excess percentage.

---

## Thermal Noise Power

```
N = k_B * T * B
```

- **k_B**: Boltzmann constant
- **T**: system temperature in Kelvin
- **B**: bandwidth in Hz

In dBm: `N(dBm) = 10 * log10(k_B * T * B / 1e-3)`

At the IEEE reference (290K, 1 Hz): N = -174.0 dBm/Hz. This is the fundamental lower bound on receiver noise.

---

## Friis Noise Cascade

```
F_total = F_1 + (F_2 - 1)/G_1 + (F_3 - 1)/(G_1 * G_2) + ...
```

- **F_n**: noise factor of stage n (linear, = 10^(NF_dB/10))
- **G_n**: gain of stage n (linear)

All values are in linear scale internally; inputs and outputs use dB.

Key insight: the first stage dominates the system noise figure. A low-noise first stage (LNA) with high gain suppresses the noise contribution of subsequent stages.

### System Noise Temperature

```
T_sys = T_ref * (F_total - 1)
```

Where F_total is the cascaded noise factor (linear).

---

## Receiver Sensitivity

```
S_min = N_floor + NF + SNR_req
```

All in dB:

- **N_floor**: thermal noise floor in dBm (= `10*log10(k_B * T * B / 1e-3)`)
- **NF**: system noise figure in dB
- **SNR_req**: required SNR at the detector in dB

S_min is the minimum signal power (in dBm) the receiver can detect.

---

## Monostatic Radar Range Equation

### Maximum Detection Range

```
R_max = [P_t * G^2 * lambda^2 * sigma / ((4*pi)^3 * S_min * L)]^(1/4)
```

- **P_t**: peak transmit power in watts
- **G**: antenna gain (linear, monostatic: same antenna TX/RX)
- **lambda**: wavelength = c / f (meters)
- **sigma**: radar cross section (RCS) in m^2
- **S_min**: minimum detectable signal power in watts
- **L**: total system losses (linear)

### Signal-to-Noise Ratio (SNR Form)

```
SNR = P_t * G^2 * lambda^2 * sigma / ((4*pi)^3 * k_B * T_s * B_n * R^4 * L)
```

- **k_B**: Boltzmann constant
- **T_s**: system noise temperature in Kelvin
- **B_n**: noise bandwidth in Hz
- **R**: range in meters

### Minimum Detectable Signal

```
S_min = k_B * T_s * B_n * SNR_min / N_pulses
```

Where N_pulses provides coherent integration gain.

### Key Physical Insight: The Fourth-Root Law

Range scales as the **fourth root** of power, gain squared, RCS, and wavelength squared:

- Doubling P_t increases R_max by factor of 2^(1/4) = 1.189 (NOT 2x)
- Doubling antenna gain (linear) increases R_max by factor of 2^(1/2) = 1.414
- 10x larger RCS increases R_max by factor of 10^(1/4) = 1.778

Any claimed detection range exceeding R_max for the given parameters is a physics violation.

---

## Input Validation Guards

PhysBound enforces these constraints on all inputs before computation:

| Constraint | Physical Basis |
|-----------|----------------|
| Frequency > 0 Hz | Causality; EM wave must propagate |
| Distance > 0 m | Causality; non-degenerate link |
| Bandwidth > 0 Hz | Information-theoretic requirement |
| Temperature >= 0 K | Third Law of Thermodynamics |
| SNR > 0 (linear) | Signal must carry energy |
| Noise Figure >= 0 dB | Quantum noise limit |
| Antenna diameter > 0 m | Physical aperture must exist |
| Power > 0 W | Conservation of Energy |
| RCS > 0 m^2 | Physical target must scatter energy |
| Losses >= 0 dB | Passive system cannot create energy |
| Num pulses >= 1 | At least one pulse required |
