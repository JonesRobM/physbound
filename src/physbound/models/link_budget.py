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
    tx_losses_db: float = Field(
        default=0.0, ge=0, description="TX-side miscellaneous losses in dB (must be >= 0)"
    )
    rx_losses_db: float = Field(
        default=0.0, ge=0, description="RX-side miscellaneous losses in dB (must be >= 0)"
    )
    tx_antenna_diameter_m: float | None = Field(
        default=None,
        gt=0,
        description="TX antenna diameter in meters (enables aperture limit check)",
    )
    rx_antenna_diameter_m: float | None = Field(
        default=None,
        gt=0,
        description="RX antenna diameter in meters (enables aperture limit check)",
    )
    aperture_efficiency: float = Field(
        default=0.55,
        gt=0,
        le=1,
        description=(
            "Aperture efficiency used for the typical-gain warning threshold "
            "(default: 0.55, parabolic dish). The hard limit is max(eta = 1 aperture, Harrington)."
        ),
    )


class LinkBudgetOutput(PhysBoundResult):
    """Output of the RF link budget calculation."""

    fspl_db: float
    received_power_dbm: float
    wavelength_m: float
    tx_physical_limit_dbi: float | None = Field(
        default=None,
        description=(
            "Hard physical gain limit for the TX antenna, dBi: "
            "max(eta = 1 aperture value, Harrington bound (ka)^2 + 2ka)"
        ),
    )
    rx_physical_limit_dbi: float | None = Field(
        default=None,
        description=(
            "Hard physical gain limit for the RX antenna, dBi: "
            "max(eta = 1 aperture value, Harrington bound (ka)^2 + 2ka)"
        ),
    )
    tx_aperture_limit_dbi: float | None = Field(
        default=None, description="eta = 1 planar-aperture gain (pi D / lambda)^2, TX antenna, dBi"
    )
    rx_aperture_limit_dbi: float | None = Field(
        default=None, description="eta = 1 planar-aperture gain (pi D / lambda)^2, RX antenna, dBi"
    )
    tx_typical_aperture_gain_dbi: float | None = Field(
        default=None, description="TX aperture gain at the typical efficiency, dBi"
    )
    rx_typical_aperture_gain_dbi: float | None = Field(
        default=None, description="RX aperture gain at the typical efficiency, dBi"
    )
    tx_limiting_bound: str | None = Field(
        default=None,
        description=(
            "Regime setting the TX limit: 'harrington' (D < lambda, electrically small) "
            "or 'aperture' (D >= lambda)"
        ),
    )
    rx_limiting_bound: str | None = Field(
        default=None,
        description=(
            "Regime setting the RX limit: 'harrington' (D < lambda, electrically small) "
            "or 'aperture' (D >= lambda)"
        ),
    )
    aperture_efficiency: float = Field(
        default=0.55, description="Efficiency used for the typical-gain warning threshold"
    )
