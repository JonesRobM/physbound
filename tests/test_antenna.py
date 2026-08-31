"""Tests for the standalone antenna aperture gain engine, models and MCP tool."""

import asyncio
import json
import math

import pytest
from pydantic import ValidationError

from physbound.engines.antenna import (
    HPBW_COEFF_TAPERED_DEG,
    HPBW_COEFF_UNIFORM_DEG,
    compute_antenna_gain,
    diameter_from_area_m,
    far_field_distance_m,
    half_power_beamwidth_deg,
)
from physbound.engines.constants import SPEED_OF_LIGHT
from physbound.errors import PhysicalViolationError
from physbound.models.antenna import AntennaGainInput, AntennaGainOutput
from physbound.server import mcp

DB_TOL = 0.01
C = SPEED_OF_LIGHT.magnitude


def call_tool(name: str, **kwargs) -> dict:
    tool = asyncio.run(mcp.get_tool(name))
    assert tool is not None
    return tool.fn(**kwargs)


class TestReferenceValues:
    def test_one_metre_dish_at_10ghz(self):
        """1 m dish at 10 GHz: lambda = 0.02998 m, (pi D/lambda)^2 -> 40.41 dBi at eta = 1,
        37.81 dBi at eta = 0.55; Harrington (ka)^2 + 2ka with ka = 104.8 -> 40.49 dBi."""
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0)
        assert abs(r["wavelength_m"] - 0.0299792458) < 1e-12
        assert abs(r["aperture_limit_dbi"] - 40.41) < DB_TOL
        assert abs(r["harrington_limit_dbi"] - 40.49) < DB_TOL
        assert r["physical_limit_dbi"] == r["harrington_limit_dbi"]
        assert r["limiting_bound"] == "aperture"
        assert abs(r["typical_gain_dbi"] - 37.81) < DB_TOL
        # Constant 10 log10(0.55) = -2.60 dB gap between the eta = 1 and eta = 0.55 aperture values
        assert abs(r["aperture_limit_dbi"] - r["typical_gain_dbi"] - 2.596) < DB_TOL

    def test_areas_and_directivity(self):
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0)
        assert abs(r["physical_aperture_m2"] - math.pi / 4) < 1e-12
        assert abs(r["effective_aperture_m2"] - 0.55 * math.pi / 4) < 1e-12
        # D_0 = 4 pi A / lambda^2 = (pi D / lambda)^2
        lam = C / 10e9
        assert abs(r["directivity_linear"] - (math.pi / lam) ** 2) < 1e-6 * (math.pi / lam) ** 2
        # G = eta * D_0
        g_lin = 10 ** (r["typical_gain_dbi"] / 10)
        assert abs(g_lin / r["directivity_linear"] - 0.55) < 1e-9

    def test_beamwidth_and_far_field(self):
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0)
        lam = C / 10e9
        assert abs(r["half_power_beamwidth_deg"] - 70 * lam) < 1e-9  # 2.099 deg
        assert abs(r["half_power_beamwidth_uniform_deg"] - 58.4 * lam) < 1e-9  # 1.751 deg
        assert abs(r["far_field_distance_m"] - 2 / lam) < 1e-6  # 66.71 m
        assert abs(r["far_field_distance_m"] - 66.71) < 0.01

    def test_readme_row_3_dish(self):
        """0.3 m dish at 1 GHz: 12.1 dBi Harrington, 9.9 dBi eta = 1 aperture, 7.4 dBi typical."""
        r = compute_antenna_gain(frequency_hz=1e9, diameter_m=0.3)
        assert abs(r["physical_limit_dbi"] - 12.09) < DB_TOL
        assert abs(r["aperture_limit_dbi"] - 9.95) < DB_TOL
        assert abs(r["typical_gain_dbi"] - 7.35) < DB_TOL
        assert r["limiting_bound"] == "aperture"  # D = 0.3 m > lambda = 0.2998 m

    def test_half_wave_dipole_in_10cm_footprint_at_900mhz(self):
        """2.15 dBi dipole in 0.1 m at 900 MHz: aperture eta = 1 is -0.5 dBi, Harrington 4.4 dBi."""
        r = compute_antenna_gain(frequency_hz=900e6, diameter_m=0.1, claimed_gain_dbi=2.15)
        assert r["claim_is_valid"] is True
        assert r["limiting_bound"] == "harrington"
        assert abs(r["aperture_limit_dbi"] - (-0.51)) < DB_TOL
        assert abs(r["physical_limit_dbi"] - 4.43) < DB_TOL
        assert r["implied_efficiency"] > 1.0
        assert any("Harrington" in w for w in r["warnings"])

    def test_area_input_matches_diameter_input(self):
        area = math.pi * 1.0**2 / 4
        r_d = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0)
        r_a = compute_antenna_gain(frequency_hz=10e9, aperture_area_m2=area)
        assert abs(r_a["diameter_m"] - 1.0) < 1e-12
        assert abs(r_a["physical_limit_dbi"] - r_d["physical_limit_dbi"]) < 1e-9

    def test_custom_efficiency(self):
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0, aperture_efficiency=0.7)
        assert abs(r["typical_gain_dbi"] - (40.41 + 10 * math.log10(0.7))) < DB_TOL
        assert abs(r["effective_aperture_m2"] - 0.7 * math.pi / 4) < 1e-12

    def test_gain_scales_20db_per_decade_of_frequency(self):
        r1 = compute_antenna_gain(frequency_hz=1e9, diameter_m=1.0)
        r2 = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0)
        assert abs((r2["aperture_limit_dbi"] - r1["aperture_limit_dbi"]) - 20.0) < 1e-9
        # the Harrington 2ka term makes the hard limit scale slightly slower than 20 dB/decade
        assert 19.0 < r2["physical_limit_dbi"] - r1["physical_limit_dbi"] < 20.0


class TestHelpers:
    def test_diameter_from_area(self):
        assert abs(diameter_from_area_m(math.pi) - 2.0) < 1e-12

    def test_diameter_from_area_rejects_non_positive(self):
        with pytest.raises(PhysicalViolationError, match="Aperture area"):
            diameter_from_area_m(0.0)
        with pytest.raises(PhysicalViolationError):
            diameter_from_area_m(-1.0)

    def test_hpbw_coefficients(self):
        assert abs(half_power_beamwidth_deg(2.0, 0.1) - HPBW_COEFF_TAPERED_DEG * 0.05) < 1e-12
        assert (
            abs(
                half_power_beamwidth_deg(2.0, 0.1, HPBW_COEFF_UNIFORM_DEG)
                - HPBW_COEFF_UNIFORM_DEG * 0.05
            )
            < 1e-12
        )

    def test_far_field_distance(self):
        assert abs(far_field_distance_m(3.0, 0.1) - 180.0) < 1e-12


class TestClaimValidation:
    def test_claim_below_typical_is_valid_no_warning(self):
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0, claimed_gain_dbi=35.0)
        assert r["claim_is_valid"] is True
        assert abs(r["implied_efficiency"] - 10 ** ((35.0 - 40.4066) / 10)) < 1e-4
        assert not any("typical-efficiency" in w for w in r["warnings"])
        assert "VALID" in r["human_readable"]

    def test_claim_between_typical_and_physical_warns(self):
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0, claimed_gain_dbi=39.0)
        assert r["claim_is_valid"] is True
        assert 0.55 < r["implied_efficiency"] <= 1.0
        assert any("typical-efficiency" in w for w in r["warnings"])

    def test_claim_at_physical_limit_is_boundary_valid(self):
        r0 = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0)
        r = compute_antenna_gain(
            frequency_hz=10e9, diameter_m=1.0, claimed_gain_dbi=r0["physical_limit_dbi"]
        )
        assert r["claim_is_valid"] is True
        # implied planar-aperture efficiency is just over 1 (the 2ka term, 0.08 dB here)
        assert 1.0 < r["implied_efficiency"] < 1.02

    def test_claim_at_aperture_limit_has_unit_efficiency(self):
        r0 = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0)
        r = compute_antenna_gain(
            frequency_hz=10e9, diameter_m=1.0, claimed_gain_dbi=r0["aperture_limit_dbi"]
        )
        assert abs(r["implied_efficiency"] - 1.0) < 1e-9
        assert any("typical-efficiency" in w for w in r["warnings"])

    def test_claim_above_physical_limit_raises(self):
        with pytest.raises(PhysicalViolationError, match="Aperture") as exc:
            compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0, claimed_gain_dbi=41.0)
        err = exc.value
        assert err.law_violated == "Antenna Aperture Limit"
        assert abs(err.computed_limit - 40.49) < DB_TOL
        assert err.claimed_value == 41.0
        assert err.unit == "dBi"

    def test_small_antenna_reports_harrington_regime(self):
        # 10 cm aperture at 900 MHz: lambda = 0.333 m > D
        r = compute_antenna_gain(frequency_hz=900e6, diameter_m=0.1)
        assert r["limiting_bound"] == "harrington"
        assert "regime: harrington" in r["human_readable"]
        assert not any("Harrington" in w for w in r["warnings"])
        # a claim below the typical gain adds no warning either
        r2 = compute_antenna_gain(frequency_hz=900e6, diameter_m=0.1, claimed_gain_dbi=-4.0)
        assert not any("Harrington" in w for w in r2["warnings"])
        # a claim above the Harrington bound is rejected
        with pytest.raises(PhysicalViolationError, match="Aperture"):
            compute_antenna_gain(frequency_hz=900e6, diameter_m=0.1, claimed_gain_dbi=4.5)

    def test_beamwidth_approximation_always_flagged(self):
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0)
        assert any("58.4" in w and "Balanis" in w for w in r["warnings"])

    def test_unity_efficiency_flagged(self):
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0, aperture_efficiency=1.0)
        assert abs(r["typical_gain_dbi"] - r["aperture_limit_dbi"]) < 1e-12
        assert any("aperture_efficiency = 1" in w for w in r["warnings"])


class TestEngineInputGuards:
    def test_zero_frequency(self):
        with pytest.raises(PhysicalViolationError):
            compute_antenna_gain(frequency_hz=0.0, diameter_m=1.0)

    def test_negative_diameter(self):
        with pytest.raises(PhysicalViolationError, match="diameter"):
            compute_antenna_gain(frequency_hz=1e9, diameter_m=-1.0)

    def test_efficiency_above_one(self):
        with pytest.raises(PhysicalViolationError, match="efficiency"):
            compute_antenna_gain(frequency_hz=1e9, diameter_m=1.0, aperture_efficiency=1.2)

    def test_neither_size_given(self):
        with pytest.raises(ValueError, match="Exactly one"):
            compute_antenna_gain(frequency_hz=1e9)

    def test_both_sizes_given(self):
        with pytest.raises(ValueError, match="Exactly one"):
            compute_antenna_gain(frequency_hz=1e9, diameter_m=1.0, aperture_area_m2=1.0)


class TestPydanticModels:
    def test_requires_exactly_one_size(self):
        with pytest.raises(ValidationError, match="Exactly one"):
            AntennaGainInput(frequency_hz=1e9)
        with pytest.raises(ValidationError, match="only one"):
            AntennaGainInput(frequency_hz=1e9, diameter_m=1.0, aperture_area_m2=0.5)

    def test_accepts_either_size(self):
        assert AntennaGainInput(frequency_hz=1e9, diameter_m=1.0).diameter_m == 1.0
        assert AntennaGainInput(frequency_hz=1e9, aperture_area_m2=2.0).aperture_area_m2 == 2.0

    def test_field_constraints(self):
        with pytest.raises(ValidationError):
            AntennaGainInput(frequency_hz=-1.0, diameter_m=1.0)
        with pytest.raises(ValidationError):
            AntennaGainInput(frequency_hz=1e9, diameter_m=0.0)
        with pytest.raises(ValidationError):
            AntennaGainInput(frequency_hz=1e9, aperture_area_m2=-1.0)
        with pytest.raises(ValidationError):
            AntennaGainInput(frequency_hz=1e9, diameter_m=1.0, aperture_efficiency=1.5)
        with pytest.raises(ValidationError):
            AntennaGainInput(frequency_hz=1e9, diameter_m=1.0, aperture_efficiency=0.0)

    def test_output_round_trips_engine_dict(self):
        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=1.0, claimed_gain_dbi=38.0)
        out = AntennaGainOutput(**r)
        dumped = out.model_dump()
        for key in (
            "wavelength_m",
            "physical_limit_dbi",
            "aperture_limit_dbi",
            "harrington_limit_dbi",
            "limiting_bound",
            "typical_gain_dbi",
            "effective_aperture_m2",
            "half_power_beamwidth_deg",
            "far_field_distance_m",
            "implied_efficiency",
            "claim_is_valid",
            "human_readable",
            "latex",
            "warnings",
        ):
            assert key in dumped


class TestMcpTool:
    def test_direct_invocation(self):
        r = call_tool("antenna_gain", frequency_hz=10e9, diameter_m=1.0)
        assert "error" not in r
        assert abs(r["physical_limit_dbi"] - 40.49) < DB_TOL
        assert abs(r["aperture_limit_dbi"] - 40.41) < DB_TOL
        assert r["limiting_bound"] == "aperture"
        assert abs(r["typical_gain_dbi"] - 37.81) < DB_TOL
        assert r["claim_is_valid"] is None

    def test_violation_returns_error_dict(self):
        r = call_tool("antenna_gain", frequency_hz=10e9, diameter_m=1.0, claimed_gain_dbi=45.0)
        assert r["error"] is True
        assert r["violation_type"] == "PhysicalViolationError"
        assert r["law_violated"] == "Antenna Aperture Limit"
        assert "latex" in r

    def test_pydantic_exactly_one_rule_surfaces(self):
        with pytest.raises(ValidationError):
            call_tool("antenna_gain", frequency_hz=10e9)

    def test_mcp_client_round_trip(self):
        from fastmcp.client import Client

        async def check():
            async with Client(mcp) as client:
                names = {t.name for t in await client.list_tools()}
                assert "antenna_gain" in names
                result = await client.call_tool(
                    "antenna_gain",
                    {
                        "frequency_hz": 10e9,
                        "aperture_area_m2": math.pi / 4,
                        "claimed_gain_dbi": 39.0,
                    },
                )
                assert not result.is_error
                data = json.loads(result.content[0].text)
                assert abs(data["diameter_m"] - 1.0) < 1e-9
                assert data["claim_is_valid"] is True
                assert data["typical_gain_dbi"] < 39.0 < data["physical_limit_dbi"]
                assert any("typical-efficiency" in w for w in data["warnings"])
                assert abs(data["far_field_distance_m"] - 66.71) < 0.01

        asyncio.new_event_loop().run_until_complete(check())
