"""Tests for the LLM demo harness in demo/llm/run.py.

The harness is a standalone script, not part of the package, so it is loaded
from its file path. Fixture rows used here are synthetic test data written to a
temporary directory; the real demo only ever replays recorded responses.
"""

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HARNESS_PATH = Path(__file__).resolve().parents[1] / "demo" / "llm" / "run.py"


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("physbound_llm_demo", HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Dataclasses with postponed annotations resolve them via sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scenarios(harness):
    return {s.id: s for s in harness.load_scenarios()}


def _write_fixture(harness, fixtures_dir: Path, scenario_id: str, contents: list[str], meta=True):
    rows_path, meta_path = harness.fixture_paths(fixtures_dir, scenario_id)
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    with rows_path.open("w", encoding="utf-8") as fh:
        for i, content in enumerate(contents):
            fh.write(json.dumps({"trial": i, "content": content}) + "\n")
    if meta:
        meta_path.write_text(
            json.dumps(
                {
                    "scenario_id": scenario_id,
                    "model": "synthetic-test-model",
                    "endpoint": "http://localhost:11434/v1",
                    "temperature": None,
                    "recorded_at": "2026-09-05T00:00:00+00:00",
                    "trials": len(contents),
                }
            )
        )


class TestScenarios:
    def test_scenarios_load_and_reference_real_tools(self, harness, scenarios):
        assert {"wifi-throughput", "dish-gain"} <= set(scenarios)
        for s in scenarios.values():
            assert callable(s.tool_fn())
            assert s.claim_unit in harness.UNIT_FAMILIES
            assert s.full_prompt().endswith("`ANSWER: <number> <unit>`.")

    def test_unknown_unit_family_rejected(self, harness, tmp_path):
        bad = tmp_path / "scenarios.json"
        bad.write_text(
            json.dumps(
                {
                    "scenarios": [
                        {
                            "id": "x",
                            "title": "x",
                            "prompt": "x",
                            "tool": "shannon_hartley",
                            "fixed_args": {},
                            "claim_arg": "claimed_throughput_bps",
                            "claim_unit": "furlongs",
                        }
                    ]
                }
            )
        )
        with pytest.raises(ValueError, match="unknown claim_unit"):
            harness.load_scenarios(bad)


class TestExtractClaim:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("Roughly 500 Mbps.\nANSWER: 500 Mbps", 500e6),
            ("**ANSWER:** 1.2 Gbps", 1.2e9),
            ("answer: 72,200 kbps", 72.2e6),
            ("ANSWER: 100 Mbit/s", 100e6),
            ("ANSWER: 100 Mb/s", 100e6),
            ("ANSWER: 100000000 bits per second", 100e6),
        ],
    )
    def test_bitrate_from_answer_line(self, harness, text, expected):
        value, note = harness.extract_claim(text, "bitrate")
        assert value == pytest.approx(expected)
        assert note == "from ANSWER line"

    def test_last_answer_line_wins(self, harness):
        value, _ = harness.extract_claim("ANSWER: 50 Mbps\nCorrection.\nANSWER: 80 Mbps", "bitrate")
        assert value == pytest.approx(80e6)

    def test_single_value_without_answer_line(self, harness):
        value, note = harness.extract_claim("You should see about 45 dBi of gain.", "gain_dbi")
        assert value == pytest.approx(45.0)
        assert "no ANSWER line" in note

    def test_db_without_i_accepted_for_gain(self, harness):
        value, _ = harness.extract_claim("ANSWER: 7.4 dB", "gain_dbi")
        assert value == pytest.approx(7.4)

    def test_dbm_not_confused_with_gain(self, harness):
        value, note = harness.extract_claim("ANSWER: -70 dBm", "gain_dbi")
        assert value is None
        assert "no gain_dbi value" in note

    def test_multiple_values_are_unparseable(self, harness):
        text = "Theory says 100 Mbps but 802.11n gives 150 Mbps per stream."
        value, note = harness.extract_claim(text, "bitrate")
        assert value is None
        assert "2 different values" in note

    def test_range_in_answer_line_is_unparseable(self, harness):
        value, note = harness.extract_claim("ANSWER: 70-100 Mbps", "bitrate")
        assert value is None
        assert "2 different values" in note

    @pytest.mark.parametrize("text", ["ANSWER: 70 to 100 Mbps", "ANSWER: 70\u2013100 Mbps"])
    def test_worded_and_dashed_ranges_are_unparseable(self, harness, text):
        value, note = harness.extract_claim(text, "bitrate")
        assert value is None
        assert "2 different values" in note

    def test_negative_value_is_a_sign_not_a_range(self, harness):
        value, _ = harness.extract_claim("ANSWER: -3 dBi", "gain_dbi")
        assert value == pytest.approx(-3.0)

    def test_repeated_same_value_is_fine(self, harness):
        value, _ = harness.extract_claim("About 100 Mbps. Yes, 100 Mbps.", "bitrate")
        assert value == pytest.approx(100e6)

    def test_no_value(self, harness):
        value, note = harness.extract_claim("It depends on many factors.", "bitrate")
        assert value is None
        assert "no bitrate value" in note

    def test_units_are_not_confused_with_mhz_or_snr(self, harness):
        text = "A 20 MHz channel at 15 dB SNR carries at most 100 Mbps."
        value, _ = harness.extract_claim(text, "bitrate")
        assert value == pytest.approx(100e6)
        value_m, _ = harness.extract_claim(text, "distance_m")
        assert value_m is None

    def test_format_quantity(self, harness):
        assert harness.format_quantity(500e6, "bitrate") == "500 Mbps"
        assert harness.format_quantity(1.2e9, "bitrate") == "1.2 Gbps"
        assert harness.format_quantity(45.0, "gain_dbi") == "45.0 dBi"


class TestLint:
    def test_shannon_violation(self, harness, scenarios):
        r = harness.lint_response(scenarios["wifi-throughput"], 0, "ANSWER: 500 Mbps")
        assert r.outcome == harness.OUTCOME_VIOLATION
        assert r.result["law_violated"] == "Shannon-Hartley Theorem"
        assert any("PHYSICS VIOLATION" in line for line in r.verdict_lines())

    def test_shannon_valid(self, harness, scenarios):
        r = harness.lint_response(scenarios["wifi-throughput"], 0, "ANSWER: 72 Mbps")
        assert r.outcome == harness.OUTCOME_VALID
        assert r.verdict_lines()[0].startswith("OK")

    def test_dish_violation(self, harness, scenarios):
        r = harness.lint_response(scenarios["dish-gain"], 0, "ANSWER: 45 dBi")
        assert r.outcome == harness.OUTCOME_VIOLATION
        assert r.result["law_violated"] == "Antenna Aperture Limit"

    def test_dish_warning(self, harness, scenarios):
        # Between the typical eta = 0.55 gain (7.4 dBi) and the hard limit (12.1 dBi).
        r = harness.lint_response(scenarios["dish-gain"], 0, "ANSWER: 9 dBi")
        assert r.outcome == harness.OUTCOME_WARNING
        assert any("warning:" in line for line in r.verdict_lines())

    def test_methodology_note_does_not_make_a_warning_outcome(self, harness, scenarios):
        r = harness.lint_response(scenarios["dish-gain"], 0, "ANSWER: 7 dBi")
        assert r.outcome == harness.OUTCOME_VALID
        assert r.result["warnings"]  # the beamwidth note is present ...
        assert any(line.startswith("  note:") for line in r.verdict_lines())  # ... shown as a note

    def test_unparseable(self, harness, scenarios):
        r = harness.lint_response(scenarios["wifi-throughput"], 0, "It depends.")
        assert r.outcome == harness.OUTCOME_UNPARSEABLE
        assert r.claim is None
        assert r.verdict_lines()[0].startswith("UNPARSEABLE")

    def test_tool_input_rejection_is_unparseable(self, harness, scenarios):
        # A negative gain claim is a number the tool accepts; a zero-bandwidth style
        # rejection cannot come from the claim, so drive a pydantic error via a bad
        # scenario instead.
        bad = harness.Scenario(
            id="bad",
            title="bad",
            prompt="x",
            tool="shannon_hartley",
            fixed_args={"bandwidth_hz": 20e6},  # no SNR -> ShannonInput validator fails
            claim_arg="claimed_throughput_bps",
            claim_unit="bitrate",
        )
        r = harness.lint_response(bad, 0, "ANSWER: 10 Mbps")
        assert r.outcome == harness.OUTCOME_UNPARSEABLE
        assert "tool rejected input" in r.note

    def test_tally_includes_all_outcomes(self, harness, scenarios):
        results = harness.lint_all(
            scenarios["wifi-throughput"],
            [
                {"trial": 0, "content": "ANSWER: 500 Mbps"},
                {"trial": 1, "content": "ANSWER: 80 Mbps"},
                {"trial": 2, "content": "no idea"},
            ],
        )
        counts = harness.tally(results)
        assert counts[harness.OUTCOME_VIOLATION] == 1
        assert counts[harness.OUTCOME_VALID] == 1
        assert counts[harness.OUTCOME_UNPARSEABLE] == 1
        assert counts[harness.OUTCOME_WARNING] == 0


class TestReplayCli:
    def test_replay_renders_transcript_and_aggregate(self, harness, tmp_path, capsys):
        _write_fixture(
            harness,
            tmp_path,
            "wifi-throughput",
            ["Around 500 Mbps.\nANSWER: 500 Mbps", "ANSWER: 80 Mbps", "Hard to say."],
        )
        _write_fixture(harness, tmp_path, "dish-gain", ["ANSWER: 45 dBi"])
        code = harness.main(["--fixtures-dir", str(tmp_path), "replay"])
        out = capsys.readouterr().out
        assert code == 0
        assert "1/2: Wi-Fi throughput" in out
        assert "2/2: Antenna gain" in out
        assert "synthetic-test-model via localhost:11434" in out
        assert "Claim  : 500 Mbps  (from ANSWER line)" in out
        assert "PHYSICS VIOLATION [Shannon-Hartley Theorem]" in out
        assert (
            "Across 3 trials: 1 physics violations, 0 valid with warnings, 1 valid, 1 unparseable"
            in out
        )

    def test_default_mode_is_replay(self, harness, tmp_path, capsys):
        _write_fixture(harness, tmp_path, "wifi-throughput", ["ANSWER: 80 Mbps"])
        _write_fixture(harness, tmp_path, "dish-gain", ["ANSWER: 7 dBi"])
        code = harness.main(["--fixtures-dir", str(tmp_path)])
        assert code == 0
        assert "OK  claim is within physical limits" in capsys.readouterr().out

    def test_trial_selection_and_list(self, harness, tmp_path, capsys):
        _write_fixture(harness, tmp_path, "dish-gain", ["ANSWER: 45 dBi", "ANSWER: 7 dBi"])
        code = harness.main(
            [
                "--fixtures-dir",
                str(tmp_path),
                "replay",
                "--scenario",
                "dish-gain",
                "--trial",
                "1",
                "--list",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "Answer (trial 1):" in out
        assert "trial  0  violation" in out
        assert "trial  1  valid " in out
        assert "valid_with_warnings" not in out

    def test_answer_truncation_is_announced(self, harness, tmp_path, capsys):
        long_answer = "\n".join(f"line {i}" for i in range(12)) + "\nANSWER: 45 dBi"
        _write_fixture(harness, tmp_path, "dish-gain", [long_answer])
        harness.main(
            [
                "--fixtures-dir",
                str(tmp_path),
                "replay",
                "--scenario",
                "dish-gain",
                "--answer-lines",
                "3",
            ]
        )
        out = capsys.readouterr().out
        assert "line 2" in out
        assert "line 3" not in out
        assert "10 more lines" in out

    def test_missing_fixture_explains_how_to_record(self, harness, tmp_path, capsys):
        code = harness.main(["--fixtures-dir", str(tmp_path), "replay", "--scenario", "dish-gain"])
        err = capsys.readouterr().err
        assert code == 1
        assert "no recording for 'dish-gain'" in err
        assert "record --model <name> --scenario dish-gain" in err

    def test_missing_meta_is_flagged_not_fatal(self, harness, tmp_path, capsys):
        _write_fixture(harness, tmp_path, "dish-gain", ["ANSWER: 45 dBi"], meta=False)
        code = harness.main(["--fixtures-dir", str(tmp_path), "replay", "--scenario", "dish-gain"])
        assert code == 0
        assert "conditions file missing" in capsys.readouterr().out

    def test_unknown_scenario_id(self, harness, tmp_path):
        with pytest.raises(SystemExit, match="unknown scenario id"):
            harness.main(["--fixtures-dir", str(tmp_path), "replay", "--scenario", "nope"])

    def test_out_of_range_trial(self, harness, tmp_path, capsys):
        _write_fixture(harness, tmp_path, "dish-gain", ["ANSWER: 45 dBi"])
        code = harness.main(
            ["--fixtures-dir", str(tmp_path), "replay", "--scenario", "dish-gain", "--trial", "7"]
        )
        assert code == 1
        assert "trial 7 not in fixtures" in capsys.readouterr().err

    def test_summary_table(self, harness, tmp_path, capsys):
        _write_fixture(
            harness, tmp_path, "wifi-throughput", ["ANSWER: 500 Mbps", "ANSWER: 80 Mbps"]
        )
        code = harness.main(["--fixtures-dir", str(tmp_path), "summary"])
        out = capsys.readouterr().out
        assert code == 0
        assert "wifi-throughput" in out
        assert "synthetic-test-model" in out
        assert "dish-gain" not in out  # not recorded, so not listed

    def test_summary_without_recordings(self, harness, tmp_path, capsys):
        code = harness.main(["--fixtures-dir", str(tmp_path), "summary"])
        assert code == 1
        assert "no recordings found" in capsys.readouterr().err


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class TestRecord:
    @pytest.fixture()
    def fake_endpoint(self, harness, monkeypatch):
        """Replace urlopen with a canned OpenAI-style response and capture requests."""
        captured: list[dict] = []
        answers = iter(["ANSWER: 500 Mbps", "ANSWER: 80 Mbps"])

        def fake_urlopen(request, timeout=None):
            captured.append(
                {
                    "url": request.full_url,
                    "headers": dict(request.header_items()),
                    "payload": json.loads(request.data.decode("utf-8")),
                    "timeout": timeout,
                }
            )
            body = {
                "id": f"chatcmpl-{len(captured)}",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": next(answers)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 40, "completion_tokens": 8, "total_tokens": 48},
            }
            return _FakeResponse(json.dumps(body).encode("utf-8"))

        monkeypatch.setattr(harness.urllib.request, "urlopen", fake_urlopen)
        return captured

    def test_record_writes_rows_and_conditions(self, harness, tmp_path, fake_endpoint, monkeypatch):
        monkeypatch.setenv("TEST_LLM_KEY", "sk-test")
        code = harness.main(
            [
                "--fixtures-dir",
                str(tmp_path),
                "record",
                "--endpoint",
                "https://example.test/v1/",
                "--api-key-env",
                "TEST_LLM_KEY",
                "--model",
                "tiny-model",
                "--trials",
                "2",
                "--scenario",
                "wifi-throughput",
                "--temperature",
                "0.7",
            ]
        )
        assert code == 0
        assert len(fake_endpoint) == 2
        req = fake_endpoint[0]
        assert req["url"] == "https://example.test/v1/chat/completions"
        assert req["headers"]["Authorization"] == "Bearer sk-test"
        assert req["payload"]["model"] == "tiny-model"
        assert req["payload"]["temperature"] == 0.7
        assert req["payload"]["messages"][-1]["content"].endswith("`ANSWER: <number> <unit>`.")
        assert all(m["role"] != "system" for m in req["payload"]["messages"])

        rows, meta = harness.load_fixture(tmp_path, "wifi-throughput")
        assert [r["trial"] for r in rows] == [0, 1]
        assert rows[0]["content"] == "ANSWER: 500 Mbps"
        assert rows[0]["finish_reason"] == "stop"
        assert rows[0]["usage"]["total_tokens"] == 48
        assert meta["model"] == "tiny-model"
        assert meta["endpoint"] == "https://example.test/v1"
        assert meta["temperature"] == 0.7
        assert meta["system_prompt"] is None
        assert meta["trials"] == 2
        assert meta["prompt_sent"] == harness.load_scenarios()[0].full_prompt()
        rows_path, _ = harness.fixture_paths(tmp_path, "wifi-throughput")
        assert meta["responses_sha256"] == hashlib.sha256(rows_path.read_bytes()).hexdigest()

        # The recording replays end to end.
        code = harness.main(
            ["--fixtures-dir", str(tmp_path), "replay", "--scenario", "wifi-throughput"]
        )
        assert code == 0

    def test_record_omits_temperature_by_default(self, harness, tmp_path, fake_endpoint):
        code = harness.main(
            [
                "--fixtures-dir",
                str(tmp_path),
                "record",
                "--endpoint",
                "http://localhost:11434/v1",
                "--model",
                "local-model",
                "--trials",
                "1",
                "--scenario",
                "wifi-throughput",
                "--system",
                "You are an RF engineer.",
            ]
        )
        assert code == 0
        payload = fake_endpoint[0]["payload"]
        assert "temperature" not in payload
        assert payload["messages"][0] == {"role": "system", "content": "You are an RF engineer."}
        assert "Authorization" not in fake_endpoint[0]["headers"]
        _, meta = harness.load_fixture(tmp_path, "wifi-throughput")
        assert meta["temperature"] is None
        assert meta["system_prompt"] == "You are an RF engineer."

    def test_record_requires_model(self, harness, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("PHYSBOUND_LLM_MODEL", raising=False)
        code = harness.main(["--fixtures-dir", str(tmp_path), "record"])
        assert code == 2
        assert "--model" in capsys.readouterr().err

    def test_record_requires_key_for_remote_endpoint(self, harness, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        code = harness.main(
            [
                "--fixtures-dir",
                str(tmp_path),
                "record",
                "--endpoint",
                "https://api.example.test/v1",
                "--model",
                "m",
            ]
        )
        assert code == 2
        assert "OPENAI_API_KEY is not set" in capsys.readouterr().err

    def test_record_reports_http_error(self, harness, tmp_path, capsys, monkeypatch):
        def failing_urlopen(request, timeout=None):
            raise harness.urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {},
                io.BytesIO(b'{"error":"rate limited"}'),
            )

        monkeypatch.setattr(harness.urllib.request, "urlopen", failing_urlopen)
        code = harness.main(
            [
                "--fixtures-dir",
                str(tmp_path),
                "record",
                "--endpoint",
                "http://localhost:11434/v1",
                "--model",
                "m",
                "--trials",
                "1",
            ]
        )
        assert code == 1
        assert "HTTP 429" in capsys.readouterr().err
