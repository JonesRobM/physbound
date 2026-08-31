"""Tests for pulse-Doppler radar ambiguity limits (engines/doppler.py)."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from physbound.engines.constants import SPEED_OF_LIGHT
from physbound.engines.doppler import (
    compute_radar_ambiguity,
    doppler_shift_hz,
    first_blind_speed_m_s,
    max_unambiguous_range_m,
    max_unambiguous_velocity_m_s,
    range_resolution_m,
)
from physbound.errors import PhysicalViolationError
from physbound.validators import validate_positive_prf, validate_positive_pulse_width

C = SPEED_OF_LIGHT.magnitude
REL_TOL = 1e-9


class TestReferenceValues:
    """Textbook reference numbers (Skolnik Ch. 2; Richards FRSP Ch. 1, 3)."""

    def test_xband_1khz_unambiguous_range(self):
        """10 GHz, PRF 1 kHz -> R_ua = c/2000 = 149.9 km."""
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3)
        assert math.isclose(r["max_unambiguous_range_m"], 149_896.229, rel_tol=1e-6)
        assert math.isclose(r["max_unambiguous_range_km"], 149.896229, rel_tol=1e-6)

    def test_xband_1khz_unambiguous_velocity(self):
        """10 GHz, PRF 1 kHz -> lambda = 2.998 cm, v_ua = lambda*PRF/4 = 7.49 m/s."""
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3)
        assert math.isclose(r["wavelength_m"], 0.0299792458, rel_tol=1e-9)
        assert math.isclose(r["max_unambiguous_velocity_m_s"], 7.4948, rel_tol=1e-4)
        assert math.isclose(r["first_blind_speed_m_s"], 14.9896, rel_tol=1e-4)
        assert math.isclose(r["max_unambiguous_doppler_hz"], 500.0, rel_tol=REL_TOL)

    def test_xband_100khz_unambiguous_range(self):
        """PRF 100 kHz -> R_ua = 1.5 km."""
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=100e3)
        assert math.isclose(r["max_unambiguous_range_m"], 1_498.96, rel_tol=1e-5)

    def test_xband_10khz_unambiguous_velocity(self):
        """PRF 10 kHz -> v_ua = 74.9 m/s, R_ua = 15 km."""
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=10e3)
        assert math.isclose(r["max_unambiguous_velocity_m_s"], 74.948, rel_tol=1e-4)
        assert math.isclose(r["max_unambiguous_range_km"], 14.9896, rel_tol=1e-5)

    def test_doppler_shift_reference(self):
        """f_d = 2 v / lambda: 300 m/s at 10 GHz -> 20.01 kHz (Skolnik Ch. 3)."""
        f_d = doppler_shift_hz(10e9, 300.0)
        assert math.isclose(f_d, 2 * 300.0 / (C / 10e9), rel_tol=REL_TOL)
        assert math.isclose(f_d, 20_013.85, rel_tol=1e-5)

    def test_doppler_sign_convention(self):
        """Closing target positive, receding negative."""
        assert doppler_shift_hz(10e9, 100.0) > 0
        assert doppler_shift_hz(10e9, -100.0) < 0
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=100e3, target_velocity_m_s=-50.0)
        assert r["doppler_shift_hz"] < 0

    def test_range_resolution_unmodulated_pulse(self):
        """1 us pulse -> dR = c*tau/2 = 149.9 m; also sets minimum range."""
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3, pulse_width_s=1e-6)
        assert math.isclose(r["range_resolution_m"], 149.896229, rel_tol=1e-6)
        assert math.isclose(r["minimum_range_m"], 149.896229, rel_tol=1e-6)
        assert math.isclose(r["duty_cycle"], 1e-3, rel_tol=REL_TOL)

    def test_range_resolution_pulse_compression(self):
        """B = 10 MHz -> dR = c/(2B) = 14.99 m regardless of pulse width."""
        r = compute_radar_ambiguity(
            frequency_hz=10e9, prf_hz=1e3, pulse_width_s=10e-6, bandwidth_hz=10e6
        )
        assert math.isclose(r["range_resolution_m"], C / 20e6, rel_tol=REL_TOL)
        # Minimum range is still governed by the physical pulse width
        assert math.isclose(r["minimum_range_m"], C * 10e-6 / 2, rel_tol=REL_TOL)
        assert any("Pulse compression" in w for w in r["warnings"])

    def test_range_doppler_invariant(self):
        """R_ua * v_ua = c*lambda/8 independent of PRF."""
        lam = C / 10e9
        for prf in (1e3, 5e3, 20e3, 100e3):
            r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=prf)
            assert math.isclose(r["range_velocity_product_m2_s"], C * lam / 8, rel_tol=REL_TOL)
            assert math.isclose(
                r["max_unambiguous_range_m"] * r["max_unambiguous_velocity_m_s"],
                C * lam / 8,
                rel_tol=REL_TOL,
            )

    def test_helper_functions_agree_with_engine(self):
        r = compute_radar_ambiguity(frequency_hz=3e9, prf_hz=2e3)
        assert math.isclose(max_unambiguous_range_m(2e3), r["max_unambiguous_range_m"])
        assert math.isclose(
            max_unambiguous_velocity_m_s(3e9, 2e3), r["max_unambiguous_velocity_m_s"]
        )
        assert math.isclose(first_blind_speed_m_s(3e9, 2e3), r["first_blind_speed_m_s"])
        assert math.isclose(range_resolution_m(pulse_width_s=2e-6), C * 1e-6)
        assert math.isclose(range_resolution_m(bandwidth_hz=1e6), C / 2e6)

    def test_range_resolution_helper_requires_argument(self):
        with pytest.raises(ValueError):
            range_resolution_m()


class TestAliasing:
    def test_unaliased_target(self):
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=10e3, target_velocity_m_s=50.0)
        assert r["doppler_aliased"] is False
        assert math.isclose(r["apparent_velocity_m_s"], 50.0, rel_tol=REL_TOL)
        assert not any("aliased" in w for w in r["warnings"])

    def test_aliased_target_folds(self):
        """v = 100 m/s at 10 GHz, PRF 10 kHz: v_ua = 74.9, blind = 149.9 -> apparent -49.9."""
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=10e3, target_velocity_m_s=100.0)
        assert r["doppler_aliased"] is True
        assert r["doppler_shift_hz"] > r["max_unambiguous_doppler_hz"]
        expected = 100.0 - r["first_blind_speed_m_s"]
        assert math.isclose(r["apparent_velocity_m_s"], expected, rel_tol=1e-9)
        assert any("aliased" in w for w in r["warnings"])

    def test_blind_speed_warning(self):
        blind = first_blind_speed_m_s(10e9, 10e3)
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=10e3, target_velocity_m_s=blind)
        assert any("blind speed" in w for w in r["warnings"])
        # Exactly at blind speed: Doppler == PRF, folds to zero apparent velocity
        assert abs(r["apparent_velocity_m_s"]) < 1e-9

    def test_target_at_exactly_v_ua_is_not_aliased(self):
        v_ua = max_unambiguous_velocity_m_s(10e9, 10e3)
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=10e3, target_velocity_m_s=v_ua)
        assert r["doppler_aliased"] is False

    def test_zero_velocity(self):
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=10e3, target_velocity_m_s=0.0)
        assert r["doppler_shift_hz"] == 0.0
        assert r["doppler_aliased"] is False


class TestViolations:
    def test_claimed_range_exceeds_r_ua(self):
        with pytest.raises(PhysicalViolationError, match="Range Ambiguity") as exc:
            compute_radar_ambiguity(
                frequency_hz=10e9, prf_hz=10e3, claimed_unambiguous_range_m=100_000.0
            )
        assert math.isclose(exc.value.computed_limit, C / 20e3, rel_tol=REL_TOL)
        assert exc.value.claimed_value == 100_000.0
        assert exc.value.unit == "m"

    def test_claimed_range_at_limit_passes(self):
        r_ua = max_unambiguous_range_m(10e3)
        r = compute_radar_ambiguity(
            frequency_hz=10e9, prf_hz=10e3, claimed_unambiguous_range_m=r_ua
        )
        assert "error" not in r

    def test_claimed_velocity_exceeds_v_ua(self):
        """10 GHz at 10 kHz PRF cannot unambiguously measure 500 m/s (v_ua = 75 m/s)."""
        with pytest.raises(PhysicalViolationError, match="Doppler Ambiguity") as exc:
            compute_radar_ambiguity(
                frequency_hz=10e9, prf_hz=10e3, claimed_unambiguous_velocity_m_s=500.0
            )
        assert math.isclose(exc.value.computed_limit, 74.948, rel_tol=1e-4)
        assert exc.value.unit == "m/s"

    def test_claimed_velocity_uses_magnitude(self):
        with pytest.raises(PhysicalViolationError, match="Doppler Ambiguity"):
            compute_radar_ambiguity(
                frequency_hz=10e9, prf_hz=10e3, claimed_unambiguous_velocity_m_s=-500.0
            )

    def test_joint_claim_violates_range_doppler_dilemma(self):
        """Each claim alone might be satisfiable at some PRF, but not at once."""
        with pytest.raises(PhysicalViolationError, match="Range-Doppler Dilemma") as exc:
            compute_radar_ambiguity(
                frequency_hz=10e9,
                prf_hz=10e3,
                claimed_unambiguous_range_m=100_000.0,
                claimed_unambiguous_velocity_m_s=500.0,
            )
        lam = C / 10e9
        assert math.isclose(exc.value.computed_limit, C * lam / 8, rel_tol=REL_TOL)
        assert exc.value.unit == "m^2/s"

    def test_joint_claim_within_invariant_but_range_too_large(self):
        """Product OK, but the range alone exceeds R_ua at this PRF -> range violation."""
        with pytest.raises(PhysicalViolationError, match="Range Ambiguity"):
            compute_radar_ambiguity(
                frequency_hz=10e9,
                prf_hz=10e3,
                claimed_unambiguous_range_m=20_000.0,
                claimed_unambiguous_velocity_m_s=1.0,
            )

    def test_claimed_resolution_finer_than_unmodulated_pulse(self):
        with pytest.raises(PhysicalViolationError, match="Range Resolution") as exc:
            compute_radar_ambiguity(
                frequency_hz=10e9, prf_hz=1e3, pulse_width_s=1e-6, claimed_range_resolution_m=10.0
            )
        assert "pulse compression" in exc.value.message
        assert math.isclose(exc.value.computed_limit, C * 1e-6 / 2, rel_tol=REL_TOL)

    def test_claimed_resolution_ok_with_pulse_compression(self):
        """Same 1 us pulse, but 50 MHz chirp -> 3 m resolution is legitimate."""
        r = compute_radar_ambiguity(
            frequency_hz=10e9,
            prf_hz=1e3,
            pulse_width_s=1e-6,
            bandwidth_hz=50e6,
            claimed_range_resolution_m=10.0,
        )
        assert math.isclose(r["range_resolution_m"], C / 100e6, rel_tol=REL_TOL)

    def test_claimed_resolution_finer_than_bandwidth_limit(self):
        with pytest.raises(PhysicalViolationError, match="Range Resolution") as exc:
            compute_radar_ambiguity(
                frequency_hz=10e9, prf_hz=1e3, bandwidth_hz=1e6, claimed_range_resolution_m=10.0
            )
        assert math.isclose(exc.value.computed_limit, C / 2e6, rel_tol=REL_TOL)

    def test_claimed_resolution_without_pulse_info_warns(self):
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3, claimed_range_resolution_m=1.0)
        assert r["range_resolution_m"] is None
        assert any("could not be checked" in w for w in r["warnings"])

    def test_non_positive_claimed_resolution(self):
        with pytest.raises(PhysicalViolationError, match="Range Resolution"):
            compute_radar_ambiguity(
                frequency_hz=10e9, prf_hz=1e3, pulse_width_s=1e-6, claimed_range_resolution_m=0.0
            )

    @pytest.mark.parametrize("prf", [0.0, -1.0, -1e3])
    def test_non_positive_prf(self, prf):
        with pytest.raises(PhysicalViolationError, match="Pulsed Radar Timing"):
            compute_radar_ambiguity(frequency_hz=10e9, prf_hz=prf)

    @pytest.mark.parametrize("tau", [0.0, -1e-6])
    def test_non_positive_pulse_width(self, tau):
        with pytest.raises(PhysicalViolationError, match="Pulsed Radar Timing"):
            compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3, pulse_width_s=tau)

    def test_duty_cycle_at_or_above_one(self):
        """tau = PRI means the radar never stops transmitting."""
        with pytest.raises(PhysicalViolationError, match="Pulsed Radar Timing") as exc:
            compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3, pulse_width_s=1e-3)
        assert exc.value.computed_limit == 1.0
        with pytest.raises(PhysicalViolationError, match="Pulsed Radar Timing"):
            compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3, pulse_width_s=2e-3)

    def test_high_duty_cycle_warns(self):
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3, pulse_width_s=0.6e-3)
        assert any("Duty cycle" in w for w in r["warnings"])

    def test_non_positive_bandwidth(self):
        with pytest.raises(PhysicalViolationError, match="Signal Processing"):
            compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3, bandwidth_hz=0.0)

    def test_non_positive_frequency(self):
        with pytest.raises(PhysicalViolationError, match="Electromagnetic"):
            compute_radar_ambiguity(frequency_hz=0.0, prf_hz=1e3)

    def test_validators_directly(self):
        validate_positive_prf(1.0)
        validate_positive_pulse_width(1e-9)
        with pytest.raises(PhysicalViolationError):
            validate_positive_prf(0.0)
        with pytest.raises(PhysicalViolationError):
            validate_positive_pulse_width(0.0)


class TestWarningsAndOutput:
    def test_range_claim_alone_gets_dilemma_warning(self):
        r = compute_radar_ambiguity(
            frequency_hz=10e9, prf_hz=1e3, claimed_unambiguous_range_m=100_000.0
        )
        assert any("Range-Doppler dilemma" in w for w in r["warnings"])

    def test_velocity_claim_alone_gets_dilemma_warning(self):
        r = compute_radar_ambiguity(
            frequency_hz=10e9, prf_hz=1e3, claimed_unambiguous_velocity_m_s=5.0
        )
        assert any("Range-Doppler dilemma" in w for w in r["warnings"])

    def test_low_time_bandwidth_product_warns(self):
        r = compute_radar_ambiguity(
            frequency_hz=10e9, prf_hz=1e3, pulse_width_s=1e-6, bandwidth_hz=1e5
        )
        assert any("Time-bandwidth product" in w for w in r["warnings"])

    def test_thz_frequency_warns(self):
        r = compute_radar_ambiguity(frequency_hz=1e12, prf_hz=1e3)
        assert any("300 GHz" in w for w in r["warnings"])

    def test_optional_outputs_none_when_not_supplied(self):
        r = compute_radar_ambiguity(frequency_hz=10e9, prf_hz=1e3)
        for key in (
            "doppler_shift_hz",
            "doppler_aliased",
            "apparent_velocity_m_s",
            "range_resolution_m",
            "minimum_range_m",
            "duty_cycle",
        ):
            assert r[key] is None
        assert r["warnings"] == []

    def test_human_readable_and_latex(self):
        r = compute_radar_ambiguity(
            frequency_hz=10e9, prf_hz=1e3, pulse_width_s=1e-6, target_velocity_m_s=100.0
        )
        assert "R_ua" in r["human_readable"]
        assert "Range resolution" in r["human_readable"]
        assert "ALIASED" in r["human_readable"]
        assert r["latex"].startswith("$R_{ua}")
        assert "f_d" in r["latex"]


# --- Property-based tests -------------------------------------------------------

freq = st.floats(min_value=1e6, max_value=3e11)
prf = st.floats(min_value=1.0, max_value=1e7)
velocity = st.floats(min_value=-1e4, max_value=1e4)


class TestProperties:
    @given(f=freq, p1=prf, p2=prf)
    def test_range_decreases_and_velocity_increases_with_prf(self, f, p1, p2):
        if p1 == p2:
            return
        lo, hi = sorted((p1, p2))
        r_lo = compute_radar_ambiguity(frequency_hz=f, prf_hz=lo)
        r_hi = compute_radar_ambiguity(frequency_hz=f, prf_hz=hi)
        assert r_lo["max_unambiguous_range_m"] > r_hi["max_unambiguous_range_m"]
        assert r_lo["max_unambiguous_velocity_m_s"] < r_hi["max_unambiguous_velocity_m_s"]

    @given(f=freq, p=prf)
    def test_invariant_is_prf_independent(self, f, p):
        r = compute_radar_ambiguity(frequency_hz=f, prf_hz=p)
        lam = C / f
        assert math.isclose(r["range_velocity_product_m2_s"], C * lam / 8, rel_tol=1e-9)
        assert math.isclose(r["first_blind_speed_m_s"], 2 * r["max_unambiguous_velocity_m_s"])

    @given(f=freq, p=prf, v=velocity)
    def test_apparent_velocity_within_unambiguous_band(self, f, p, v):
        r = compute_radar_ambiguity(frequency_hz=f, prf_hz=p, target_velocity_m_s=v)
        v_ua = r["max_unambiguous_velocity_m_s"]
        assert abs(r["apparent_velocity_m_s"]) <= v_ua * (1 + 1e-9)
        assert r["doppler_aliased"] == (abs(v) > v_ua)
        # Folding preserves velocity modulo the blind speed
        diff = (v - r["apparent_velocity_m_s"]) / r["first_blind_speed_m_s"]
        assert math.isclose(diff, round(diff), abs_tol=1e-6)

    @given(f=freq, p=prf)
    def test_claim_at_limit_never_raises(self, f, p):
        r = compute_radar_ambiguity(frequency_hz=f, prf_hz=p)
        compute_radar_ambiguity(
            frequency_hz=f,
            prf_hz=p,
            claimed_unambiguous_range_m=r["max_unambiguous_range_m"],
            claimed_unambiguous_velocity_m_s=r["max_unambiguous_velocity_m_s"],
        )
