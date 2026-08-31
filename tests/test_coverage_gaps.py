"""Tests targeting previously uncovered branches.

Covers:
- non-positive antenna diameter in ``max_aperture_gain_dbi``
- the >300 GHz atmospheric-absorption warning in ``compute_link_budget``
- both ``ValueError`` branches of ``ShannonInput.exactly_one_snr``
- ``physbound.server.main`` running the MCP server over stdio
"""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from physbound.engines.link_budget import compute_link_budget, max_aperture_gain_dbi
from physbound.errors import PhysicalViolationError
from physbound.models.shannon import ShannonInput
from physbound.server import main


class TestApertureGainDiameter:
    @pytest.mark.parametrize("diameter_m", [0.0, -1.0, -1e-9])
    def test_non_positive_diameter_raises(self, diameter_m: float) -> None:
        with pytest.raises(PhysicalViolationError) as exc_info:
            max_aperture_gain_dbi(diameter_m=diameter_m, frequency_hz=10e9)
        err = exc_info.value
        assert err.law_violated == "Antenna Theory"
        assert err.claimed_value == diameter_m
        assert err.unit == "m"
        assert "must be positive" in err.message

    def test_positive_diameter_does_not_raise(self) -> None:
        gain = max_aperture_gain_dbi(diameter_m=1.0, frequency_hz=10e9)
        assert gain > 0


class TestLinkBudgetHighFrequencyWarning:
    def test_above_300ghz_emits_atmospheric_warning(self) -> None:
        result = compute_link_budget(
            tx_power_dbm=20.0,
            tx_antenna_gain_dbi=30.0,
            rx_antenna_gain_dbi=30.0,
            frequency_hz=400e9,
            distance_m=100.0,
        )
        assert len(result["warnings"]) == 1
        warning = result["warnings"][0]
        assert "exceeds 300 GHz" in warning
        assert "atmospheric absorption" in warning
        assert "400.0 GHz" in warning

    def test_at_or_below_300ghz_no_warning(self) -> None:
        result = compute_link_budget(
            tx_power_dbm=20.0,
            tx_antenna_gain_dbi=30.0,
            rx_antenna_gain_dbi=30.0,
            frequency_hz=3e11,
            distance_m=100.0,
        )
        assert result["warnings"] == []


class TestShannonInputSnrValidation:
    def test_neither_snr_raises(self) -> None:
        with pytest.raises(ValidationError, match="Exactly one of snr_linear or snr_db"):
            ShannonInput(bandwidth_hz=1e6)

    def test_both_snr_raises(self) -> None:
        with pytest.raises(ValidationError, match="Provide only one of snr_linear or snr_db"):
            ShannonInput(bandwidth_hz=1e6, snr_db=10.0, snr_linear=10.0)

    @pytest.mark.parametrize("kwargs", [{"snr_db": 10.0}, {"snr_linear": 10.0}])
    def test_exactly_one_snr_accepted(self, kwargs: dict) -> None:
        model = ShannonInput(bandwidth_hz=1e6, **kwargs)
        assert model.bandwidth_hz == 1e6


class TestServerMain:
    def test_main_runs_stdio_transport(self) -> None:
        with patch("physbound.server.mcp.run") as mock_run:
            main()
        mock_run.assert_called_once_with(transport="stdio")
