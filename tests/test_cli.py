"""CLI tests — argument parsing, exit codes, output shapes, serve dispatch."""

import json

import pytest

from physbound import __version__
from physbound import server as server_module
from physbound.cli import EXIT_OK, EXIT_USAGE, EXIT_VIOLATION, main


@pytest.fixture()
def fake_run(monkeypatch):
    """Replace mcp.run with a recorder so serve tests never block."""
    calls: list[dict] = []

    def record(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(server_module.mcp, "run", record)
    return calls


class TestVersionAndUsage:
    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_unknown_command_exits_2(self):
        with pytest.raises(SystemExit) as excinfo:
            main(["frobnicate"])
        assert excinfo.value.code == EXIT_USAGE

    def test_check_without_tool_exits_2(self):
        with pytest.raises(SystemExit) as excinfo:
            main(["check"])
        assert excinfo.value.code == EXIT_USAGE

    def test_missing_required_flag_exits_2(self):
        with pytest.raises(SystemExit) as excinfo:
            main(["check", "shannon"])
        assert excinfo.value.code == EXIT_USAGE

    def test_non_numeric_flag_exits_2(self):
        with pytest.raises(SystemExit) as excinfo:
            main(["check", "shannon", "--bandwidth-hz", "twenty"])
        assert excinfo.value.code == EXIT_USAGE


class TestServeDispatch:
    def test_no_args_starts_stdio_server(self, fake_run):
        assert main([]) == EXIT_OK
        assert fake_run == [{"args": (), "kwargs": {"transport": "stdio"}}]

    def test_serve_defaults_to_stdio(self, fake_run):
        assert main(["serve"]) == EXIT_OK
        assert fake_run == [{"args": (), "kwargs": {"transport": "stdio"}}]

    def test_serve_http_passes_host_and_port(self, fake_run):
        assert main(["serve", "--transport", "http", "--host", "0.0.0.0", "--port", "9000"]) == 0
        assert fake_run == [
            {"args": (), "kwargs": {"transport": "http", "host": "0.0.0.0", "port": 9000}}
        ]

    def test_serve_rejects_unknown_transport(self, fake_run):
        with pytest.raises(SystemExit) as excinfo:
            main(["serve", "--transport", "sse"])
        assert excinfo.value.code == EXIT_USAGE
        assert fake_run == []


class TestCheckLinkBudget:
    ARGS = [
        "check",
        "link-budget",
        "--tx-power-dbm",
        "20",
        "--tx-antenna-gain-dbi",
        "10",
        "--rx-antenna-gain-dbi",
        "3",
        "--frequency-hz",
        "2.4e9",
        "--distance-m",
        "100",
    ]

    def test_happy_path(self, capsys):
        assert main(self.ARGS) == EXIT_OK
        out = capsys.readouterr().out
        assert "Link Budget" in out or "dBm" in out

    def test_violation_exit_code_1(self, capsys):
        code = main(
            [
                "check",
                "link-budget",
                "--tx-power-dbm",
                "20",
                "--tx-antenna-gain-dbi",
                "45",
                "--rx-antenna-gain-dbi",
                "0",
                "--frequency-hz",
                "1e9",
                "--distance-m",
                "1000",
                "--tx-antenna-diameter-m",
                "0.3",
            ]
        )
        assert code == EXIT_VIOLATION
        err = capsys.readouterr().err
        assert "PHYSICS VIOLATION" in err
        assert "Aperture" in err


class TestCheckShannon:
    def test_happy_path(self, capsys):
        code = main(["check", "shannon", "--bandwidth-hz", "20e6", "--snr-db", "15"])
        assert code == EXIT_OK
        assert "Capacity" in capsys.readouterr().out

    def test_valid_claim(self, capsys):
        code = main(
            [
                "check",
                "shannon",
                "--bandwidth-hz",
                "20e6",
                "--snr-db",
                "15",
                "--claimed-throughput-bps",
                "50e6",
            ]
        )
        assert code == EXIT_OK

    def test_violation_exit_code_1(self, capsys):
        code = main(
            [
                "check",
                "shannon",
                "--bandwidth-hz",
                "20e6",
                "--snr-db",
                "15",
                "--claimed-throughput-bps",
                "500e6",
            ]
        )
        assert code == EXIT_VIOLATION
        err = capsys.readouterr().err
        assert "Shannon" in err
        assert "Computed limit" in err
        assert "Claimed value" in err

    def test_json_output_shape(self, capsys):
        code = main(["check", "shannon", "--bandwidth-hz", "20e6", "--snr-db", "15", "--json"])
        assert code == EXIT_OK
        data = json.loads(capsys.readouterr().out)
        assert data["capacity_bps"] > 0
        assert "spectral_efficiency_bps_hz" in data
        assert "human_readable" in data

    def test_json_violation_still_exit_1(self, capsys):
        code = main(
            [
                "check",
                "shannon",
                "--bandwidth-hz",
                "20e6",
                "--snr-db",
                "15",
                "--claimed-throughput-bps",
                "500e6",
                "--json",
            ]
        )
        assert code == EXIT_VIOLATION
        data = json.loads(capsys.readouterr().out)
        assert data["error"] is True
        assert data["law_violated"] == "Shannon-Hartley Theorem"

    def test_both_snr_flags_is_usage_error(self, capsys):
        code = main(
            ["check", "shannon", "--bandwidth-hz", "20e6", "--snr-db", "15", "--snr-linear", "31"]
        )
        assert code == EXIT_USAGE
        assert "invalid arguments" in capsys.readouterr().err

    def test_missing_snr_is_usage_error(self, capsys):
        code = main(["check", "shannon", "--bandwidth-hz", "20e6"])
        assert code == EXIT_USAGE


class TestCheckNoise:
    def test_happy_path(self, capsys):
        code = main(["check", "noise", "--bandwidth-hz", "1e6"])
        assert code == EXIT_OK
        assert "-113.98" in capsys.readouterr().out

    def test_repeatable_stages_and_sensitivity(self, capsys):
        code = main(
            [
                "check",
                "noise",
                "--bandwidth-hz",
                "10e6",
                "--stage",
                "20:1.5",
                "--stage",
                "10:8",
                "--required-snr-db",
                "10",
            ]
        )
        assert code == EXIT_OK
        out = capsys.readouterr().out
        assert "Cascaded NF" in out
        assert "Sensitivity" in out

    def test_stage_with_negative_gain(self, capsys):
        # A value starting with "-" must use the --flag=value form or argparse
        # mistakes it for an option name.
        code = main(["check", "noise", "--bandwidth-hz", "1e6", "--stage=-3:3"])
        assert code == EXIT_OK

    def test_warning_printed_for_non_reference_temperature(self, capsys):
        code = main(
            [
                "check",
                "noise",
                "--bandwidth-hz",
                "1e6",
                "--temperature-k",
                "77",
                "--stage",
                "20:3",
            ]
        )
        assert code == EXIT_OK
        assert "warning:" in capsys.readouterr().out

    def test_malformed_stage_exits_2(self):
        with pytest.raises(SystemExit) as excinfo:
            main(["check", "noise", "--bandwidth-hz", "1e6", "--stage", "20"])
        assert excinfo.value.code == EXIT_USAGE

    def test_non_numeric_stage_exits_2(self):
        with pytest.raises(SystemExit) as excinfo:
            main(["check", "noise", "--bandwidth-hz", "1e6", "--stage", "a:b"])
        assert excinfo.value.code == EXIT_USAGE

    def test_negative_bandwidth_is_usage_error(self, capsys):
        code = main(["check", "noise", "--bandwidth-hz", "-1"])
        assert code == EXIT_USAGE


class TestCheckRadarRange:
    ARGS = [
        "check",
        "radar-range",
        "--peak-power-w",
        "1000",
        "--antenna-gain-dbi",
        "30",
        "--frequency-hz",
        "10e9",
        "--rcs-m2",
        "1",
    ]

    def test_happy_path(self, capsys):
        assert main(self.ARGS) == EXIT_OK
        assert "Range" in capsys.readouterr().out

    def test_num_pulses_is_int(self, capsys):
        code = main([*self.ARGS, "--num-pulses", "10", "--losses-db", "3", "--json"])
        assert code == EXIT_OK
        data = json.loads(capsys.readouterr().out)
        assert data["integration_gain"] == 10

    def test_violation_exit_code_1(self, capsys):
        code = main(
            [
                "check",
                "radar-range",
                "--peak-power-w",
                "100",
                "--antenna-gain-dbi",
                "20",
                "--frequency-hz",
                "10e9",
                "--rcs-m2",
                "0.01",
                "--claimed-range-m",
                "1e6",
            ]
        )
        assert code == EXIT_VIOLATION
        assert "Radar Range" in capsys.readouterr().err


class TestCheckAntenna:
    def test_happy_path(self, capsys):
        code = main(["check", "antenna", "--frequency-hz", "10e9", "--diameter-m", "1"])
        assert code == EXIT_OK
        assert "dBi" in capsys.readouterr().out

    def test_valid_claim_with_warning(self, capsys):
        code = main(
            [
                "check",
                "antenna",
                "--frequency-hz",
                "10e9",
                "--diameter-m",
                "1",
                "--claimed-gain-dbi",
                "39",
            ]
        )
        assert code == EXIT_OK
        assert "warning:" in capsys.readouterr().out

    def test_violation_exit_code_1(self, capsys):
        code = main(
            [
                "check",
                "antenna",
                "--frequency-hz",
                "1e9",
                "--diameter-m",
                "0.3",
                "--claimed-gain-dbi",
                "45",
            ]
        )
        assert code == EXIT_VIOLATION
        assert "Aperture" in capsys.readouterr().err

    def test_both_size_inputs_is_usage_error(self, capsys):
        code = main(
            [
                "check",
                "antenna",
                "--frequency-hz",
                "10e9",
                "--diameter-m",
                "1",
                "--aperture-area-m2",
                "1",
            ]
        )
        assert code == EXIT_USAGE


class TestCheckRadarAmbiguity:
    def test_happy_path(self, capsys):
        code = main(
            [
                "check",
                "radar-ambiguity",
                "--frequency-hz",
                "10e9",
                "--prf-hz",
                "1e3",
                "--pulse-width-s",
                "1e-6",
            ]
        )
        assert code == EXIT_OK
        assert "R_ua" in capsys.readouterr().out

    def test_aliased_target_warns(self, capsys):
        code = main(
            [
                "check",
                "radar-ambiguity",
                "--frequency-hz",
                "10e9",
                "--prf-hz",
                "10e3",
                "--target-velocity-m-s",
                "100",
            ]
        )
        assert code == EXIT_OK
        assert "aliased" in capsys.readouterr().out

    def test_violation_exit_code_1(self, capsys):
        code = main(
            [
                "check",
                "radar-ambiguity",
                "--frequency-hz",
                "10e9",
                "--prf-hz",
                "10e3",
                "--claimed-unambiguous-velocity-m-s",
                "500",
            ]
        )
        assert code == EXIT_VIOLATION
        assert "Doppler" in capsys.readouterr().err
