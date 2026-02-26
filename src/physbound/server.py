"""PhysBound MCP Server — Physical Layer Linter for AI hallucination detection.

Exposes four RF validation tools via the Model Context Protocol (MCP):
  1. rf_link_budget — Friis transmission link budget with aperture limit checks
  2. shannon_hartley — Shannon-Hartley channel capacity and throughput validation
  3. noise_floor — Thermal noise, Friis noise cascade, and receiver sensitivity
  4. radar_range — Monostatic radar range equation with R_max and claim validation
"""

from fastmcp import FastMCP

from physbound.engines import link_budget as lb_engine
from physbound.engines import noise as nz_engine
from physbound.engines import radar as rd_engine
from physbound.engines import shannon as sh_engine
from physbound.engines.constants import BOLTZMANN
from physbound.engines.units import db_to_linear, linear_to_db
from physbound.errors import PhysicalViolationError
from physbound.models.link_budget import LinkBudgetOutput
from physbound.models.noise import NoiseFloorInput, NoiseFloorOutput, NoiseStage
from physbound.models.radar import RadarRangeInput, RadarRangeOutput
from physbound.models.shannon import ShannonInput, ShannonOutput

mcp = FastMCP(
    name="PhysBound",
    instructions=(
        "Physics validation MCP server. Validates RF link budgets, "
        "Shannon-Hartley channel capacity claims, thermal noise calculations, "
        "and radar range equations against hard physical limits. "
        "Catches AI hallucinations in physics."
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
) -> dict:
    """Calculate a complete RF link budget using the Friis transmission equation.

    Computes free-space path loss (FSPL), received power, and validates antenna
    gains against aperture limits (G_max = eta * (pi*D/lambda)^2). Rejects any
    configuration that implies physically impossible antenna performance.

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
    F_total = F_1 + (F_2-1)/G_1 + (F_3-1)/(G_1*G_2) + ... and computes
    receiver sensitivity as S_min = N_floor + NF + SNR_required.

    Use this tool when you need to:
    - Determine the thermal noise floor for a receiver bandwidth
    - Cascade noise figures through a multi-stage receiver chain
    - Calculate minimum detectable signal / receiver sensitivity
    - Validate that a claimed noise figure is physically plausible

    Returns a PhysicalViolationError dict if inputs violate thermodynamic limits.

    Args:
        bandwidth_hz: Receiver bandwidth in Hz (must be > 0)
        temperature_k: System noise temperature in Kelvin (default: 290K, must be >= 0)
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
            # System noise temperature: T_sys = T_ref * (F - 1)
            f_linear = db_to_linear(cascaded_nf_db)
            system_noise_temp_k = params.temperature_k * (f_linear - 1)

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


def main():
    """Entry point for `physbound` console script and stdio MCP."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
