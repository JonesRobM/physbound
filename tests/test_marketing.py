"""Marketing test suite: Common LLM Hallucinations vs PhysBound Truths.

Each test case documents a real-world hallucination pattern and validates
that PhysBound correctly catches (or correctly computes) the truth.

Run with `pytest tests/test_marketing.py -s` to print the Markdown delta table.
"""

import pytest

from physbound.engines.link_budget import (
    compute_link_budget,
    max_aperture_gain_dbi,
    physical_aperture_gain_limit_dbi,
    physical_gain_limit_dbi,
)
from physbound.engines.noise import (
    friis_noise_cascade,
    thermal_noise_power_dbm,
)
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
    {
        "id": "bluetooth_1km_range",
        "hallucination": (
            "Bluetooth at 2.4 GHz with 0 dBm TX and 0 dBi antennas reaches 1 km at -60 dBm"
        ),
        "truth": None,
        "category": "Link Budget / FSPL",
    },
    {
        "id": "lte_narrowband_gigabit",
        "hallucination": "A 10 MHz LTE channel at 10 dB SNR supports 1 Gbps",
        "truth": None,
        "category": "Shannon-Hartley",
    },
    {
        "id": "cascade_order_irrelevant",
        "hallucination": (
            "Receiver NF is the same regardless of stage order: LNA(20dB/1.5dB) + Mixer(10dB/8dB)"
        ),
        "truth": None,
        "category": "Noise Cascade",
    },
    {
        "id": "small_antenna_uhf",
        "hallucination": "A 10 cm patch antenna at 900 MHz provides 20 dBi gain",
        "truth": None,
        "category": "Antenna Aperture",
    },
    {
        "id": "radar_double_power_double_range",
        "hallucination": "Doubling transmit power doubles radar detection range",
        "truth": None,
        "category": "Radar Range Equation",
    },
    {
        "id": "drone_200km_xband",
        "hallucination": (
            "Small drone (0.01 m^2 RCS) detectable at 200 km by 1 kW X-band radar with 30 dBi gain"
        ),
        "truth": None,
        "category": "Radar Range Equation",
    },
    {
        "id": "starlink_dish_50dbi",
        "hallucination": "A 0.5 m user-terminal dish at 12 GHz gives 50 dBi gain",
        "truth": None,
        "category": "Antenna Gain",
    },
    {
        "id": "wifi_router_antenna_far_field",
        "hallucination": (
            "A 3 m dish at 10 GHz is in its far field at 10 m, so gain can be measured there"
        ),
        "truth": None,
        "category": "Antenna Gain",
    },
    {
        "id": "pulse_doppler_500ms_at_10khz",
        "hallucination": "A 10 GHz radar at 10 kHz PRF unambiguously measures 500 m/s",
        "truth": None,
        "category": "Radar Ambiguity",
    },
    {
        "id": "pulse_doppler_range_and_velocity_free_lunch",
        "hallucination": (
            "A 10 GHz pulse-Doppler radar can unambiguously cover 150 km and +/-300 m/s at once"
        ),
        "truth": None,
        "category": "Radar Ambiguity",
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
        HALLUCINATION_CASES[0]["truth"] = f"Shannon limit: {capacity / 1e6:.1f} Mbps (not 500 Mbps)"

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
        # Hard limit = max(eta = 1 aperture, Harrington (ka)^2 + 2ka) for 0.3 m at 1 GHz
        g_phys = physical_gain_limit_dbi(0.3, 1e9)
        g_ap = physical_aperture_gain_limit_dbi(0.3, 1e9)
        g_typ = max_aperture_gain_dbi(0.3, 1e9)
        assert abs(g_phys - 12.1) < 0.05
        assert abs(g_ap - 9.9) < 0.05
        assert abs(g_typ - 7.4) < 0.05
        HALLUCINATION_CASES[2]["truth"] = (
            f"Physical limit: {g_phys:.1f} dBi (Harrington); aperture eta=1: {g_ap:.1f} dBi; "
            f"typical dish: {g_typ:.1f} dBi (eta=0.55) (not 45 dBi)"
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
        HALLUCINATION_CASES[4]["truth"] = f"Actual RX power at 10 km: {prx:.1f} dBm (not -40 dBm)"

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
        HALLUCINATION_CASES[5]["truth"] = f"Actual RX power at GEO: {prx:.1f} dBm (not -80 dBm)"


class TestLinkBudgetHallucinations2:
    def test_bluetooth_1km_range(self):
        """LLMs overestimate Bluetooth range (Class 2: 0 dBm / 1 mW)."""
        result = compute_link_budget(
            tx_power_dbm=0,  # 1 mW = 0 dBm (Bluetooth Class 2)
            tx_antenna_gain_dbi=0,
            rx_antenna_gain_dbi=0,
            frequency_hz=2.4e9,
            distance_m=1000,
        )
        prx = result["received_power_dbm"]
        assert prx < -60, "Bluetooth at 1 km should be well below -60 dBm"
        HALLUCINATION_CASES[6]["truth"] = f"Actual RX power at 1 km: {prx:.1f} dBm (not -60 dBm)"


class TestShannonHallucinations2:
    def test_lte_narrowband_gigabit(self):
        """LLMs claim gigabit speeds on narrow LTE channels."""
        snr = snr_db_to_linear(10.0)
        capacity = channel_capacity_bps(10e6, snr)
        assert capacity < 1e9, "10 MHz at 10 dB SNR cannot reach 1 Gbps"
        with pytest.raises(PhysicalViolationError, match="Shannon"):
            validate_throughput_claim(10e6, snr, 1e9)
        HALLUCINATION_CASES[7]["truth"] = (
            f"Shannon limit: {capacity / 1e6:.1f} Mbps (not 1000 Mbps)"
        )


class TestNoiseCascadeHallucinations:
    def test_cascade_order_matters(self):
        """LLMs claim stage order doesn't affect system noise figure."""
        # Good order: LNA first
        nf_good = friis_noise_cascade([(20.0, 1.5), (10.0, 8.0)])
        # Bad order: mixer first
        nf_bad = friis_noise_cascade([(10.0, 8.0), (20.0, 1.5)])
        # The difference is substantial
        penalty = nf_bad - nf_good
        assert penalty > 5, "Swapping LNA/mixer order should degrade NF by >5 dB"
        HALLUCINATION_CASES[8]["truth"] = (
            f"LNA first: {nf_good:.2f} dB vs mixer first: {nf_bad:.2f} dB "
            f"(penalty: {penalty:.1f} dB)"
        )


class TestAntennaHallucinations2:
    def test_small_antenna_uhf(self):
        """LLMs overestimate gain for small antennas at low frequencies."""
        with pytest.raises(PhysicalViolationError, match="Aperture"):
            compute_link_budget(
                tx_power_dbm=20,
                tx_antenna_gain_dbi=20,
                rx_antenna_gain_dbi=0,
                frequency_hz=900e6,
                distance_m=1000,
                tx_antenna_diameter_m=0.1,
            )
        # D = 0.1 m < lambda = 0.333 m: the Harrington bound (ka)^2 + 2ka governs
        g_phys = physical_gain_limit_dbi(0.1, 900e6)
        g_ap = physical_aperture_gain_limit_dbi(0.1, 900e6)
        g_typ = max_aperture_gain_dbi(0.1, 900e6)
        assert abs(g_phys - 4.4) < 0.05
        assert abs(g_ap - (-0.5)) < 0.05
        assert abs(g_typ - (-3.1)) < 0.05
        # a real half-wave dipole (2.15 dBi) in the same footprint is NOT a violation
        ok = compute_link_budget(20, 2.15, 0, 900e6, 1000, tx_antenna_diameter_m=0.1)
        assert ok["tx_limiting_bound"] == "harrington"
        HALLUCINATION_CASES[9]["truth"] = (
            f"Physical limit: {g_phys:.1f} dBi (Harrington, D < lambda); aperture eta=1: "
            f"{g_ap:.1f} dBi; typical: {g_typ:.1f} dBi (eta=0.55) (not 20 dBi)"
        )


class TestRadarRangeHallucinations:
    def test_double_power_double_range(self):
        """LLMs commonly claim doubling power doubles radar range.

        Due to R^4 dependence, doubling P only increases R by 2^(1/4) = 1.189x.
        """
        from physbound.engines.radar import compute_radar_range

        r1 = compute_radar_range(1000, 30, 10e9, 1.0)
        r2 = compute_radar_range(2000, 30, 10e9, 1.0)
        ratio = r2["max_range_m"] / r1["max_range_m"]
        assert abs(ratio - 2.0) > 0.5, "Range ratio should NOT be 2.0"
        assert abs(ratio - 2**0.25) < 0.01, "Range ratio should be 2^(1/4)"
        HALLUCINATION_CASES[10]["truth"] = (
            f"Range increases by factor {ratio:.3f} (2^(1/4) = {2**0.25:.3f}), not 2.0"
        )

    def test_drone_200km_xband(self):
        """LLMs overestimate radar detection range for small RCS targets."""
        from physbound.engines.radar import compute_radar_range

        result = compute_radar_range(
            peak_power_w=1000,
            antenna_gain_dbi=30,
            frequency_hz=10e9,
            rcs_m2=0.01,
        )
        r_max_km = result["max_range_km"]
        assert r_max_km < 200, "1 kW X-band cannot detect drone at 200 km"
        with pytest.raises(PhysicalViolationError, match="Radar Range"):
            compute_radar_range(
                peak_power_w=1000,
                antenna_gain_dbi=30,
                frequency_hz=10e9,
                rcs_m2=0.01,
                claimed_range_m=200_000,
            )
        HALLUCINATION_CASES[11]["truth"] = (
            f"Max range: {r_max_km:.1f} km for 0.01 m^2 RCS at 1 kW X-band (not 200 km)"
        )


class TestAntennaGainToolHallucinations:
    def test_starlink_dish_50dbi(self):
        """LLMs quote gain figures far above what a 0.5 m aperture can deliver at Ku-band."""
        from physbound.engines.antenna import compute_antenna_gain

        with pytest.raises(PhysicalViolationError, match="Aperture"):
            compute_antenna_gain(frequency_hz=12e9, diameter_m=0.5, claimed_gain_dbi=50.0)
        r = compute_antenna_gain(frequency_hz=12e9, diameter_m=0.5)
        # (pi * 0.5 / 0.02498)^2 -> 36.0 dBi at eta = 1; Harrington 36.1 dBi; 33.4 dBi at eta = 0.55
        assert abs(r["aperture_limit_dbi"] - 36.0) < 0.05
        assert abs(r["physical_limit_dbi"] - 36.1) < 0.05
        assert abs(r["typical_gain_dbi"] - 33.4) < 0.05
        HALLUCINATION_CASES[12]["truth"] = (
            f"Physical limit: {r['physical_limit_dbi']:.1f} dBi (Harrington); typical dish: "
            f"{r['typical_gain_dbi']:.1f} dBi (eta=0.55) (not 50 dBi)"
        )

    def test_far_field_distance_underestimated(self):
        """LLMs ignore the 2D^2/lambda Fraunhofer distance for large apertures."""
        from physbound.engines.antenna import compute_antenna_gain

        r = compute_antenna_gain(frequency_hz=10e9, diameter_m=3.0)
        r_ff = r["far_field_distance_m"]
        # 2 * 9 / 0.02998 = 600 m
        assert abs(r_ff - 600.4) < 0.5
        assert r_ff > 10.0, "10 m is deep inside the near field of a 3 m dish at 10 GHz"
        HALLUCINATION_CASES[13]["truth"] = (
            f"Far-field distance 2D^2/lambda = {r_ff:.0f} m; 10 m is in the near field"
        )


class TestRadarAmbiguityHallucinations:
    def test_pulse_doppler_500ms_at_10khz(self):
        """LLMs quote velocity coverage far beyond +/-lambda*PRF/4 for a given PRF."""
        from physbound.engines.doppler import compute_radar_ambiguity

        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=10e3)
        v_ua = r["max_unambiguous_velocity_m_s"]
        # lambda = 2.998 cm, PRF 10 kHz -> v_ua = 74.9 m/s, first blind speed 149.9 m/s
        assert abs(v_ua - 74.95) < 0.05
        with pytest.raises(PhysicalViolationError, match="Doppler Ambiguity"):
            compute_radar_ambiguity(
                frequency_hz=10e9, prf_hz=10e3, claimed_unambiguous_velocity_m_s=500.0
            )
        HALLUCINATION_CASES[14]["truth"] = (
            f"v_ua = lambda*PRF/4 = +/-{v_ua:.1f} m/s (blind speed "
            f"{r['first_blind_speed_m_s']:.1f} m/s); 500 m/s aliases (not 500 m/s)"
        )

    def test_range_and_velocity_free_lunch(self):
        """LLMs ignore the range-Doppler dilemma: R_ua * v_ua = c*lambda/8 for any PRF."""
        from physbound.engines.doppler import compute_radar_ambiguity

        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3)
        invariant = r["range_velocity_product_m2_s"]
        claimed_product = 150_000.0 * 300.0
        assert claimed_product > invariant * 10, "claim exceeds the invariant by > 10x"
        with pytest.raises(PhysicalViolationError, match="Range-Doppler Dilemma"):
            compute_radar_ambiguity(
                frequency_hz=10e9,
                prf_hz=1e3,
                claimed_unambiguous_range_m=150_000.0,
                claimed_unambiguous_velocity_m_s=300.0,
            )
        HALLUCINATION_CASES[15]["truth"] = (
            f"R_ua*v_ua = c*lambda/8 = {invariant:.3e} m^2/s for any PRF; "
            f"claimed {claimed_product:.1e} m^2/s ({claimed_product / invariant:.0f}x too large)"
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
        rows.append(f"| {i} | {case['category']} | {case['hallucination']} | {truth} | CAUGHT |")

    table = "\n".join([header, separator, *rows])
    print(f"\n\n{'=' * 80}")
    print("PhysBound: LLM Hallucination Detection Results")
    print(f"{'=' * 80}\n")
    print(table)
    print(f"\n{'=' * 80}\n")
