"""Pydantic models for the RF Link Budget tool."""

from pydantic import BaseModel, Field

from physbound.models.common import PhysBoundResult


class LinkBudgetInput(BaseModel):
    """Input parameters for RF link budget calculation using Friis transmission equation."""

    tx_power_dbm: float = Field(description="Transmit power in dBm")
    tx_antenna_gain_dbi: float = Field(description="Transmit antenna gain in dBi")
    rx_antenna_gain_dbi: float = Field(description="Receive antenna gain in dBi")
    frequency_hz: float = Field(gt=0, description="Carrier frequency in Hz")
    distance_m: float = Field(gt=0, description="Link distance in meters")
    tx_losses_db: float = Field(default=0.0, description="TX-side miscellaneous losses in dB")
    rx_losses_db: float = Field(default=0.0, description="RX-side miscellaneous losses in dB")
    tx_antenna_diameter_m: float | None = Field(
        default=None, description="TX antenna diameter in meters (enables aperture limit check)"
    )
    rx_antenna_diameter_m: float | None = Field(
        default=None, description="RX antenna diameter in meters (enables aperture limit check)"
    )


class LinkBudgetOutput(PhysBoundResult):
    """Output of the RF link budget calculation."""

    fspl_db: float
    received_power_dbm: float
    wavelength_m: float
    tx_aperture_limit_dbi: float | None = None
    rx_aperture_limit_dbi: float | None = None
