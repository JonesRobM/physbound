"""Pydantic models for the standalone Antenna Gain tool."""

from pydantic import BaseModel, Field, model_validator

from physbound.models.common import PhysBoundResult


class AntennaGainInput(BaseModel):
    """Input parameters for antenna aperture gain calculation and claim validation."""

    frequency_hz: float = Field(gt=0, description="Operating frequency in Hz")
    diameter_m: float | None = Field(
        default=None, gt=0, description="Circular aperture diameter in meters"
    )
    aperture_area_m2: float | None = Field(
        default=None,
        gt=0,
        description="Physical aperture area in m^2 (alternative to diameter_m)",
    )
    claimed_gain_dbi: float | None = Field(
        default=None, description="Antenna gain claim to validate in dBi"
    )
    aperture_efficiency: float = Field(
        default=0.55,
        gt=0,
        le=1,
        description=(
            "Aperture efficiency used for the typical gain and warning threshold "
            "(default: 0.55, parabolic dish). The hard limit is max(eta = 1 aperture, Harrington)."
        ),
    )

    @model_validator(mode="after")
    def exactly_one_size(self):
        if self.diameter_m is None and self.aperture_area_m2 is None:
            raise ValueError("Exactly one of diameter_m or aperture_area_m2 must be provided")
        if self.diameter_m is not None and self.aperture_area_m2 is not None:
            raise ValueError("Provide only one of diameter_m or aperture_area_m2, not both")
        return self


class AntennaGainOutput(PhysBoundResult):
    """Output of the antenna aperture gain calculation."""

    frequency_hz: float
    wavelength_m: float
    diameter_m: float = Field(description="Circular (or equivalent circular) diameter, m")
    physical_aperture_m2: float = Field(description="A_phys = pi D^2 / 4")
    effective_aperture_m2: float = Field(description="A_e = eta * A_phys")
    aperture_efficiency: float
    physical_limit_dbi: float = Field(
        description=(
            "Hard physical gain limit, dBi: max(eta = 1 aperture value, Harrington bound "
            "(ka)^2 + 2ka, a = D/2) — numerically the Harrington value"
        )
    )
    aperture_limit_dbi: float = Field(
        description="eta = 1 planar-aperture gain (pi D / lambda)^2 = (ka)^2, dBi"
    )
    harrington_limit_dbi: float = Field(
        description=(
            "Harrington bound (ka)^2 + 2ka for an antenna enclosed in a sphere of diameter D, dBi"
        )
    )
    limiting_bound: str = Field(
        description=(
            "'harrington' when D < lambda (electrically small; aperture formula understates the "
            "bound) or 'aperture' when D >= lambda (Harrington and aperture values agree to "
            "within 10 log10(1 + 2 lambda / (pi D)) dB)"
        )
    )
    typical_gain_dbi: float = Field(description="G = eta (pi D / lambda)^2, dBi")
    directivity_linear: float = Field(
        description="Maximum directivity D_0 = 4 pi A_phys / lambda^2 (linear); G = eta * D_0"
    )
    half_power_beamwidth_deg: float = Field(
        description="HPBW ~ 70 lambda / D (tapered parabolic reflector approximation), degrees"
    )
    half_power_beamwidth_uniform_deg: float = Field(
        description="HPBW ~ 58.4 lambda / D (uniformly illuminated circular aperture), degrees"
    )
    far_field_distance_m: float = Field(description="Fraunhofer distance 2 D^2 / lambda, m")
    claimed_gain_dbi: float | None = None
    implied_efficiency: float | None = Field(
        default=None,
        description=(
            "Planar-aperture efficiency required to reach the claimed gain: "
            "G_claim / (pi D / lambda)^2; may exceed 1 for a valid electrically small antenna"
        ),
    )
    claim_is_valid: bool | None = None
