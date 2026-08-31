"""PhysBound MCP Server — Physical Layer Linter for AI hallucination detection.

Exposes six RF validation tools via the Model Context Protocol (MCP):
  1. rf_link_budget — Friis transmission link budget with aperture limit checks
  2. shannon_hartley — Shannon-Hartley channel capacity and throughput validation
  3. noise_floor — Thermal noise, Friis noise cascade, and receiver sensitivity
  4. radar_range — Monostatic radar range equation with R_max and claim validation
  5. antenna_gain — Aperture gain limits, beamwidth, far-field distance, gain claims
  6. radar_ambiguity — Pulse-Doppler unambiguous range/velocity, Doppler and resolution
"""

from fastmcp import FastMCP

from physbound.engines import antenna as ant_engine
from physbound.engines import doppler as dp_engine
from physbound.engines import link_budget as lb_engine
from physbound.engines import noise as nz_engine
from physbound.engines import radar as rd_engine
from physbound.engines import shannon as sh_engine
from physbound.engines.constants import BOLTZMANN, T_REF
from physbound.engines.units import db_to_linear, linear_to_db
from physbound.errors import PhysicalViolationError
from physbound.models.antenna import AntennaGainInput, AntennaGainOutput
from physbound.models.doppler import RadarAmbiguityInput, RadarAmbiguityOutput
from physbound.models.link_budget import LinkBudgetOutput
from physbound.models.noise import NoiseFloorInput, NoiseFloorOutput, NoiseStage
from physbound.models.radar import RadarRangeInput, RadarRangeOutput
from physbound.models.shannon import ShannonInput, ShannonOutput

mcp = FastMCP(
    name="PhysBound",
    instructions=(
        "Physics validation MCP server with six tools. Validates RF link budgets, "
        "Shannon-Hartley channel capacity claims, thermal noise calculations, "
        "radar range equations, antenna gain claims (aperture and Harrington "
        "bounds) and pulse-Doppler radar ambiguity (unambiguous range/velocity) "
        "against hard physical limits. Catches AI hallucinations in physics."
    ),
)


@mcp.tool
def rf_link_budget(
    tx_power_dbm: float,
    tx_antenna_gain_dbi: float,
    rx_antenna_gain_dbi: float,
    frequency_hz: float,
    distance_m: float,
    tx_losses_db: float = 0.0,
    rx_losses_db: float = 0.0,
    tx_antenna_diameter_m: float | None = None,
    rx_antenna_diameter_m: float | None = None,
    aperture_efficiency: float = 0.55,
) -> dict:
    """Calculate a complete RF link budget using the Friis transmission equation.

    Computes free-space path loss (FSPL), received power, and validates antenna
    gains against the physical gain limit. The hard bound is
    G_max = max((pi*D/lambda)^2, (ka)^2 + 2ka) with k = 2*pi/lambda and a = D/2,
    i.e. the larger of the eta = 1 aperture value and Harrington's bound for an
    antenna enclosed in a sphere of diameter D (numerically the Harrington value,
    which converges to the aperture value for D >> lambda and matters for
    electrically small antennas, D < lambda); a claimed gain above it is
    rejected. A claimed gain above the typical-efficiency value
    eta*(pi*D/lambda)^2 (eta = 0.55 by default) but below the physical bound is
    accepted with a warning. Negative losses are rejected (conservation of energy).

    Use this tool when you need to:
    - Estimate received signal strength for a wireless link
    - Validate whether a claimed link budget is physically achievable
    - Check if antenna gain claims are consistent with antenna dimensions
    - Compute free-space path loss at a given frequency and distance

    Returns both human-readable summary and machine-readable JSON with all
    intermediate values. Returns a PhysicalViolationError dict if any input
    violates physics.

    Args:
        tx_power_dbm: Transmit power in dBm
        tx_antenna_gain_dbi: Transmit antenna gain in dBi
        rx_antenna_gain_dbi: Receive antenna gain in dBi
        frequency_hz: Carrier frequency in Hz (must be > 0)
        distance_m: Link distance in meters (must be > 0)
        tx_losses_db: TX-side miscellaneous losses in dB (default: 0)
        rx_losses_db: RX-side miscellaneous losses in dB (default: 0)
        tx_antenna_diameter_m: TX antenna diameter in meters (enables aperture check)
        rx_antenna_diameter_m: RX antenna diameter in meters (enables aperture check)
        aperture_efficiency: Efficiency for the typical-gain warning threshold
            (default: 0.55 for a parabolic dish; the hard limit is
            max(eta = 1 aperture value, Harrington bound))
    """
    try:
        result = lb_engine.compute_link_budget(
            tx_power_dbm=tx_power_dbm,
            tx_antenna_gain_dbi=tx_antenna_gain_dbi,
            rx_antenna_gain_dbi=rx_antenna_gain_dbi,
            frequency_hz=frequency_hz,
            distance_m=distance_m,
            tx_losses_db=tx_losses_db,
            rx_losses_db=rx_losses_db,
            tx_antenna_diameter_m=tx_antenna_diameter_m,
            rx_antenna_diameter_m=rx_antenna_diameter_m,
            aperture_efficiency=aperture_efficiency,
        )
        return LinkBudgetOutput(**result).model_dump()
    except PhysicalViolationError as e:
        return e.to_dict()


@mcp.tool
def shannon_hartley(
    bandwidth_hz: float,
    snr_linear: float | None = None,
    snr_db: float | None = None,
    claimed_throughput_bps: float | None = None,
) -> dict:
    """Calculate Shannon-Hartley channel capacity and validate throughput claims.

    Computes the theoretical maximum data rate C = B * log2(1 + SNR) for an AWGN
    channel. If a claimed throughput is provided, validates it against this limit.
    Any claim exceeding the Shannon limit is a physical impossibility.

    Use this tool when you need to:
    - Calculate maximum achievable throughput for a given bandwidth and SNR
    - Validate whether a throughput claim is physically possible
    - Determine spectral efficiency limits
    - Check if a modulation/coding scheme claim is realistic

    Returns a PhysicalViolationError dict when a claim exceeds the Shannon limit.

    Args:
        bandwidth_hz: Channel bandwidth in Hz (must be > 0)
        snr_linear: Signal-to-noise ratio (linear, not dB). Provide this OR snr_db.
        snr_db: Signal-to-noise ratio in dB. Provide this OR snr_linear.
        claimed_throughput_bps: Optional throughput claim to validate in bits/sec
    """
    try:
        # Validate and resolve SNR
        params = ShannonInput(
            bandwidth_hz=bandwidth_hz,
            snr_linear=snr_linear,
            snr_db=snr_db,
            claimed_throughput_bps=claimed_throughput_bps,
        )

        # Resolve SNR to both representations
        # Model validator guarantees exactly one of snr_db/snr_linear is set
        if params.snr_db is not None:
            resolved_snr_linear = db_to_linear(params.snr_db)
            resolved_snr_db = params.snr_db
        else:
            assert params.snr_linear is not None
            resolved_snr_linear = params.snr_linear
            resolved_snr_db = linear_to_db(params.snr_linear)

        capacity = sh_engine.channel_capacity_bps(params.bandwidth_hz, resolved_snr_linear)
        eta = sh_engine.spectral_efficiency(resolved_snr_linear)

        # If throughput claim provided, validate it
        claim_is_valid = None
        excess_percentage = None
        warnings: list[str] = []

        if params.claimed_throughput_bps is not None:
            result = sh_engine.validate_throughput_claim(
                params.bandwidth_hz, resolved_snr_linear, params.claimed_throughput_bps
            )
            claim_is_valid = result["claim_is_valid"]
            excess_percentage = result["excess_percentage"]
            warnings = result["warnings"]

        human_readable = (
            f"Shannon-Hartley Capacity:\n"
            f"  Bandwidth:  {params.bandwidth_hz / 1e6:.3f} MHz\n"
            f"  SNR:        {resolved_snr_db:.1f} dB ({resolved_snr_linear:.2f} linear)\n"
            f"  Capacity:   {capacity:.1f} bps ({capacity / 1e6:.3f} Mbps)\n"
            f"  Spectral Efficiency: {eta:.3f} bps/Hz"
        )

        latex = (
            rf"$C = B \log_2(1 + \text{{SNR}}) = "
            rf"{params.bandwidth_hz:.0f} \times \log_2(1 + {resolved_snr_linear:.2f}) = "
            rf"{capacity:.1f}\,\text{{bps}}$"
        )

        return ShannonOutput(
            capacity_bps=capacity,
            spectral_efficiency_bps_hz=eta,
            snr_db=resolved_snr_db,
            snr_linear=resolved_snr_linear,
            claimed_throughput_bps=params.claimed_throughput_bps,
            claim_is_valid=claim_is_valid,
            excess_percentage=excess_percentage,
            human_readable=human_readable,
            latex=latex,
            warnings=warnings,
        ).model_dump()

    except PhysicalViolationError as e:
        return e.to_dict()


@mcp.tool
def noise_floor(
    bandwidth_hz: float,
    temperature_k: float = 290.0,
    stages: list[dict] | None = None,
    required_snr_db: float | None = None,
) -> dict:
    """Calculate thermal noise power (kTB), cascaded noise figure, and receiver sensitivity.

    Computes the fundamental thermal noise floor N = k_B * T * B, which is
    -174 dBm/Hz at the IEEE standard temperature of 290K. Optionally cascades
    multiple amplifier/filter stages using the Friis noise figure formula
    F_total = F_1 + (F_2-1)/G_1 + (F_3-1)/(G_1*G_2) + ..., the receiver's
    effective input noise temperature T_e = T_0*(F-1) with T_0 = 290 K (the
    IEEE reference at which noise figure is defined, independent of
    temperature_k), and receiver sensitivity
    S_min = k_B*(T_A + T_e)*B*SNR_required, which reduces to
    N_floor + NF + SNR_required when temperature_k = 290 K.

    Use this tool when you need to:
    - Determine the thermal noise floor for a receiver bandwidth
    - Cascade noise figures through a multi-stage receiver chain
    - Calculate minimum detectable signal / receiver sensitivity
    - Validate that a claimed noise figure is physically plausible

    Returns a PhysicalViolationError dict if inputs violate thermodynamic limits.

    Args:
        bandwidth_hz: Receiver bandwidth in Hz (must be > 0)
        temperature_k: Source/antenna noise temperature T_A in Kelvin used for the
            kTB floor (default: 290K, must be >= 0)
        stages: Optional list of stages, each with 'gain_db' and 'noise_figure_db' keys
        required_snr_db: Required SNR in dB for sensitivity calculation
    """
    try:
        params = NoiseFloorInput(
            bandwidth_hz=bandwidth_hz,
            temperature_k=temperature_k,
            stages=[
                NoiseStage(gain_db=s["gain_db"], noise_figure_db=s["noise_figure_db"])
                for s in stages
            ]
            if stages
            else None,
            required_snr_db=required_snr_db,
        )

        n_dbm = nz_engine.thermal_noise_power_dbm(params.bandwidth_hz, params.temperature_k)
        n_watts = nz_engine.thermal_noise_power_watts(params.bandwidth_hz, params.temperature_k)

        warnings: list[str] = []
        cascaded_nf_db = None
        system_noise_temp_k = None
        sensitivity_dbm = None

        # Friis noise cascade if stages provided
        if params.stages:
            stage_tuples = [(s.gain_db, s.noise_figure_db) for s in params.stages]
            cascaded_nf_db = nz_engine.friis_noise_cascade(stage_tuples)
            # Effective input noise temperature: T_e = T_0 * (F - 1), T_0 = 290 K.
            # NF is defined at T_0 (IEEE), so this does not depend on temperature_k.
            system_noise_temp_k = nz_engine.effective_noise_temperature_k(cascaded_nf_db)
            if params.temperature_k != T_REF.magnitude:
                warnings.append(
                    f"Noise figure is referenced to T_0 = {T_REF.magnitude:.0f} K; "
                    f"temperature_k = {params.temperature_k:.1f} K is treated as the "
                    "source/antenna temperature T_A and the receiver adds "
                    f"T_e = T_0 (F - 1) = {system_noise_temp_k:.1f} K on top of it"
                )

        # Receiver sensitivity
        if params.required_snr_db is not None:
            nf = cascaded_nf_db if cascaded_nf_db is not None else 0.0
            sensitivity_dbm = nz_engine.receiver_sensitivity_dbm(
                params.bandwidth_hz, nf, params.required_snr_db, params.temperature_k
            )

        human_readable = (
            f"Thermal Noise Floor:\n"
            f"  Temperature: {params.temperature_k:.1f} K\n"
            f"  Bandwidth:   {params.bandwidth_hz / 1e6:.3f} MHz\n"
            f"  Noise Power: {n_dbm:.2f} dBm ({n_watts:.3e} W)"
        )
        if cascaded_nf_db is not None:
            human_readable += f"\n  Cascaded NF: {cascaded_nf_db:.2f} dB"
            human_readable += f"\n  T_e = T_0(F-1): {system_noise_temp_k:.2f} K"
        if sensitivity_dbm is not None:
            human_readable += f"\n  Sensitivity: {sensitivity_dbm:.2f} dBm"

        k_b = BOLTZMANN.magnitude
        latex = (
            rf"$N = k_B T B = {k_b:.4e} \times {params.temperature_k:.1f} "
            rf"\times {params.bandwidth_hz:.0f} = {n_dbm:.2f}\,\text{{dBm}}$"
        )

        return NoiseFloorOutput(
            thermal_noise_dbm=n_dbm,
            thermal_noise_watts=n_watts,
            cascaded_noise_figure_db=cascaded_nf_db,
            system_noise_temp_k=system_noise_temp_k,
            receiver_sensitivity_dbm=sensitivity_dbm,
            human_readable=human_readable,
            latex=latex,
            warnings=warnings,
        ).model_dump()

    except PhysicalViolationError as e:
        return e.to_dict()


@mcp.tool
def radar_range(
    peak_power_w: float,
    antenna_gain_dbi: float,
    frequency_hz: float,
    rcs_m2: float,
    system_noise_temp_k: float = 290.0,
    noise_bandwidth_hz: float = 1e6,
    min_snr_db: float = 13.0,
    claimed_range_m: float | None = None,
    num_pulses: int = 1,
    losses_db: float = 0.0,
) -> dict:
    """Calculate maximum monostatic radar detection range and validate range claims.

    Computes the radar range equation R_max = [P_t * G^2 * lambda^2 * sigma /
    ((4*pi)^3 * S_min * L)]^(1/4) for a monostatic radar (same antenna for
    transmit and receive). Validates that claimed detection ranges do not exceed
    the theoretical maximum. Catches the common fourth-root fallacy where LLMs
    incorrectly state that doubling transmit power doubles radar range (it only
    increases range by a factor of 2^(1/4) = 1.19x).

    Use this tool when you need to:
    - Calculate the maximum detection range of a radar system
    - Validate whether a claimed radar detection range is physically achievable
    - Determine minimum detectable signal power for a radar receiver
    - Check if radar performance claims account for the R^4 path loss
    - Verify that RCS assumptions are reasonable for the target class

    Returns both human-readable summary and machine-readable JSON with all
    intermediate values. Returns a PhysicalViolationError dict if any input
    violates physics or the claimed range exceeds R_max.

    Args:
        peak_power_w: Peak transmit power in watts (must be > 0)
        antenna_gain_dbi: Antenna gain in dBi (same antenna for TX and RX)
        frequency_hz: Operating frequency in Hz (must be > 0)
        rcs_m2: Radar cross section of the target in m^2 (must be > 0)
        system_noise_temp_k: System noise temperature in Kelvin (default: 290K)
        noise_bandwidth_hz: Receiver noise bandwidth in Hz (default: 1 MHz)
        min_snr_db: Minimum required SNR in dB for detection (default: 13 dB, Swerling I)
        claimed_range_m: Optional claimed detection range to validate against R_max (meters)
        num_pulses: Number of integrated pulses for integration gain (default: 1)
        losses_db: Total system losses in dB (default: 0)
    """
    try:
        params = RadarRangeInput(
            peak_power_w=peak_power_w,
            antenna_gain_dbi=antenna_gain_dbi,
            frequency_hz=frequency_hz,
            rcs_m2=rcs_m2,
            system_noise_temp_k=system_noise_temp_k,
            noise_bandwidth_hz=noise_bandwidth_hz,
            min_snr_db=min_snr_db,
            claimed_range_m=claimed_range_m,
            num_pulses=num_pulses,
            losses_db=losses_db,
        )
        result = rd_engine.compute_radar_range(
            peak_power_w=params.peak_power_w,
            antenna_gain_dbi=params.antenna_gain_dbi,
            frequency_hz=params.frequency_hz,
            rcs_m2=params.rcs_m2,
            system_noise_temp_k=params.system_noise_temp_k,
            noise_bandwidth_hz=params.noise_bandwidth_hz,
            min_snr_db=params.min_snr_db,
            claimed_range_m=params.claimed_range_m,
            num_pulses=params.num_pulses,
            losses_db=params.losses_db,
        )
        return RadarRangeOutput(**result).model_dump()
    except PhysicalViolationError as e:
        return e.to_dict()


@mcp.tool
def antenna_gain(
    frequency_hz: float,
    diameter_m: float | None = None,
    aperture_area_m2: float | None = None,
    claimed_gain_dbi: float | None = None,
    aperture_efficiency: float = 0.55,
) -> dict:
    """Calculate antenna aperture gain limits, beamwidth, far-field distance; validate gain claims.

    For a circular aperture of diameter D (or an aperture of area A, converted to
    the equivalent circular diameter D = sqrt(4A/pi)) computes the planar-aperture
    directivity D_0 = 4*pi*A/lambda^2 = (pi*D/lambda)^2 (aperture efficiency
    eta = 1), Harrington's bound D_max = (ka)^2 + 2ka (k = 2*pi/lambda, a = D/2)
    for any antenna enclosed in a sphere of diameter D, the hard physical gain
    limit max(D_0, D_max) (numerically D_max; equal to D_0 to within 0.1 dB for
    D >> lambda, but several dB higher for electrically small antennas D < lambda,
    e.g. a 2.15 dBi dipole in a 0.1 m footprint at 900 MHz is valid although
    D_0 = -0.5 dBi), and the typical gain G = eta*D_0 at the given efficiency
    (default eta = 0.55, parabolic dish). The limiting_bound field reports
    'harrington' for D < lambda and 'aperture' for D >= lambda.
    Also returns the effective aperture A_e = eta*A, a half-power beamwidth
    estimate (HPBW ~ 70*lambda/D degrees for a tapered reflector; 58.4*lambda/D
    for a uniformly illuminated circular aperture) and the far-field
    (Fraunhofer) distance 2*D^2/lambda.

    If claimed_gain_dbi is given it is validated: a claim above the physical
    limit is rejected as a physics violation; a claim between the typical gain
    and the physical limit is accepted with a warning and the implied
    planar-aperture efficiency eta = G_claim / D_0 is reported.

    Use this tool when you need to:
    - Check whether a quoted antenna gain is consistent with its size and frequency
    - Estimate the gain, beamwidth or effective aperture of a dish of known diameter
    - Find the minimum far-field range for antenna measurements or Friis validity
    - Size an antenna for a required gain at a given frequency

    Returns a PhysicalViolationError dict if any input violates physics or the
    claimed gain exceeds the aperture limit.

    Args:
        frequency_hz: Operating frequency in Hz (must be > 0)
        diameter_m: Circular aperture diameter in meters. Provide this OR aperture_area_m2.
        aperture_area_m2: Physical aperture area in m^2. Provide this OR diameter_m.
        claimed_gain_dbi: Optional antenna gain claim to validate in dBi
        aperture_efficiency: Efficiency for the typical gain / warning threshold
            (default: 0.55 for a parabolic dish; the hard limit is
            max(eta = 1 aperture value, Harrington bound))
    """
    try:
        params = AntennaGainInput(
            frequency_hz=frequency_hz,
            diameter_m=diameter_m,
            aperture_area_m2=aperture_area_m2,
            claimed_gain_dbi=claimed_gain_dbi,
            aperture_efficiency=aperture_efficiency,
        )
        result = ant_engine.compute_antenna_gain(
            frequency_hz=params.frequency_hz,
            diameter_m=params.diameter_m,
            aperture_area_m2=params.aperture_area_m2,
            claimed_gain_dbi=params.claimed_gain_dbi,
            aperture_efficiency=params.aperture_efficiency,
        )
        return AntennaGainOutput(**result).model_dump()
    except PhysicalViolationError as e:
        return e.to_dict()


@mcp.tool
def radar_ambiguity(
    frequency_hz: float,
    prf_hz: float,
    pulse_width_s: float | None = None,
    target_velocity_m_s: float | None = None,
    bandwidth_hz: float | None = None,
    claimed_unambiguous_range_m: float | None = None,
    claimed_unambiguous_velocity_m_s: float | None = None,
    claimed_range_resolution_m: float | None = None,
) -> dict:
    """Calculate pulse-Doppler radar ambiguity limits and validate range/velocity claims.

    Computes the maximum unambiguous range R_ua = c / (2 * PRF), the first blind
    speed lambda * PRF / 2, the unambiguous velocity v_ua = +/- lambda * PRF / 4
    (Doppler within +/- PRF/2), the Doppler shift f_d = 2 * v_r / lambda of a
    target (closing velocity positive) and whether it aliases, and — when a pulse
    width is given — the duty cycle, eclipsing minimum range c * tau / 2 and the
    range resolution c * tau / 2 (or c / (2 B) when a compressed bandwidth is
    supplied). Reports the range-Doppler dilemma invariant R_ua * v_ua = c * lambda / 8,
    which no choice of PRF can beat (Skolnik, Introduction to Radar Systems, Ch. 2-3;
    Richards, Fundamentals of Radar Signal Processing, Ch. 1, 3, 5).

    Use this tool when you need to:
    - Find the unambiguous range and velocity coverage of a given PRF
    - Check whether a claimed unambiguous range or velocity is possible at that PRF
    - Check whether a claimed range resolution is possible for the pulse/bandwidth
    - Determine whether a target's Doppler will alias or fall at a blind speed
    - Expose claims that silently violate the range-Doppler dilemma

    Returns both human-readable summary and machine-readable JSON with all
    intermediate values. Returns a PhysicalViolationError dict if any input
    violates physics (PRF <= 0, tau <= 0, duty cycle >= 1) or a claim exceeds
    its limit.

    Args:
        frequency_hz: Carrier frequency in Hz (must be > 0)
        prf_hz: Pulse repetition frequency in Hz (must be > 0)
        pulse_width_s: Optional transmitted pulse width tau in seconds (must be > 0)
        target_velocity_m_s: Optional target radial velocity in m/s (closing positive)
        bandwidth_hz: Optional compressed bandwidth in Hz; sets the resolution limit to c/(2B)
        claimed_unambiguous_range_m: Optional claimed unambiguous range to validate (m)
        claimed_unambiguous_velocity_m_s: Optional claimed unambiguous velocity to validate (m/s)
        claimed_range_resolution_m: Optional claimed range resolution to validate (m)
    """
    try:
        params = RadarAmbiguityInput(
            frequency_hz=frequency_hz,
            prf_hz=prf_hz,
            pulse_width_s=pulse_width_s,
            target_velocity_m_s=target_velocity_m_s,
            bandwidth_hz=bandwidth_hz,
            claimed_unambiguous_range_m=claimed_unambiguous_range_m,
            claimed_unambiguous_velocity_m_s=claimed_unambiguous_velocity_m_s,
            claimed_range_resolution_m=claimed_range_resolution_m,
        )
        result = dp_engine.compute_radar_ambiguity(
            frequency_hz=params.frequency_hz,
            prf_hz=params.prf_hz,
            pulse_width_s=params.pulse_width_s,
            target_velocity_m_s=params.target_velocity_m_s,
            bandwidth_hz=params.bandwidth_hz,
            claimed_unambiguous_range_m=params.claimed_unambiguous_range_m,
            claimed_unambiguous_velocity_m_s=params.claimed_unambiguous_velocity_m_s,
            claimed_range_resolution_m=params.claimed_range_resolution_m,
        )
        return RadarAmbiguityOutput(**result).model_dump()
    except PhysicalViolationError as e:
        return e.to_dict()


def main():
    """Entry point for `physbound` console script and stdio MCP."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
