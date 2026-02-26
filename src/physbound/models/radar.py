"""Pydantic models for the Radar Range Equation tool."""

from pydantic import BaseModel, Field

from physbound.models.common import PhysBoundResult


class RadarRangeInput(BaseModel):
    """Input parameters for monostatic radar range equation calculation."""

    peak_power_w: float = Field(gt=0, description="Peak transmit power in watts")
    antenna_gain_dbi: float = Field(description="Antenna gain in dBi (same antenna TX/RX)")
    frequency_hz: float = Field(gt=0, description="Operating frequency in Hz")
    rcs_m2: float = Field(gt=0, description="Radar cross section in m^2")
    system_noise_temp_k: float = Field(
        default=290.0, ge=0, description="System noise temperature in Kelvin (default: 290K)"
    )
    noise_bandwidth_hz: float = Field(
        default=1e6, gt=0, description="Receiver noise bandwidth in Hz (default: 1 MHz)"
    )
    min_snr_db: float = Field(
        default=13.0,
        description=(
            "Minimum required SNR in dB for detection (default: 13 dB, Swerling I Pd=0.9 Pfa=1e-6)"
        ),
    )
    claimed_range_m: float | None = Field(
        default=None, gt=0, description="Optional claimed detection range to validate (meters)"
    )
    num_pulses: int = Field(default=1, ge=1, description="Number of integrated pulses (default: 1)")
    losses_db: float = Field(
        default=0.0, ge=0, description="Total system losses in dB (default: 0)"
    )


class RadarRangeOutput(PhysBoundResult):
    """Output of monostatic radar range equation calculation."""

    max_range_m: float
    max_range_km: float
    wavelength_m: float
    min_detectable_power_w: float
    min_detectable_power_dbm: float
    antenna_gain_linear: float
    snr_min_linear: float
    integration_gain: int
    losses_linear: float
