"""Property-based tests using Hypothesis.

Validates mathematical invariants that must hold for ALL valid inputs,
not just specific test vectors.
"""

import math

from hypothesis import assume, given
from hypothesis import strategies as st

from physbound.engines.link_budget import free_space_path_loss_db, max_aperture_gain_dbi
from physbound.engines.noise import thermal_noise_power_dbm
from physbound.engines.radar import compute_radar_range
from physbound.engines.shannon import channel_capacity_bps, spectral_efficiency
from physbound.engines.units import db_to_linear, linear_to_db

# --- Strategy helpers ---
# Physically reasonable ranges to avoid overflow/underflow

positive_freq = st.floats(min_value=1e3, max_value=3e11)  # 1 kHz to 300 GHz
positive_dist = st.floats(min_value=0.01, max_value=1e10)  # 1 cm to 10 Gm
positive_bw = st.floats(min_value=1.0, max_value=1e10)  # 1 Hz to 10 GHz
positive_snr = st.floats(min_value=1e-6, max_value=1e10)  # near-zero to 100 dB
positive_temp = st.floats(min_value=1.0, max_value=1e6)  # 1 K to 1 MK
positive_linear = st.floats(min_value=1e-15, max_value=1e15)
db_values = st.floats(min_value=-150.0, max_value=150.0)
diameter = st.floats(min_value=0.01, max_value=100.0)  # 1 cm to 100 m
positive_power = st.floats(min_value=0.1, max_value=1e6)  # 0.1 W to 1 MW
positive_rcs = st.floats(min_value=1e-6, max_value=1e4)  # 1 mm^2 to 10000 m^2
gain_dbi = st.floats(min_value=0.0, max_value=60.0)  # 0 to 60 dBi
min_snr_db = st.floats(min_value=1.0, max_value=30.0)  # 1 to 30 dB


# --- dB / linear roundtrip ---


class TestDBConversionProperties:
    @given(x=positive_linear)
    def test_linear_to_db_roundtrip(self, x):
        """linear -> dB -> linear should recover the original value."""
        db = linear_to_db(x)
        recovered = db_to_linear(db)
        assert math.isclose(recovered, x, rel_tol=1e-9)

    @given(x=db_values)
    def test_db_to_linear_roundtrip(self, x):
        """dB -> linear -> dB should recover the original value."""
        linear = db_to_linear(x)
        recovered = linear_to_db(linear)
        assert math.isclose(recovered, x, abs_tol=1e-9)

    @given(x=positive_linear, y=positive_linear)
    def test_db_preserves_ordering(self, x, y):
        """dB conversion preserves ordering: if x > y then dB(x) > dB(y)."""
        assume(x > y * 1.001 or y > x * 1.001)  # require meaningful separation
        if x > y:
            assert linear_to_db(x) > linear_to_db(y)
        elif x < y:
            assert linear_to_db(x) < linear_to_db(y)

    @given(x=db_values)
    def test_db_to_linear_always_positive(self, x):
        """Linear values are always positive."""
        assert db_to_linear(x) > 0


# --- FSPL monotonicity ---


class TestFSPLProperties:
    @given(f=positive_freq, d1=positive_dist, d2=positive_dist)
    def test_fspl_increases_with_distance(self, f, d1, d2):
        """FSPL is monotonically increasing with distance at fixed frequency."""
        assume(d2 > d1 * 1.001)
        assert free_space_path_loss_db(f, d1) < free_space_path_loss_db(f, d2)

    @given(d=positive_dist, f1=positive_freq, f2=positive_freq)
    def test_fspl_increases_with_frequency(self, d, f1, f2):
        """FSPL is monotonically increasing with frequency at fixed distance."""
        assume(f2 > f1 * 1.001)
        assert free_space_path_loss_db(f1, d) < free_space_path_loss_db(f2, d)

    @given(f=positive_freq, d=positive_dist)
    def test_fspl_positive_in_far_field(self, f, d):
        """FSPL is positive when the link is in the far field (d > wavelength)."""
        wavelength = 299_792_458 / f
        assume(d > wavelength)
        assert free_space_path_loss_db(f, d) > 0

    @given(f=positive_freq, d=positive_dist)
    def test_fspl_doubles_distance_adds_6db(self, f, d):
        """Doubling distance adds ~6.02 dB to FSPL (inverse square law)."""
        d2 = d * 2
        if d2 <= 1e10:  # stay in range
            delta = free_space_path_loss_db(f, d2) - free_space_path_loss_db(f, d)
            assert math.isclose(delta, 20 * math.log10(2), rel_tol=1e-9)


# --- Shannon-Hartley monotonicity ---


class TestShannonProperties:
    @given(bw=positive_bw, snr1=positive_snr, snr2=positive_snr)
    def test_capacity_increases_with_snr(self, bw, snr1, snr2):
        """Shannon capacity increases with SNR at fixed bandwidth."""
        assume(snr2 > snr1 * 1.001)
        assert channel_capacity_bps(bw, snr1) < channel_capacity_bps(bw, snr2)

    @given(snr=positive_snr, bw1=positive_bw, bw2=positive_bw)
    def test_capacity_increases_with_bandwidth(self, snr, bw1, bw2):
        """Shannon capacity increases with bandwidth at fixed SNR."""
        assume(bw2 > bw1 * 1.001)
        assert channel_capacity_bps(bw1, snr) < channel_capacity_bps(bw2, snr)

    @given(bw=positive_bw, snr=positive_snr)
    def test_capacity_always_positive(self, bw, snr):
        """Channel capacity is always positive for positive SNR."""
        assert channel_capacity_bps(bw, snr) > 0

    @given(snr=positive_snr)
    def test_capacity_linear_in_bandwidth(self, snr):
        """Doubling bandwidth doubles capacity (C is linear in B)."""
        bw = 1e6
        c1 = channel_capacity_bps(bw, snr)
        c2 = channel_capacity_bps(bw * 2, snr)
        assert math.isclose(c2, c1 * 2, rel_tol=1e-9)

    @given(snr=positive_snr)
    def test_spectral_efficiency_independent_of_bandwidth(self, snr):
        """Spectral efficiency depends only on SNR, not bandwidth."""
        eta = spectral_efficiency(snr)
        c1 = channel_capacity_bps(1e6, snr) / 1e6
        assert math.isclose(eta, c1, rel_tol=1e-9)


# --- Thermal noise monotonicity ---


class TestNoiseProperties:
    @given(t=positive_temp, bw1=positive_bw, bw2=positive_bw)
    def test_noise_increases_with_bandwidth(self, t, bw1, bw2):
        """Thermal noise increases with bandwidth."""
        assume(bw2 > bw1 * 1.001)
        assert thermal_noise_power_dbm(bw1, t) < thermal_noise_power_dbm(bw2, t)

    @given(bw=positive_bw, t1=positive_temp, t2=positive_temp)
    def test_noise_increases_with_temperature(self, bw, t1, t2):
        """Thermal noise increases with temperature."""
        assume(t2 > t1 * 1.001)
        assert thermal_noise_power_dbm(bw, t1) < thermal_noise_power_dbm(bw, t2)

    @given(bw=positive_bw)
    def test_noise_at_290k_anchored(self, bw):
        """Noise at 290K scales from the -174 dBm/Hz reference."""
        n = thermal_noise_power_dbm(bw, 290.0)
        expected = -174.0 + 10 * math.log10(bw)
        assert math.isclose(n, expected, abs_tol=0.1)


# --- Aperture gain ---


class TestApertureProperties:
    @given(d=diameter, f1=positive_freq, f2=positive_freq)
    def test_gain_increases_with_frequency(self, d, f1, f2):
        """Aperture gain increases with frequency (shorter wavelength)."""
        assume(f2 > f1 * 1.001)  # require meaningful separation
        assert max_aperture_gain_dbi(d, f1) < max_aperture_gain_dbi(d, f2)

    @given(f=positive_freq, d1=diameter, d2=diameter)
    def test_gain_increases_with_diameter(self, f, d1, d2):
        """Aperture gain increases with antenna diameter."""
        assume(d2 > d1 * 1.001)  # require meaningful separation to avoid FP equality
        assert max_aperture_gain_dbi(d1, f) < max_aperture_gain_dbi(d2, f)

    @given(d=diameter, f=positive_freq)
    def test_doubling_diameter_adds_6db(self, d, f):
        """Doubling antenna diameter adds ~6.02 dB gain (area scales as D^2)."""
        d2 = d * 2
        if d2 <= 100:
            delta = max_aperture_gain_dbi(d2, f) - max_aperture_gain_dbi(d, f)
            assert math.isclose(delta, 20 * math.log10(2), rel_tol=1e-9)


# --- Radar range monotonicity ---


class TestRadarRangeProperties:
    @given(p1=positive_power, p2=positive_power)
    def test_range_increases_with_power(self, p1, p2):
        """R_max increases monotonically with peak power (R ~ P^(1/4))."""
        assume(p2 > p1 * 1.01)
        r1 = compute_radar_range(p1, 30.0, 10e9, 1.0)
        r2 = compute_radar_range(p2, 30.0, 10e9, 1.0)
        assert r1["max_range_m"] < r2["max_range_m"]

    @given(g1=gain_dbi, g2=gain_dbi)
    def test_range_increases_with_gain(self, g1, g2):
        """R_max increases monotonically with antenna gain (R ~ G^(1/2))."""
        assume(g2 > g1 + 0.5)
        r1 = compute_radar_range(1000.0, g1, 10e9, 1.0)
        r2 = compute_radar_range(1000.0, g2, 10e9, 1.0)
        assert r1["max_range_m"] < r2["max_range_m"]

    @given(s1=positive_rcs, s2=positive_rcs)
    def test_range_increases_with_rcs(self, s1, s2):
        """R_max increases monotonically with RCS (R ~ sigma^(1/4))."""
        assume(s2 > s1 * 1.01)
        r1 = compute_radar_range(1000.0, 30.0, 10e9, s1)
        r2 = compute_radar_range(1000.0, 30.0, 10e9, s2)
        assert r1["max_range_m"] < r2["max_range_m"]

    @given(f1=positive_freq, f2=positive_freq)
    def test_range_decreases_with_frequency(self, f1, f2):
        """R_max decreases with frequency (R ~ lambda^(1/2) = (c/f)^(1/2))."""
        assume(f2 > f1 * 1.01)
        r1 = compute_radar_range(1000.0, 30.0, f1, 1.0)
        r2 = compute_radar_range(1000.0, 30.0, f2, 1.0)
        assert r1["max_range_m"] > r2["max_range_m"]

    @given(t1=positive_temp, t2=positive_temp)
    def test_range_decreases_with_temperature(self, t1, t2):
        """R_max decreases with system noise temperature."""
        assume(t2 > t1 * 1.01)
        r1 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, system_noise_temp_k=t1)
        r2 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, system_noise_temp_k=t2)
        assert r1["max_range_m"] > r2["max_range_m"]

    @given(snr1=min_snr_db, snr2=min_snr_db)
    def test_range_decreases_with_min_snr(self, snr1, snr2):
        """R_max decreases with increasing minimum SNR requirement."""
        assume(snr2 > snr1 + 0.5)
        r1 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, min_snr_db=snr1)
        r2 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, min_snr_db=snr2)
        assert r1["max_range_m"] > r2["max_range_m"]

    @given(p=positive_power)
    def test_fourth_root_scaling(self, p):
        """Doubling power increases range by exactly 2^(1/4)."""
        assume(p * 2 <= 1e6)
        r1 = compute_radar_range(p, 30.0, 10e9, 1.0)
        r2 = compute_radar_range(p * 2, 30.0, 10e9, 1.0)
        ratio = r2["max_range_m"] / r1["max_range_m"]
        assert math.isclose(ratio, 2**0.25, rel_tol=1e-9)
