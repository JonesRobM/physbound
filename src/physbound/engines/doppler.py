"""Pulse-Doppler radar ambiguity, blind-speed and resolution limits.

Formulas (Skolnik, *Introduction to Radar Systems*, 3rd ed., Ch. 2-3;
Richards, *Fundamentals of Radar Signal Processing*, 2nd ed., Ch. 1, 3, 5):

    lambda        = c / f
    PRI           = 1 / PRF
    R_ua          = c / (2 * PRF)                 maximum unambiguous range
    v_blind       = lambda * PRF / 2               first blind speed (f_d = PRF)
    v_ua          = lambda * PRF / 4               unambiguous velocity (f_d = +/- PRF/2)
    f_d           = 2 * v_r / lambda               Doppler shift, closing v_r > 0
    R_ua * v_ua   = c * lambda / 8                 range-Doppler dilemma invariant
    dR            = c * tau / 2                    range resolution, unmodulated pulse
    dR            = c / (2 * B)                    range resolution, pulse compression
    R_min         = c * tau / 2                    eclipsing (receiver blanked during TX)
    duty cycle    = tau * PRF
"""

import math

from physbound.engines.constants import SPEED_OF_LIGHT
from physbound.errors import PhysicalViolationError
from physbound.validators import (
    validate_positive_bandwidth,
    validate_positive_frequency,
    validate_positive_prf,
    validate_positive_pulse_width,
)

_LAW_RANGE = "Radar Range Ambiguity"
_LAW_DOPPLER = "Radar Doppler Ambiguity"
_LAW_RESOLUTION = "Radar Range Resolution"
_LAW_DILEMMA = "Range-Doppler Dilemma"


def max_unambiguous_range_m(prf_hz: float) -> float:
    """R_ua = c / (2 PRF): a return from beyond R_ua arrives after the next pulse."""
    validate_positive_prf(prf_hz)
    return SPEED_OF_LIGHT.magnitude / (2.0 * prf_hz)


def first_blind_speed_m_s(frequency_hz: float, prf_hz: float) -> float:
    """v_blind = lambda PRF / 2: Doppler equal to PRF is indistinguishable from clutter."""
    validate_positive_frequency(frequency_hz)
    validate_positive_prf(prf_hz)
    wavelength_m = SPEED_OF_LIGHT.magnitude / frequency_hz
    return wavelength_m * prf_hz / 2.0


def max_unambiguous_velocity_m_s(frequency_hz: float, prf_hz: float) -> float:
    """v_ua = lambda PRF / 4: |f_d| <= PRF/2 (Nyquist for pulse-to-pulse sampling)."""
    return first_blind_speed_m_s(frequency_hz, prf_hz) / 2.0


def doppler_shift_hz(frequency_hz: float, radial_velocity_m_s: float) -> float:
    """f_d = 2 v_r / lambda for a monostatic radar; closing velocity is positive."""
    validate_positive_frequency(frequency_hz)
    wavelength_m = SPEED_OF_LIGHT.magnitude / frequency_hz
    return 2.0 * radial_velocity_m_s / wavelength_m


def range_resolution_m(
    pulse_width_s: float | None = None, bandwidth_hz: float | None = None
) -> float:
    """Range resolution dR = c / (2 B); for an unmodulated pulse B = 1/tau so dR = c tau / 2."""
    c = SPEED_OF_LIGHT.magnitude
    if bandwidth_hz is not None:
        validate_positive_bandwidth(bandwidth_hz)
        return c / (2.0 * bandwidth_hz)
    if pulse_width_s is not None:
        validate_positive_pulse_width(pulse_width_s)
        return c * pulse_width_s / 2.0
    raise ValueError("range_resolution_m requires pulse_width_s or bandwidth_hz")


def compute_radar_ambiguity(
    frequency_hz: float,
    prf_hz: float,
    pulse_width_s: float | None = None,
    target_velocity_m_s: float | None = None,
    bandwidth_hz: float | None = None,
    claimed_unambiguous_range_m: float | None = None,
    claimed_unambiguous_velocity_m_s: float | None = None,
    claimed_range_resolution_m: float | None = None,
) -> dict:
    """Compute pulse-Doppler ambiguity limits and validate claims against them.

    Args:
        frequency_hz: Carrier frequency in Hz.
        prf_hz: Pulse repetition frequency in Hz.
        pulse_width_s: Optional transmitted pulse width tau in seconds.
        target_velocity_m_s: Optional radial velocity (closing positive) in m/s.
        bandwidth_hz: Optional transmitted (compressed) bandwidth in Hz. When given,
            the range-resolution limit is c/(2B) instead of c*tau/2.
        claimed_unambiguous_range_m: Optional claimed unambiguous range to validate.
        claimed_unambiguous_velocity_m_s: Optional claimed unambiguous (radial)
            velocity magnitude to validate.
        claimed_range_resolution_m: Optional claimed range resolution to validate.

    Returns:
        Dict with wavelength_m, pulse_repetition_interval_s, max_unambiguous_range_m/km,
        first_blind_speed_m_s, max_unambiguous_velocity_m_s, max_unambiguous_doppler_hz,
        range_velocity_product_m2_s, doppler_shift_hz, doppler_aliased,
        apparent_velocity_m_s, range_resolution_m, minimum_range_m, duty_cycle,
        human_readable, latex, warnings.

    Raises:
        PhysicalViolationError: On non-physical inputs (PRF <= 0, tau <= 0,
            tau*PRF >= 1, B <= 0) or when a claim exceeds the corresponding limit.
    """
    validate_positive_frequency(frequency_hz)
    validate_positive_prf(prf_hz)
    if pulse_width_s is not None:
        validate_positive_pulse_width(pulse_width_s)
    if bandwidth_hz is not None:
        validate_positive_bandwidth(bandwidth_hz)

    c = SPEED_OF_LIGHT.magnitude
    wavelength_m = c / frequency_hz
    pri_s = 1.0 / prf_hz
    r_ua = c / (2.0 * prf_hz)
    v_blind = wavelength_m * prf_hz / 2.0
    v_ua = v_blind / 2.0
    f_d_ua = prf_hz / 2.0
    rv_product = r_ua * v_ua  # = c * lambda / 8, independent of PRF

    warnings: list[str] = []

    # --- Pulse-width dependent quantities -----------------------------------------
    duty_cycle: float | None = None
    min_range_m: float | None = None
    range_res_m: float | None = None
    if pulse_width_s is not None:
        duty_cycle = pulse_width_s * prf_hz
        if duty_cycle >= 1.0:
            raise PhysicalViolationError(
                message=(
                    f"Duty cycle tau*PRF = {pulse_width_s:.3e} s x {prf_hz:.3e} Hz = "
                    f"{duty_cycle:.3f} >= 1: the pulse is at least as long as the pulse "
                    "repetition interval, so the radar never stops transmitting and cannot "
                    "receive (this is CW, not pulsed, operation)"
                ),
                law_violated="Pulsed Radar Timing",
                latex_explanation=(
                    r"$\tau \cdot \text{PRF} < 1$ required for a pulsed radar; "
                    rf"$\tau \cdot \text{{PRF}} = {duty_cycle:.3f}$"
                ),
                computed_limit=1.0,
                claimed_value=duty_cycle,
            )
        min_range_m = c * pulse_width_s / 2.0
        range_res_m = c * pulse_width_s / 2.0
        if duty_cycle > 0.5:
            warnings.append(
                f"Duty cycle {duty_cycle:.2f} > 0.5: eclipsing blanks more than half of every "
                f"PRI; minimum range {min_range_m:.1f} m approaches R_ua = {r_ua:.1f} m."
            )

    resolution_law_note = "unmodulated pulse (dR = c*tau/2)"
    if bandwidth_hz is not None:
        range_res_m = c / (2.0 * bandwidth_hz)
        resolution_law_note = "pulse compression (dR = c/(2B))"
        if pulse_width_s is not None:
            time_bw_product = bandwidth_hz * pulse_width_s
            if time_bw_product < 1.0:
                warnings.append(
                    f"Time-bandwidth product B*tau = {time_bw_product:.3f} < 1: an unmodulated "
                    f"pulse of width {pulse_width_s:.3e} s already occupies ~1/tau = "
                    f"{1.0 / pulse_width_s:.3e} Hz; the supplied bandwidth is narrower than "
                    "the pulse itself. Using c/(2B) as requested."
                )
            else:
                warnings.append(
                    f"Pulse compression assumed: B*tau = {time_bw_product:.1f}, resolution "
                    f"{range_res_m:.2f} m vs {c * pulse_width_s / 2.0:.2f} m for an "
                    "unmodulated pulse of the same width."
                )

    # --- Target Doppler ----------------------------------------------------------
    f_d: float | None = None
    aliased: bool | None = None
    apparent_v: float | None = None
    if target_velocity_m_s is not None:
        f_d = 2.0 * target_velocity_m_s / wavelength_m
        aliased = abs(f_d) > f_d_ua
        # Fold f_d into (-PRF/2, PRF/2]; apparent velocity is what the radar would measure
        f_alias = f_d - prf_hz * math.floor(f_d / prf_hz + 0.5)
        apparent_v = f_alias * wavelength_m / 2.0
        if aliased:
            warnings.append(
                f"Target Doppler {f_d:.1f} Hz exceeds +/-PRF/2 = +/-{f_d_ua:.1f} Hz: velocity "
                f"{target_velocity_m_s:.2f} m/s is aliased and would be measured as "
                f"{apparent_v:.2f} m/s (Richards, FRSP Ch. 3)."
            )
        if abs(target_velocity_m_s) >= v_blind:
            n_blind = abs(target_velocity_m_s) / v_blind
            warnings.append(
                f"|v| = {abs(target_velocity_m_s):.2f} m/s >= first blind speed "
                f"{v_blind:.2f} m/s ({n_blind:.2f}x). Near integer multiples of the blind "
                "speed the target falls in the MTI clutter notch (Skolnik Ch. 3)."
            )

    # --- Claim validation ---------------------------------------------------------
    if (
        claimed_unambiguous_range_m is not None
        and claimed_unambiguous_velocity_m_s is not None
        and claimed_unambiguous_range_m * abs(claimed_unambiguous_velocity_m_s) > rv_product
    ):
        claimed_product = claimed_unambiguous_range_m * abs(claimed_unambiguous_velocity_m_s)
        raise PhysicalViolationError(
            message=(
                f"Claimed unambiguous range {claimed_unambiguous_range_m:.1f} m and velocity "
                f"{abs(claimed_unambiguous_velocity_m_s):.2f} m/s have product "
                f"{claimed_product:.3e} m^2/s, exceeding the range-Doppler dilemma invariant "
                f"R_ua * v_ua = c*lambda/8 = {rv_product:.3e} m^2/s at {frequency_hz / 1e9:.3f} "
                "GHz. No single PRF can satisfy both; raising PRF buys velocity coverage at "
                "the expense of range and vice versa"
            ),
            law_violated=_LAW_DILEMMA,
            latex_explanation=(
                r"$R_{ua}\,v_{ua} = \frac{c}{2\,\text{PRF}} \cdot \frac{\lambda\,\text{PRF}}{4} "
                rf"= \frac{{c\lambda}}{{8}} = {rv_product:.3e}\,\text{{m}}^2/\text{{s}}$; "
                rf"claimed ${claimed_product:.3e}\,\text{{m}}^2/\text{{s}}$"
            ),
            computed_limit=rv_product,
            claimed_value=claimed_product,
            unit="m^2/s",
        )

    if claimed_unambiguous_range_m is not None and claimed_unambiguous_range_m > r_ua:
        excess_pct = (claimed_unambiguous_range_m - r_ua) / r_ua * 100.0
        raise PhysicalViolationError(
            message=(
                f"Claimed unambiguous range {claimed_unambiguous_range_m:.1f} m "
                f"({claimed_unambiguous_range_m / 1000:.2f} km) exceeds R_ua = c/(2 PRF) = "
                f"{r_ua:.1f} m ({r_ua / 1000:.2f} km) at PRF {prf_hz:.1f} Hz by "
                f"{excess_pct:.1f}%. Echoes from beyond R_ua arrive after the next pulse "
                "is transmitted and are folded into a shorter apparent range"
            ),
            law_violated=_LAW_RANGE,
            latex_explanation=(
                rf"$R_{{ua}} = \frac{{c}}{{2\,\text{{PRF}}}} = \frac{{{c:.0f}}}{{2 \times "
                rf"{prf_hz:.1f}}} = {r_ua:.1f}\,\text{{m}}$; claimed "
                rf"${claimed_unambiguous_range_m:.1f}\,\text{{m}}$ exceeds this by "
                rf"${excess_pct:.1f}\%$"
            ),
            computed_limit=r_ua,
            claimed_value=claimed_unambiguous_range_m,
            unit="m",
        )

    if (
        claimed_unambiguous_velocity_m_s is not None
        and abs(claimed_unambiguous_velocity_m_s) > v_ua
    ):
        v_claim = abs(claimed_unambiguous_velocity_m_s)
        excess_pct = (v_claim - v_ua) / v_ua * 100.0
        raise PhysicalViolationError(
            message=(
                f"Claimed unambiguous velocity {v_claim:.2f} m/s exceeds v_ua = lambda*PRF/4 = "
                f"{v_ua:.2f} m/s at {frequency_hz / 1e9:.3f} GHz, PRF {prf_hz:.1f} Hz by "
                f"{excess_pct:.1f}%. The pulse train samples Doppler at PRF, so only "
                f"|f_d| <= PRF/2 = {f_d_ua:.1f} Hz is unambiguous (first blind speed "
                f"{v_blind:.2f} m/s)"
            ),
            law_violated=_LAW_DOPPLER,
            latex_explanation=(
                rf"$v_{{ua}} = \frac{{\lambda\,\text{{PRF}}}}{{4}} = \frac{{{wavelength_m:.4f} "
                rf"\times {prf_hz:.1f}}}{{4}} = {v_ua:.2f}\,\text{{m/s}}$; claimed "
                rf"${v_claim:.2f}\,\text{{m/s}}$ exceeds this by ${excess_pct:.1f}\%$"
            ),
            computed_limit=v_ua,
            claimed_value=v_claim,
            unit="m/s",
        )

    if claimed_range_resolution_m is not None:
        if claimed_range_resolution_m <= 0:
            raise PhysicalViolationError(
                message=f"Range resolution must be positive, got {claimed_range_resolution_m} m",
                law_violated=_LAW_RESOLUTION,
                latex_explanation=r"$\Delta R > 0$ required",
                claimed_value=claimed_range_resolution_m,
                unit="m",
            )
        if range_res_m is None:
            warnings.append(
                f"Claimed range resolution {claimed_range_resolution_m:.2f} m could not be "
                "checked: supply pulse_width_s (unmodulated pulse) or bandwidth_hz "
                "(pulse compression)."
            )
        elif claimed_range_resolution_m < range_res_m:
            if bandwidth_hz is not None:
                latex = (
                    rf"$\Delta R = \frac{{c}}{{2B}} = \frac{{{c:.0f}}}{{2 \times "
                    rf"{bandwidth_hz:.3e}}} = {range_res_m:.3f}\,\text{{m}}$"
                )
                hint = f"the {bandwidth_hz:.3e} Hz bandwidth supplied"
            else:
                assert pulse_width_s is not None
                latex = (
                    rf"$\Delta R = \frac{{c\tau}}{{2}} = \frac{{{c:.0f} \times "
                    rf"{pulse_width_s:.3e}}}{{2}} = {range_res_m:.3f}\,\text{{m}}$"
                )
                hint = (
                    f"an unmodulated {pulse_width_s:.3e} s pulse; pulse compression with "
                    f"bandwidth B > {1.0 / pulse_width_s:.3e} Hz would be needed "
                    "(pass bandwidth_hz)"
                )
            raise PhysicalViolationError(
                message=(
                    f"Claimed range resolution {claimed_range_resolution_m:.3f} m is finer "
                    f"than the c/(2B) limit of {range_res_m:.3f} m for {hint}"
                ),
                law_violated=_LAW_RESOLUTION,
                latex_explanation=(
                    f"{latex}; claimed ${claimed_range_resolution_m:.3f}" r"\,\text{m}$"
                ),
                computed_limit=range_res_m,
                claimed_value=claimed_range_resolution_m,
                unit="m",
            )

    # --- Range-Doppler dilemma advisories ----------------------------------------
    if claimed_unambiguous_range_m is not None and claimed_unambiguous_velocity_m_s is None:
        warnings.append(
            f"Range-Doppler dilemma: R_ua * v_ua = c*lambda/8 = {rv_product:.3e} m^2/s. With "
            f"R_ua = {r_ua:.1f} m the unambiguous velocity at this PRF is only "
            f"+/-{v_ua:.2f} m/s."
        )
    if claimed_unambiguous_velocity_m_s is not None and claimed_unambiguous_range_m is None:
        warnings.append(
            f"Range-Doppler dilemma: R_ua * v_ua = c*lambda/8 = {rv_product:.3e} m^2/s. With "
            f"v_ua = +/-{v_ua:.2f} m/s the unambiguous range at this PRF is only "
            f"{r_ua:.1f} m."
        )
    if frequency_hz > 3e11:
        warnings.append(
            "Frequency > 300 GHz: atmospheric absorption limits practical range well below R_ua."
        )

    # --- Human-readable / LaTeX ---------------------------------------------------
    lines = [
        "Pulse-Doppler Radar Ambiguity:",
        f"  Frequency:        {frequency_hz / 1e9:.3f} GHz (lambda = {wavelength_m:.4f} m)",
        f"  PRF:              {prf_hz:.1f} Hz (PRI = {pri_s * 1e6:.2f} us)",
        f"  R_ua = c/(2 PRF): {r_ua:.1f} m ({r_ua / 1000:.2f} km)",
        f"  v_ua = lam*PRF/4: +/-{v_ua:.2f} m/s (|f_d| <= {f_d_ua:.1f} Hz)",
        f"  First blind speed:{v_blind:.2f} m/s",
        f"  R_ua * v_ua:      {rv_product:.3e} m^2/s (= c*lambda/8, PRF-independent)",
    ]
    if pulse_width_s is not None:
        assert duty_cycle is not None and min_range_m is not None
        lines.append(f"  Pulse width:      {pulse_width_s * 1e6:.3f} us (duty {duty_cycle:.3f})")
        lines.append(f"  Min range (ecl.): {min_range_m:.2f} m")
    if range_res_m is not None:
        lines.append(f"  Range resolution: {range_res_m:.3f} m [{resolution_law_note}]")
    if f_d is not None:
        assert target_velocity_m_s is not None and apparent_v is not None
        status = f"ALIASED, apparent {apparent_v:.2f} m/s" if aliased else "unambiguous"
        lines.append(
            f"  Target v_r:       {target_velocity_m_s:.2f} m/s -> f_d = {f_d:.1f} Hz ({status})"
        )
    human_readable = "\n".join(lines)

    latex = (
        rf"$R_{{ua}} = \frac{{c}}{{2\,\text{{PRF}}}} = {r_ua:.1f}\,\text{{m}},\quad "
        rf"v_{{ua}} = \frac{{\lambda\,\text{{PRF}}}}{{4}} = {v_ua:.2f}\,\text{{m/s}},\quad "
        rf"R_{{ua}} v_{{ua}} = \frac{{c\lambda}}{{8}} = {rv_product:.3e}\,\text{{m}}^2/\text{{s}}$"
    )
    if f_d is not None:
        latex += rf" $f_d = \frac{{2 v_r}}{{\lambda}} = {f_d:.1f}\,\text{{Hz}}$"

    return {
        "wavelength_m": wavelength_m,
        "pulse_repetition_interval_s": pri_s,
        "max_unambiguous_range_m": r_ua,
        "max_unambiguous_range_km": r_ua / 1000.0,
        "first_blind_speed_m_s": v_blind,
        "max_unambiguous_velocity_m_s": v_ua,
        "max_unambiguous_doppler_hz": f_d_ua,
        "range_velocity_product_m2_s": rv_product,
        "doppler_shift_hz": f_d,
        "doppler_aliased": aliased,
        "apparent_velocity_m_s": apparent_v,
        "range_resolution_m": range_res_m,
        "minimum_range_m": min_range_m,
        "duty_cycle": duty_cycle,
        "warnings": warnings,
        "human_readable": human_readable,
        "latex": latex,
    }
