"""Pydantic models for the Shannon-Hartley Channel Capacity tool."""

from pydantic import BaseModel, Field, model_validator

from physbound.models.common import PhysBoundResult


class ShannonInput(BaseModel):
    """Input parameters for Shannon-Hartley channel capacity validation."""

    bandwidth_hz: float = Field(gt=0, description="Channel bandwidth in Hz")
    snr_linear: float | None = Field(
        default=None, description="Signal-to-noise ratio (linear, not dB)"
    )
    snr_db: float | None = Field(
        default=None, description="Signal-to-noise ratio in dB (alternative to snr_linear)"
    )
    claimed_throughput_bps: float | None = Field(
        default=None, description="Throughput claim to validate in bits per second"
    )

    @model_validator(mode="after")
    def exactly_one_snr(self):
        if self.snr_linear is None and self.snr_db is None:
            raise ValueError("Exactly one of snr_linear or snr_db must be provided")
        if self.snr_linear is not None and self.snr_db is not None:
            raise ValueError("Provide only one of snr_linear or snr_db, not both")
        return self


class ShannonOutput(PhysBoundResult):
    """Output of Shannon-Hartley channel capacity calculation."""

    capacity_bps: float
    spectral_efficiency_bps_hz: float
    snr_db: float
    snr_linear: float
    claimed_throughput_bps: float | None = None
    claim_is_valid: bool | None = None
    excess_percentage: float | None = None
