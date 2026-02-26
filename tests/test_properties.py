"""Property-based tests using Hypothesis.

Validates mathematical invariants that must hold for ALL valid inputs,
not just specific test vectors.
"""

import math

from hypothesis import assume, given
from hypothesis import strategies as st

from physbound.engines.link_budget import free_space_path_loss_db, max_aperture_gain_dbi
from physbound.engines.noise import thermal_noise_power_dbm
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
