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
    def test_lists_all_three_tools(self, client):
        async def check():
            async with client:
                tools = await client.list_tools()
                names = {t.name for t in tools}
                assert names == {"rf_link_budget", "shannon_hartley", "noise_floor"}

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

        run_async(check())
