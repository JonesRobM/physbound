"""Marketing test suite: Common LLM Hallucinations vs PhysBound Truths.

Each test case documents a real-world hallucination pattern and validates
that PhysBound correctly catches (or correctly computes) the truth.

Run with `pytest tests/test_marketing.py -s` to print the Markdown delta table.
"""

import math

import pytest

from physbound.engines.link_budget import compute_link_budget, free_space_path_loss_db
from physbound.engines.noise import thermal_noise_power_dbm
from physbound.engines.shannon import (
    channel_capacity_bps,
    snr_db_to_linear,
    validate_throughput_claim,
)
from physbound.errors import PhysicalViolationError

HALLUCINATION_CASES = [
    {
        "id": "wifi_500mbps_impossible",
        "hallucination": "A 20 MHz 802.11n channel with 15 dB SNR can achieve 500 Mbps",
        "truth": None,  # computed at test time
        "category": "Shannon-Hartley",
    },
    {
        "id": "5g_throughput_fantasy",
        "hallucination": "A 100 MHz 5G channel with 20 dB SNR delivers 2 Gbps",
        "truth": None,
        "category": "Shannon-Hartley",
    },
    {
        "id": "impossible_dish_gain",
        "hallucination": "A 30 cm dish antenna at 1 GHz provides 45 dBi gain",
        "truth": None,
        "category": "Antenna Aperture",
    },
    {
        "id": "noise_floor_minus_180",
        "hallucination": "Receiver noise floor of -180 dBm/Hz at room temperature",
        "truth": None,
        "category": "Thermal Noise",
    },
    {
        "id": "wifi_range_exaggeration",
        "hallucination": "Wi-Fi at 2.4 GHz with 20 dBm TX reaches 10 km with -40 dBm RX power",
        "truth": None,
        "category": "Link Budget / FSPL",
    },
    {
        "id": "satellite_link_fantasy",
        "hallucination": "A 1W transmitter at 12 GHz with 0 dBi antennas reaches GEO at -80 dBm",
        "truth": None,
        "category": "Link Budget / FSPL",
    },
]


class TestShannonHallucinations:
    def test_wifi_500mbps_impossible(self):
        """LLMs commonly claim 500 Mbps for 20 MHz 802.11n at modest SNR."""
        snr = snr_db_to_linear(15.0)
        capacity = channel_capacity_bps(20e6, snr)
        assert capacity < 500e6, "Shannon limit should be well below 500 Mbps"
        with pytest.raises(PhysicalViolationError, match="Shannon"):
            validate_throughput_claim(20e6, snr, 500e6)
        # Record truth
        HALLUCINATION_CASES[0]["truth"] = (
            f"Shannon limit: {capacity / 1e6:.1f} Mbps (not 500 Mbps)"
        )

    def test_5g_throughput_fantasy(self):
        """LLMs overestimate 5G single-carrier throughput."""
        snr = snr_db_to_linear(20.0)
        capacity = channel_capacity_bps(100e6, snr)
        assert capacity < 2e9, "Shannon limit should be below 2 Gbps"
        with pytest.raises(PhysicalViolationError, match="Shannon"):
            validate_throughput_claim(100e6, snr, 2e9)
        HALLUCINATION_CASES[1]["truth"] = (
            f"Shannon limit: {capacity / 1e6:.1f} Mbps (not 2000 Mbps)"
        )


class TestAntennaHallucinations:
    def test_impossible_dish_gain(self):
        """LLMs claim absurd gain for small dishes at low frequencies."""
        with pytest.raises(PhysicalViolationError, match="Aperture"):
            compute_link_budget(
                tx_power_dbm=20,
                tx_antenna_gain_dbi=45,
                rx_antenna_gain_dbi=0,
                frequency_hz=1e9,
                distance_m=1000,
                tx_antenna_diameter_m=0.3,
            )
        # G_max for 0.3m dish at 1 GHz
        from physbound.engines.link_budget import max_aperture_gain_dbi

        g_max = max_aperture_gain_dbi(0.3, 1e9)
        HALLUCINATION_CASES[2]["truth"] = (
            f"Max gain: {g_max:.1f} dBi for 0.3 m dish at 1 GHz (not 45 dBi)"
        )


class TestNoiseHallucinations:
    def test_noise_floor_minus_180(self):
        """LLMs sometimes quote -180 dBm/Hz at room temperature."""
        actual = thermal_noise_power_dbm(1.0, 290.0)
        assert actual > -175, "Noise floor at 290K must be > -175 dBm/Hz"
        assert actual < -173, "Noise floor at 290K must be < -173 dBm/Hz"
        HALLUCINATION_CASES[3]["truth"] = (
            f"Thermal noise floor: {actual:.1f} dBm/Hz at 290K (not -180 dBm/Hz)"
        )


class TestLinkBudgetHallucinations:
    def test_wifi_range_exaggeration(self):
        """LLMs overestimate Wi-Fi range by ignoring FSPL."""
        result = compute_link_budget(
            tx_power_dbm=20,
            tx_antenna_gain_dbi=3,
            rx_antenna_gain_dbi=3,
            frequency_hz=2.4e9,
            distance_m=10000,
        )
        prx = result["received_power_dbm"]
        assert prx < -40, "RX power at 10 km should be much weaker than -40 dBm"
        HALLUCINATION_CASES[4]["truth"] = (
            f"Actual RX power at 10 km: {prx:.1f} dBm (not -40 dBm)"
        )

    def test_satellite_link_fantasy(self):
        """LLMs underestimate GEO satellite path loss."""
        geo_distance = 35_786_000  # meters
        result = compute_link_budget(
            tx_power_dbm=30,  # 1W = 30 dBm
            tx_antenna_gain_dbi=0,
            rx_antenna_gain_dbi=0,
            frequency_hz=12e9,
            distance_m=geo_distance,
        )
        prx = result["received_power_dbm"]
        assert prx < -80, "0 dBi antennas to GEO at 12 GHz should be far below -80 dBm"
        HALLUCINATION_CASES[5]["truth"] = (
            f"Actual RX power at GEO: {prx:.1f} dBm (not -80 dBm)"
        )


def test_generate_markdown_table(capsys):
    """Generate the marketing delta table to stdout.

    Run with: pytest tests/test_marketing.py::test_generate_markdown_table -s
    """
    # Ensure truths are populated by running all tests first
    # (pytest runs them in order within this module)

    header = "| # | Category | LLM Hallucination | PhysBound Truth | Verdict |"
    separator = "|---|----------|-------------------|-----------------|---------|"
    rows = []

    for i, case in enumerate(HALLUCINATION_CASES, 1):
        truth = case["truth"] or "(run full suite to populate)"
        rows.append(
            f"| {i} | {case['category']} | {case['hallucination']} | {truth} | CAUGHT |"
        )

    table = "\n".join([header, separator, *rows])
    print(f"\n\n{'=' * 80}")
    print("PhysBound: LLM Hallucination Detection Results")
    print(f"{'=' * 80}\n")
    print(table)
    print(f"\n{'=' * 80}\n")
