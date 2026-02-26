"""MCP server integration tests — verify tool invocation and response shapes."""

from physbound.server import mcp


# Access the underlying functions through the MCP tool registry
def call_tool(name: str, **kwargs) -> dict:
    """Call an MCP tool's underlying function directly for testing."""
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    tool = tools[name]
    return tool.fn(**kwargs)


class TestRfLinkBudget:
    def test_basic_invocation(self):
        result = call_tool(
            "rf_link_budget",
            tx_power_dbm=20.0,
            tx_antenna_gain_dbi=10.0,
            rx_antenna_gain_dbi=3.0,
            frequency_hz=2.4e9,
            distance_m=100.0,
        )
        assert "fspl_db" in result
        assert "received_power_dbm" in result
        assert "human_readable" in result
        assert "latex" in result
        assert "error" not in result

    def test_aperture_violation_returns_error_dict(self):
        result = call_tool(
            "rf_link_budget",
            tx_power_dbm=20.0,
            tx_antenna_gain_dbi=45.0,
            rx_antenna_gain_dbi=0.0,
            frequency_hz=1e9,
            distance_m=1000.0,
            tx_antenna_diameter_m=0.3,
        )
        assert result["error"] is True
        assert result["violation_type"] == "PhysicalViolationError"
        assert "latex" in result
        assert "Aperture" in result["law_violated"]

    def test_with_losses(self):
        result = call_tool(
            "rf_link_budget",
            tx_power_dbm=30.0,
            tx_antenna_gain_dbi=15.0,
            rx_antenna_gain_dbi=12.0,
            frequency_hz=5.8e9,
            distance_m=5000.0,
            tx_losses_db=2.0,
            rx_losses_db=1.5,
        )
        assert "received_power_dbm" in result


class TestShannonHartley:
    def test_basic_capacity(self):
        result = call_tool("shannon_hartley", bandwidth_hz=20e6, snr_db=15.0)
        assert "capacity_bps" in result
        assert "spectral_efficiency_bps_hz" in result
        assert result["claim_is_valid"] is None

    def test_valid_claim(self):
        result = call_tool(
            "shannon_hartley", bandwidth_hz=20e6, snr_db=15.0, claimed_throughput_bps=50e6
        )
        assert result["claim_is_valid"] is True

    def test_impossible_claim_returns_error(self):
        result = call_tool(
            "shannon_hartley", bandwidth_hz=20e6, snr_db=15.0, claimed_throughput_bps=500e6
        )
        assert result["error"] is True
        assert "Shannon" in result["law_violated"]

    def test_snr_linear_input(self):
        result = call_tool("shannon_hartley", bandwidth_hz=1e6, snr_linear=10.0)
        assert "capacity_bps" in result


class TestNoiseFloor:
    def test_basic_noise_floor(self):
        result = call_tool("noise_floor", bandwidth_hz=1e6)
        assert "thermal_noise_dbm" in result
        assert "thermal_noise_watts" in result
        assert abs(result["thermal_noise_dbm"] - (-114.0)) < 0.1

    def test_with_stages(self):
        result = call_tool(
            "noise_floor",
            bandwidth_hz=1e6,
            stages=[
                {"gain_db": 20.0, "noise_figure_db": 1.0},
                {"gain_db": 0.0, "noise_figure_db": 10.0},
            ],
        )
        assert result["cascaded_noise_figure_db"] is not None
        assert result["cascaded_noise_figure_db"] < 2.0

    def test_with_sensitivity(self):
        result = call_tool("noise_floor", bandwidth_hz=1e6, required_snr_db=10.0)
        assert result["receiver_sensitivity_dbm"] is not None

    def test_custom_temperature(self):
        result = call_tool("noise_floor", bandwidth_hz=1e6, temperature_k=77.0)
        assert result["thermal_noise_dbm"] < -114.0


class TestRadarRange:
    def test_basic_invocation(self):
        result = call_tool(
            "radar_range",
            peak_power_w=1000.0,
            antenna_gain_dbi=30.0,
            frequency_hz=10e9,
            rcs_m2=1.0,
        )
        assert "max_range_m" in result
        assert "max_range_km" in result
        assert "wavelength_m" in result
        assert "human_readable" in result
        assert "latex" in result
        assert "error" not in result

    def test_claimed_range_violation_returns_error_dict(self):
        result = call_tool(
            "radar_range",
            peak_power_w=1000.0,
            antenna_gain_dbi=30.0,
            frequency_hz=10e9,
            rcs_m2=0.01,
            claimed_range_m=500_000.0,
        )
        assert result["error"] is True
        assert result["violation_type"] == "PhysicalViolationError"
        assert "Radar Range" in result["law_violated"]

    def test_with_losses_and_pulses(self):
        result = call_tool(
            "radar_range",
            peak_power_w=5000.0,
            antenna_gain_dbi=35.0,
            frequency_hz=3e9,
            rcs_m2=10.0,
            losses_db=3.0,
            num_pulses=10,
        )
        assert result["max_range_m"] > 0
        assert result["integration_gain"] == 10


class TestToolRegistration:
    def test_all_tools_registered(self):
        tool_names = {t.name for t in mcp._tool_manager._tools.values()}
        assert tool_names == {"rf_link_budget", "shannon_hartley", "noise_floor", "radar_range"}
