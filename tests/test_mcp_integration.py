"""End-to-end MCP integration tests.

Tests the full MCP protocol round trip: client connects to server,
discovers tools, calls them, and validates structured responses.
This proves the MCP server works as a real client would use it.
"""

import asyncio
import json

import pytest

from physbound.server import mcp

try:
    from fastmcp.client import Client

    HAS_CLIENT = True
except ImportError:
    HAS_CLIENT = False


def run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture()
def client():
    """Create an MCP client connected to the PhysBound server."""
    if not HAS_CLIENT:
        pytest.skip("fastmcp.client not available")
    return Client(mcp)


class TestMCPToolDiscovery:
    def test_lists_all_tools(self, client):
        async def check():
            async with client:
                tools = await client.list_tools()
                names = {t.name for t in tools}
                assert names == {
                    "rf_link_budget",
                    "shannon_hartley",
                    "noise_floor",
                    "radar_range",
                    "antenna_gain",
                    "radar_ambiguity",
                }

        run_async(check())

    def test_tools_have_descriptions(self, client):
        async def check():
            async with client:
                tools = await client.list_tools()
                for tool in tools:
                    assert tool.description, f"{tool.name} has no description"

        run_async(check())


class TestMCPShannonHartley:
    def test_valid_capacity_query(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "shannon_hartley", {"bandwidth_hz": 20e6, "snr_db": 15.0}
                )
                assert not result.is_error
                data = json.loads(result.content[0].text)
                assert "capacity_bps" in data
                assert data["capacity_bps"] > 0
                assert "spectral_efficiency_bps_hz" in data

        run_async(check())

    def test_catches_impossible_throughput(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "shannon_hartley",
                    {
                        "bandwidth_hz": 20e6,
                        "snr_db": 15.0,
                        "claimed_throughput_bps": 500e6,
                    },
                )
                data = json.loads(result.content[0].text)
                assert data["error"] is True
                assert data["law_violated"] == "Shannon-Hartley Theorem"
                assert data["computed_limit"] < 500e6

        run_async(check())


class TestMCPLinkBudget:
    def test_valid_link_budget(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "rf_link_budget",
                    {
                        "tx_power_dbm": 20.0,
                        "tx_antenna_gain_dbi": 10.0,
                        "rx_antenna_gain_dbi": 3.0,
                        "frequency_hz": 2.4e9,
                        "distance_m": 100.0,
                    },
                )
                assert not result.is_error
                data = json.loads(result.content[0].text)
                assert "received_power_dbm" in data
                assert "fspl_db" in data
                assert "latex" in data

        run_async(check())

    def test_catches_impossible_antenna_gain(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "rf_link_budget",
                    {
                        "tx_power_dbm": 20.0,
                        "tx_antenna_gain_dbi": 45.0,
                        "rx_antenna_gain_dbi": 0.0,
                        "frequency_hz": 1e9,
                        "distance_m": 1000.0,
                        "tx_antenna_diameter_m": 0.3,
                    },
                )
                data = json.loads(result.content[0].text)
                assert data["error"] is True
                assert "Aperture" in data["law_violated"]
                # Hard limit is the Harrington bound (ka)^2 + 2ka, ka = 3.144 -> 12.1 dBi
                # (the eta = 1 aperture value (pi * 0.3 / 0.2998)^2 is 9.9 dBi)
                assert abs(data["computed_limit"] - 12.09) < 0.05

        run_async(check())

    def test_high_efficiency_gain_warns_but_passes(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "rf_link_budget",
                    {
                        "tx_power_dbm": 20.0,
                        "tx_antenna_gain_dbi": 39.0,
                        "rx_antenna_gain_dbi": 0.0,
                        "frequency_hz": 10e9,
                        "distance_m": 50000.0,
                        "tx_antenna_diameter_m": 1.0,
                    },
                )
                data = json.loads(result.content[0].text)
                assert "error" not in data
                assert data["tx_typical_aperture_gain_dbi"] < 39.0 < data["tx_aperture_limit_dbi"]
                assert data["tx_aperture_limit_dbi"] < data["tx_physical_limit_dbi"]
                assert data["tx_limiting_bound"] == "aperture"
                assert any("typical-efficiency" in w for w in data["warnings"])

        run_async(check())

    def test_dipole_in_small_footprint_passes(self, client):
        """2.15 dBi dipole, 0.1 m footprint at 900 MHz: valid under the Harrington bound."""

        async def check():
            async with client:
                result = await client.call_tool(
                    "rf_link_budget",
                    {
                        "tx_power_dbm": 20.0,
                        "tx_antenna_gain_dbi": 2.15,
                        "rx_antenna_gain_dbi": 0.0,
                        "frequency_hz": 900e6,
                        "distance_m": 1000.0,
                        "tx_antenna_diameter_m": 0.1,
                    },
                )
                data = json.loads(result.content[0].text)
                assert "error" not in data
                assert data["tx_limiting_bound"] == "harrington"
                assert abs(data["tx_physical_limit_dbi"] - 4.43) < 0.01
                assert abs(data["tx_aperture_limit_dbi"] - (-0.51)) < 0.01

        run_async(check())

    def test_negative_loss_rejected(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "rf_link_budget",
                    {
                        "tx_power_dbm": 20.0,
                        "tx_antenna_gain_dbi": 10.0,
                        "rx_antenna_gain_dbi": 3.0,
                        "frequency_hz": 2.4e9,
                        "distance_m": 100.0,
                        "tx_losses_db": -2.0,
                    },
                )
                data = json.loads(result.content[0].text)
                assert data["error"] is True
                assert "Conservation of Energy" in data["law_violated"]

        run_async(check())


class TestMCPNoiseFloor:
    def test_basic_noise_floor(self, client):
        async def check():
            async with client:
                result = await client.call_tool("noise_floor", {"bandwidth_hz": 1e6})
                assert not result.is_error
                data = json.loads(result.content[0].text)
                assert abs(data["thermal_noise_dbm"] - (-114.0)) < 0.1

        run_async(check())

    def test_cascaded_noise_with_sensitivity(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "noise_floor",
                    {
                        "bandwidth_hz": 10e6,
                        "stages": [
                            {"gain_db": 20.0, "noise_figure_db": 1.5},
                            {"gain_db": 10.0, "noise_figure_db": 8.0},
                        ],
                        "required_snr_db": 10.0,
                    },
                )
                assert not result.is_error
                data = json.loads(result.content[0].text)
                assert data["cascaded_noise_figure_db"] is not None
                assert data["receiver_sensitivity_dbm"] is not None
                assert data["cascaded_noise_figure_db"] < 2.0
                # T_e = 290 (F - 1) with F = 10^(NF/10)
                f_lin = 10 ** (data["cascaded_noise_figure_db"] / 10)
                assert abs(data["system_noise_temp_k"] - 290.0 * (f_lin - 1)) < 1e-6

        run_async(check())

    def test_system_noise_temp_independent_of_source_temperature(self, client):
        """T_e = T_0 (F - 1) is referenced to 290 K regardless of temperature_k."""

        async def check():
            async with client:
                stages = [{"gain_db": 20.0, "noise_figure_db": 3.0}]
                r290 = await client.call_tool(
                    "noise_floor", {"bandwidth_hz": 1e6, "stages": stages, "temperature_k": 290.0}
                )
                r77 = await client.call_tool(
                    "noise_floor", {"bandwidth_hz": 1e6, "stages": stages, "temperature_k": 77.0}
                )
                d290 = json.loads(r290.content[0].text)
                d77 = json.loads(r77.content[0].text)
                assert abs(d290["system_noise_temp_k"] - 288.6) < 0.1
                assert abs(d77["system_noise_temp_k"] - 288.6) < 0.1
                assert any("T_0" in w for w in d77["warnings"])
                assert not any("T_0" in w for w in d290["warnings"])

        run_async(check())


class TestMCPRadarRange:
    def test_valid_radar_range_query(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "radar_range",
                    {
                        "peak_power_w": 1000.0,
                        "antenna_gain_dbi": 30.0,
                        "frequency_hz": 10e9,
                        "rcs_m2": 1.0,
                    },
                )
                assert not result.is_error
                data = json.loads(result.content[0].text)
                assert "max_range_m" in data
                assert data["max_range_m"] > 0

        run_async(check())

    def test_catches_impossible_range_claim(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "radar_range",
                    {
                        "peak_power_w": 100.0,
                        "antenna_gain_dbi": 20.0,
                        "frequency_hz": 10e9,
                        "rcs_m2": 0.01,
                        "claimed_range_m": 1_000_000.0,
                    },
                )
                data = json.loads(result.content[0].text)
                assert data["error"] is True
                assert "Radar Range" in data["law_violated"]

        run_async(check())


class TestMCPAntennaGain:
    def test_valid_antenna_gain_query(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "antenna_gain", {"frequency_hz": 10e9, "diameter_m": 1.0}
                )
                assert not result.is_error
                data = json.loads(result.content[0].text)
                # 1 m dish at 10 GHz: (pi / 0.02998)^2 -> 40.4 dBi (eta = 1), 37.8 dBi (eta = 0.55);
                # Harrington (ka)^2 + 2ka -> 40.5 dBi
                assert abs(data["aperture_limit_dbi"] - 40.41) < 0.01
                assert abs(data["physical_limit_dbi"] - 40.49) < 0.01
                assert data["limiting_bound"] == "aperture"
                assert abs(data["typical_gain_dbi"] - 37.81) < 0.01
                assert abs(data["far_field_distance_m"] - 66.71) < 0.01
                assert abs(data["half_power_beamwidth_deg"] - 2.10) < 0.01
                assert data["claim_is_valid"] is None

        run_async(check())

    def test_catches_impossible_gain_claim(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "antenna_gain",
                    {"frequency_hz": 1e9, "diameter_m": 0.3, "claimed_gain_dbi": 45.0},
                )
                data = json.loads(result.content[0].text)
                assert data["error"] is True
                assert data["law_violated"] == "Antenna Aperture Limit"
                assert abs(data["computed_limit"] - 12.09) < 0.01

        run_async(check())

    def test_high_efficiency_claim_warns_but_passes(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "antenna_gain",
                    {
                        "frequency_hz": 10e9,
                        "aperture_area_m2": 0.7853981633974483,
                        "claimed_gain_dbi": 39.0,
                    },
                )
                data = json.loads(result.content[0].text)
                assert "error" not in data
                assert data["claim_is_valid"] is True
                assert data["typical_gain_dbi"] < 39.0 < data["physical_limit_dbi"]
                assert 0.55 < data["implied_efficiency"] < 1.0
                assert any("typical-efficiency" in w for w in data["warnings"])

        run_async(check())

    def test_exactly_one_size_enforced(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "antenna_gain",
                    {"frequency_hz": 10e9, "diameter_m": 1.0, "aperture_area_m2": 1.0},
                    raise_on_error=False,
                )
                assert result.is_error

        run_async(check())


class TestMCPRadarAmbiguity:
    def test_valid_ambiguity_query(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "radar_ambiguity",
                    {"frequency_hz": 10e9, "prf_hz": 1e3, "pulse_width_s": 1e-6},
                )
                assert not result.is_error
                data = json.loads(result.content[0].text)
                assert abs(data["max_unambiguous_range_km"] - 149.896) < 0.001
                assert abs(data["max_unambiguous_velocity_m_s"] - 7.495) < 0.001
                assert abs(data["range_resolution_m"] - 149.896) < 0.001
                assert abs(data["minimum_range_m"] - 149.896) < 0.001
                assert "latex" in data

        run_async(check())

    def test_catches_impossible_velocity_claim(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "radar_ambiguity",
                    {
                        "frequency_hz": 10e9,
                        "prf_hz": 10e3,
                        "claimed_unambiguous_velocity_m_s": 500.0,
                    },
                )
                data = json.loads(result.content[0].text)
                assert data["error"] is True
                assert data["law_violated"] == "Radar Doppler Ambiguity"
                assert abs(data["computed_limit"] - 74.95) < 0.05
                assert data["claimed_value"] == 500.0

        run_async(check())

    def test_aliased_target_reported(self, client):
        async def check():
            async with client:
                result = await client.call_tool(
                    "radar_ambiguity",
                    {"frequency_hz": 10e9, "prf_hz": 10e3, "target_velocity_m_s": 100.0},
                )
                data = json.loads(result.content[0].text)
                assert "error" not in data
                assert data["doppler_aliased"] is True
                assert abs(data["doppler_shift_hz"] - 6671.3) < 0.1
                assert any("aliased" in w for w in data["warnings"])

        run_async(check())
