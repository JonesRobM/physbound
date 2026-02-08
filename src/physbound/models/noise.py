"""Pydantic models for the Thermal Noise Floor tool."""

from pydantic import BaseModel, Field

from physbound.models.common import PhysBoundResult


class NoiseStage(BaseModel):
    """A single amplifier/component stage for Friis noise figure cascading."""

    gain_db: float = Field(description="Stage gain in dB")
    noise_figure_db: float = Field(ge=0, description="Stage noise figure in dB")


class NoiseFloorInput(BaseModel):
    """Input parameters for thermal noise floor and receiver sensitivity calculation."""

    bandwidth_hz: float = Field(gt=0, description="Receiver bandwidth in Hz")
    temperature_k: float = Field(
        default=290.0, ge=0, description="System noise temperature in Kelvin (default: 290K)"
    )
    stages: list[NoiseStage] | None = Field(
        default=None, description="Optional cascade of amplifier stages for Friis noise formula"
    )
    required_snr_db: float | None = Field(
        default=None, description="Required SNR in dB for receiver sensitivity calculation"
    )


class NoiseFloorOutput(PhysBoundResult):
    """Output of thermal noise floor and sensitivity calculation."""

    thermal_noise_dbm: float
    thermal_noise_watts: float
    cascaded_noise_figure_db: float | None = None
    system_noise_temp_k: float | None = None
    receiver_sensitivity_dbm: float | None = None
