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
- **L_tx**, **L_rx**: miscellaneous losses (dB), e.g., cable, connector, mismatch. Must be >= 0 dB: a negative loss would be a passive component creating energy (same rule as the radar `L`).

---

## Antenna Gain Limit (aperture and Harrington bounds)

```
G     = eta * (pi * D / lambda)^2          (circular aperture of diameter D)
D_max = (ka)^2 + 2ka,  k = 2*pi/lambda,  a = D/2    (Harrington bound)
```

Derivation: the gain of any aperture antenna is `G = 4*pi*A_e / lambda^2`
(Balanis, *Antenna Theory*, Sec. 2.16; Pozar, *Microwave Engineering*, Ch. 14),
where the effective aperture `A_e = eta * A_phys` and `A_phys = pi * D^2 / 4`
for a circular aperture. Substituting gives `G = eta * (pi*D/lambda)^2`.

- **eta**: aperture efficiency, `0 < eta <= 1` (illumination taper, spillover, blockage, surface error)
- **D**: antenna diameter in meters
- **lambda**: wavelength = c / f

Because `A_e` cannot exceed the physical area, `eta <= 1` and `G_ap = (pi*D/lambda)^2` is the
largest gain a *planar* aperture of diameter `D` can have. It is **not** a rigorous bound on an
arbitrary antenna that fits in a `D`-metre footprint: a half-wave dipole (2.15 dBi) in a 0.1 m
footprint at 900 MHz exceeds `G_ap = -0.5 dBi`. The rigorous bound on the directivity of any
antenna enclosed in a sphere of radius `a = D/2` is Harrington's `D_max = (ka)^2 + 2ka`
(Harrington, "Effect of antenna size on gain, bandwidth, and efficiency", *J. Res. NBS* 64D,
1960; Balanis, *Antenna Theory*, small-antenna limits). Since `ka = pi*D/lambda`, this is the
aperture value `(ka)^2` plus the `2ka` term, so PhysBound's hard limit is

```
G_phys = max(G_ap, D_max) = D_max          (for every D, because 2ka > 0)
```

The two coincide to within `10*log10(1 + 2*lambda/(pi*D))` dB: 0.08 dB for a 1 m dish at
10 GHz, 0.03 dB for a 30 m dish at 1 GHz (large dishes are effectively unchanged), but
>= 2.1 dB whenever `D < lambda`, where the aperture formula would falsely reject real
electrically small antennas.

PhysBound uses three values:

| Value | Formula | Behaviour |
|-------|---------|-----------|
| Physical limit | `G_phys = max((pi*D/lambda)^2, (ka)^2 + 2ka)` | Claimed gain above this is a **PhysicalViolationError** |
| Aperture value (`eta = 1`) | `G_ap = (pi * D / lambda)^2` | Claimed gain between `G_ap` and `G_phys` is accepted with a **warning** (implied `eta > 1`: only a non-planar / electrically small radiator can do it) |
| Typical value (`eta = 0.55`, parabolic dish; Skolnik, *Radar Handbook*, Ch. 9) | `G_typ = 0.55 * (pi * D / lambda)^2` | Claimed gain between `G_typ` and `G_ap` is accepted with a **warning** (it implies `eta > 0.55`, unusually efficient) |

The gap between `G_ap` and `G_typ` is a constant `-10*log10(0.55) = 2.6 dB`. The
`aperture_efficiency` parameter moves the warning threshold only; the hard limit is always
`max(G_ap, D_max)`.

All values are returned: `tx_physical_limit_dbi` / `rx_physical_limit_dbi` (hard limit),
`tx_aperture_limit_dbi` / `rx_aperture_limit_dbi` (`eta = 1`), `tx_typical_aperture_gain_dbi` /
`rx_typical_aperture_gain_dbi` (typical efficiency) and `tx_limiting_bound` / `rx_limiting_bound`
(`"harrington"` when `D < lambda`, electrically small; `"aperture"` when `D >= lambda`), together
with the implied planar-aperture efficiency `eta_claim = G_claim / G_ap` in the messages.

Worked examples:
- README row 3: 0.3 m dish at 1 GHz, `lambda = 0.2998 m`, `ka = pi*D/lambda = 3.144`, so
  `G_ap = 9.88 -> 9.95 dBi`, `D_max = 9.88 + 6.29 = 16.17 -> 12.09 dBi` and
  `G_typ = 5.44 -> 7.35 dBi`. A 45 dBi claim would need `eta = 3200`.
- README row 10: 0.1 m at 900 MHz, `lambda = 0.333 m`, `ka = 0.943`: `G_ap = -0.51 dBi`,
  `D_max = 0.889 + 1.886 = 2.775 -> 4.43 dBi`, `G_typ = -3.10 dBi`. A 20 dBi claim is rejected,
  but a 2.15 dBi half-wave dipole in the same footprint is **valid** (warned: implied `eta = 1.84`,
  non-planar radiator).

Caveats reported as warnings:
- The Friis equation assumes far-field propagation, `d > 2*D^2/lambda` (Fraunhofer distance). Links closer than this are flagged.
- Above 300 GHz the free-space model ignores atmospheric absorption.

---

## Antenna Gain Tool (`antenna_gain`)

Standalone version of the aperture check above, for a single antenna given either
its circular diameter `D` or its physical area `A_phys`.

```
lambda   = c / f
D        = sqrt(4 * A_phys / pi)                 (equivalent circular diameter, if area given)
A_phys   = pi * D^2 / 4
A_e      = eta * A_phys                          (effective aperture)
D_0      = 4*pi*A_phys / lambda^2 = (pi*D/lambda)^2   (planar-aperture directivity, eta = 1)
D_max    = (ka)^2 + 2ka,  k = 2*pi/lambda,  a = D/2    (Harrington bound; = D_0 + 2ka)
G_phys   = max(D_0, D_max) = D_max                (hard physical gain limit)
G        = eta * D_0 = 4*pi*A_e / lambda^2       (gain at aperture efficiency eta)
HPBW     ~ 70   * lambda / D  degrees            (tapered parabolic reflector, rule of thumb)
HPBW     ~ 58.4 * lambda / D  degrees            (uniformly illuminated circular aperture)
R_ff     = 2 * D^2 / lambda                      (far-field / Fraunhofer distance)
eta_claim = G_claim / D_0                        (efficiency implied by a gain claim)
```

Sources:
- `G = 4*pi*A_e/lambda^2` and `G = e_ap * D_0`: Balanis, *Antenna Theory*, Sec. 2.16 (aperture
  efficiency and directivity of aperture antennas); Pozar, *Microwave Engineering*, Ch. 14.
- HPBW of a uniformly illuminated circular aperture `29.2 deg * lambda/a`, `a = D/2`, i.e.
  `58.4 deg * lambda/D`: Balanis, Sec. 12.5, Table 12.2. Reflectors with typical edge taper
  broaden this to about `70 deg * lambda/D` (Balanis, Sec. 15.4; Stutzman & Thiele, *Antenna
  Theory and Design*, Sec. 9.4). Both values are returned and flagged as approximations.
- Far-field region begins at `R = 2 D^2 / lambda`: Balanis, Sec. 2.2.4.
- Typical parabolic-dish aperture efficiency `eta = 0.55`: Skolnik, *Radar Handbook*, Ch. 9.
- Harrington bound `D_max = (ka)^2 + 2ka` for an antenna enclosed in a sphere of radius
  `a = D/2`: Harrington, *J. Res. NBS* 64D (1960); Balanis. Governs for `D < lambda`.

Outputs: `wavelength_m`, `diameter_m`, `physical_aperture_m2`, `effective_aperture_m2`,
`physical_limit_dbi` (`max(D_0, D_max)`), `aperture_limit_dbi` (D_0, eta = 1),
`harrington_limit_dbi` (D_max), `limiting_bound` (`"harrington"` for `D < lambda`,
`"aperture"` for `D >= lambda`), `typical_gain_dbi` (eta = `aperture_efficiency`),
`directivity_linear` (D_0), `half_power_beamwidth_deg` (70 lambda/D),
`half_power_beamwidth_uniform_deg` (58.4 lambda/D), `far_field_distance_m`, and when
`claimed_gain_dbi` is supplied `implied_efficiency` and `claim_is_valid`.

Validation uses the same thresholds as the link budget tool: a claim above
`physical_limit_dbi` raises **PhysicalViolationError** (law: "Antenna Aperture Limit");
a claim between `typical_gain_dbi` and `physical_limit_dbi` is a **warning** (with a note
that only a non-planar / electrically small radiator can exceed `aperture_limit_dbi`).

Worked example: 1 m dish at 10 GHz, `lambda = 0.029979 m`, `ka = pi*D/lambda = 104.8`,
`D_0 = 10983 -> 40.41 dBi`, `D_max = 10983 + 209.6 = 11193 -> 40.49 dBi`, `G(eta=0.55) = 37.81 dBi`,
`A_e = 0.432 m^2`, `HPBW ~ 2.10 deg` (uniform: 1.75 deg), `R_ff = 66.7 m`. A 45 dBi claim would
need `eta = 2.9`. Small-antenna example: a 2.15 dBi half-wave dipole in a 0.1 m footprint at
900 MHz (`ka = 0.943`, `D_0 = -0.51 dBi`, `D_max = 4.43 dBi`) is valid with `limiting_bound =
"harrington"`; the planar-aperture formula alone would have rejected it.

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

### Effective Input Noise Temperature

```
T_e = T_0 * (F_total - 1),    T_0 = 290 K
```

Where F_total is the cascaded noise factor (linear). Noise figure is *defined*
(IEEE Std; Pozar, *Microwave Engineering*, Sec. 10.1) as the SNR degradation
when the source is at the reference temperature `T_0 = 290 K`:

```
F = (S_i/N_i) / (S_o/N_o) = (T_0 + T_e) / T_0    =>    T_e = T_0 (F - 1)
```

`T_e` characterises the receiver hardware and therefore does **not** depend on
the `temperature_k` (antenna/source temperature) supplied to the `noise_floor`
tool. Example: NF = 1.66 dB gives `T_e = 290 * (1.466 - 1) = 135.0 K` whether the
antenna looks at a 290 K or a 77 K source. (Earlier versions computed
`temperature_k * (F - 1)`, which understated `T_e` by `T_0 / T_A` for cold
sources; this was wrong and has been fixed.)

---

## Receiver Sensitivity

```
S_min = k_B * (T_A + T_e) * B * SNR_req,      T_e = T_0 * (F - 1)
```

The total input-referred noise is the source (antenna) noise `k_B * T_A * B`
plus the receiver's own noise `k_B * T_e * B`. In dB:

```
S_min(dBm) = 10*log10(k_B * (T_A + T_e) * B / 1e-3) + SNR_req
```

- **T_A**: source/antenna noise temperature (`temperature_k`, default 290 K)
- **T_e**: receiver effective input noise temperature, referenced to `T_0 = 290 K`
- **NF**: system noise figure in dB, `F = 10^(NF/10)`
- **SNR_req**: required SNR at the detector in dB

When `T_A = T_0 = 290 K`, `k_B (T_0 + T_0(F-1)) B = k_B T_0 B F` and this reduces to
the familiar `S_min = N_floor + NF + SNR_req`. For other source temperatures the
familiar form is incorrect because NF is defined at 290 K: with `T_A = 77 K` and
`NF = 3 dB`, `T_e = 288.6 K` and the true noise is `k_B * 365.6 K * B`, 3.8 dB
higher than `N_floor(77 K) + 3 dB` would suggest.

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
| Radar T_s > 0 K | S_min = k T_s B -> 0 gives unbounded range |
| Aperture efficiency 0 < eta <= 1 | Effective area cannot exceed physical area |
| SNR > 0 (linear) | Signal must carry energy |
| Noise Figure >= 0 dB | Quantum noise limit |
| Antenna diameter > 0 m | Physical aperture must exist |
| Power > 0 W | Conservation of Energy |
| RCS > 0 m^2 | Physical target must scatter energy |
| Losses >= 0 dB (radar L, link L_tx, L_rx) | Passive system cannot create energy |
| Num pulses >= 1 | At least one pulse required |
| PRF > 0 Hz | Pulsed radar must emit pulses |
| Pulse width tau > 0 s | A pulse must carry finite energy |
| Duty cycle tau * PRF < 1 | Receiver must be un-blanked for part of every PRI (else CW, not pulsed) |

---

## Pulse-Doppler Radar Ambiguity (`radar_ambiguity`)

Sources: Skolnik, *Introduction to Radar Systems*, 3rd ed., Ch. 2 (range ambiguity,
duty cycle) and Ch. 3 (MTI, blind speeds, Doppler); Richards, *Fundamentals of Radar
Signal Processing*, 2nd ed., Ch. 1 (Doppler shift, range resolution), Ch. 3 (Doppler
sampling and aliasing) and Ch. 5 (Doppler processing, range-Doppler dilemma).

```
lambda      = c / f
PRI         = 1 / PRF
R_ua        = c / (2 * PRF)             maximum unambiguous range
v_blind     = lambda * PRF / 2          first blind speed (f_d = PRF)
v_ua        = lambda * PRF / 4          unambiguous radial velocity (|f_d| <= PRF/2)
f_d         = 2 * v_r / lambda          Doppler shift, closing velocity positive
R_ua * v_ua = c * lambda / 8            range-Doppler dilemma invariant
dR          = c * tau / 2               range resolution, unmodulated pulse of width tau
dR          = c / (2 * B)               range resolution with pulse compression, bandwidth B
R_min       = c * tau / 2               eclipsing: receiver blanked while transmitting
duty        = tau * PRF
```

- **R_ua**: an echo from beyond `R_ua` arrives after the next pulse is transmitted and
  is folded to the apparent range `R mod R_ua` (second-time-around echo).
- **v_ua / v_blind**: the pulse train samples the Doppler phase at the PRF, so by the
  sampling theorem only `|f_d| <= PRF/2` is unambiguous; `f_d = n * PRF` is
  indistinguishable from stationary clutter (MTI blind speeds). A target with
  `|f_d| > PRF/2` is reported as **aliased**, with the apparent velocity obtained by
  folding `f_d` into `(-PRF/2, PRF/2]`.
- **Range-Doppler dilemma**: because `R_ua ~ 1/PRF` and `v_ua ~ PRF`, their product is
  fixed at `c * lambda / 8` for a given carrier. Raising the PRF buys velocity coverage
  at the expense of range and vice versa; only a change of wavelength (or multiple-PRF
  staggering / Chinese-remainder unfolding, outside the scope of this tool) can move the
  product.
- **Range resolution**: for a simple pulse the effective bandwidth is `B ~ 1/tau`, so
  `dR = c*tau/2`. Pulse compression (chirp, phase codes) decouples resolution from pulse
  width: pass `bandwidth_hz` and the tool uses `c/(2B)` instead, warning if `B*tau < 1`.

Outputs: `wavelength_m`, `pulse_repetition_interval_s`, `max_unambiguous_range_m` / `_km`,
`first_blind_speed_m_s`, `max_unambiguous_velocity_m_s`, `max_unambiguous_doppler_hz`
(`PRF/2`), `range_velocity_product_m2_s` (`c*lambda/8`), and when the corresponding inputs
are supplied `doppler_shift_hz`, `doppler_aliased`, `apparent_velocity_m_s`,
`range_resolution_m`, `minimum_range_m`, `duty_cycle`.

Violations (**PhysicalViolationError**):

| Claim | Law violated | Limit |
|-------|--------------|-------|
| `claimed_unambiguous_range_m > c/(2 PRF)` | Radar Range Ambiguity | `R_ua` |
| `claimed_unambiguous_velocity_m_s > lambda PRF/4` | Radar Doppler Ambiguity | `v_ua` |
| `R_claim * v_claim > c lambda/8` (both given) | Range-Doppler Dilemma | `c lambda/8` |
| `claimed_range_resolution_m < c tau/2` (or `c/(2B)`) | Radar Range Resolution | `dR` |
| `PRF <= 0`, `tau <= 0`, `tau * PRF >= 1` | Pulsed Radar Timing | - |

Warnings: target Doppler aliased (`|f_d| > PRF/2`), target at or beyond the first blind
speed, duty cycle > 0.5, `B*tau < 1`, a single range or velocity claim that leaves the
other quantity tightly constrained by the dilemma, and `f > 300 GHz`.

Worked example (README rows 15-16): X-band 10 GHz, `lambda = 2.998 cm`.
`PRF = 1 kHz`: `R_ua = 149.9 km`, `v_ua = +/-7.49 m/s`, blind speed `14.99 m/s`.
`PRF = 10 kHz`: `R_ua = 15.0 km`, `v_ua = +/-74.9 m/s`; a claimed 500 m/s unambiguous
velocity is 6.7x the limit. `PRF = 100 kHz`: `R_ua = 1.5 km`. In every case
`R_ua * v_ua = 1.123e6 m^2/s`, so 150 km with +/-300 m/s (`4.5e7 m^2/s`) is impossible at any PRF.
A 1 us unmodulated pulse gives `dR = R_min = 149.9 m`; a 10 m resolution requires
`B >= 15 MHz` of pulse compression.
