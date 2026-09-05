"""PhysBound LLM demo harness: ask a real model an RF question, lint its answer.

The harness has three modes:

``record``
    Send each scenario's prompt to an OpenAI-compatible chat-completions
    endpoint ``N`` times and store every response, verbatim and unedited, in
    ``fixtures/<scenario>.jsonl``. A ``fixtures/<scenario>.meta.json`` file
    records the conditions: model, endpoint, exact prompt sent, sampling
    parameters, trial count, timestamp and the SHA-256 of the response file.

``replay`` (default)
    Read the fixtures, extract the single claimed number from each response,
    run the matching physbound tool on it, and print one transcript (trial 0
    unless ``--trial`` says otherwise) followed by the outcome counts across
    all trials. Needs no network, no API key, and nothing beyond physbound.

``summary``
    One table of outcome counts across every recorded scenario.

Design notes
------------
* The question fixes every input except the claim. Extraction therefore only
  has to find one number with a unit in the answer, which is done with a
  deterministic unit-aware parser. No second model is involved in judging.
* Responses that hedge, give a range, or state several different values are
  counted as ``unparseable`` rather than forced into a verdict.
* Nothing is edited or filtered after recording. The transcript shown is
  trial 0 by default, so the demo cannot silently cherry-pick.

Run from the repository root with ``uv run python demo/llm/run.py --help``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import textwrap
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

import physbound
from physbound import server as _server

HARNESS_VERSION = "1"
HERE = Path(__file__).resolve().parent
DEFAULT_SCENARIOS = HERE / "scenarios.json"
DEFAULT_FIXTURES = HERE / "fixtures"
DEFAULT_ENDPOINT = "http://localhost:11434/v1"  # Ollama's OpenAI-compatible server

# Appended to every scenario prompt so the answer ends in a machine-readable
# line. It constrains the format of the answer, not its physics.
FORMAT_SUFFIX = (
    "\n\nAnswer briefly, then finish with one final line of the form `ANSWER: <number> <unit>`."
)

OUTCOME_VIOLATION = "violation"
OUTCOME_WARNING = "valid_with_warnings"
OUTCOME_VALID = "valid"
OUTCOME_UNPARSEABLE = "unparseable"
OUTCOMES = (OUTCOME_VIOLATION, OUTCOME_WARNING, OUTCOME_VALID, OUTCOME_UNPARSEABLE)

_SI = {"k": 1e3, "m": 1e6, "g": 1e9, "t": 1e12}
_NUM = r"(?P<num>-?\d[\d,]*(?:\.\d+)?)"

# Each unit family maps to a regex that captures a number (``num``) and an
# optional SI prefix (``prefix``), and a canonical unit label for display.
UNIT_FAMILIES: dict[str, dict[str, Any]] = {
    "bitrate": {
        "pattern": re.compile(
            _NUM
            + r"\s*(?P<prefix>[kKmMgGtT])?\s*"
            + r"(?:bps|bit/s|bits/s|b/s|bit per second|bits per second)\b",
            re.IGNORECASE,
        ),
        "label": "bps",
    },
    "gain_dbi": {
        "pattern": re.compile(_NUM + r"\s*(?P<prefix>)dBi?\b", re.IGNORECASE),
        "label": "dBi",
    },
    "power_dbm": {
        "pattern": re.compile(_NUM + r"\s*(?P<prefix>)dBm\b", re.IGNORECASE),
        "label": "dBm",
    },
    "distance_m": {
        "pattern": re.compile(
            _NUM + r"\s*(?P<prefix>[kK])?\s*(?:m|metres|meters)\b", re.IGNORECASE
        ),
        "label": "m",
    },
}

_ANSWER_LINE = re.compile(r"^\s*\**\s*ANSWER\s*:\**\s*(?P<body>.+?)\s*$", re.IGNORECASE | re.M)


# --------------------------------------------------------------------------- #
# Scenarios and fixtures
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    prompt: str
    tool: str
    fixed_args: dict[str, Any]
    claim_arg: str
    claim_unit: str

    def full_prompt(self) -> str:
        return self.prompt + FORMAT_SUFFIX

    def tool_fn(self):
        return getattr(_server, self.tool)


def load_scenarios(path: Path = DEFAULT_SCENARIOS) -> list[Scenario]:
    data = json.loads(path.read_text(encoding="utf-8"))
    scenarios = [Scenario(**item) for item in data["scenarios"]]
    for s in scenarios:
        if s.claim_unit not in UNIT_FAMILIES:
            raise ValueError(f"scenario {s.id!r}: unknown claim_unit {s.claim_unit!r}")
        if not callable(getattr(_server, s.tool, None)):
            raise ValueError(f"scenario {s.id!r}: unknown physbound tool {s.tool!r}")
    return scenarios


def fixture_paths(fixtures_dir: Path, scenario_id: str) -> tuple[Path, Path]:
    return fixtures_dir / f"{scenario_id}.jsonl", fixtures_dir / f"{scenario_id}.meta.json"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_fixture(fixtures_dir: Path, scenario_id: str) -> tuple[list[dict], dict | None]:
    rows_path, meta_path = fixture_paths(fixtures_dir, scenario_id)
    if not rows_path.exists():
        raise FileNotFoundError(rows_path)
    rows = [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
    return rows, meta


# --------------------------------------------------------------------------- #
# Claim extraction
# --------------------------------------------------------------------------- #


_RANGE_BEFORE = re.compile(r"(?P<lo>\d[\d,]*(?:\.\d+)?)\s*(?:-|\u2013|\u2014|to)\s*$")
_TRAILING_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)$")


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def _values_in(text: str, pattern: re.Pattern) -> list[float]:
    """All values of one unit family in ``text``, in base units.

    A range such as ``70-100 Mbps``, ``70 to 100 Mbps`` or ``70\u2013100 Mbps``
    contributes both ends, so it is later reported as two different values.
    A leading minus is a sign only when no digit precedes it (``-3 dBi``).
    """
    values: list[float] = []
    for m in pattern.finditer(text):
        num = m.group("num")
        mult = _SI.get((m.group("prefix") or "").lower(), 1.0)
        before = text[: m.start()]
        if num.startswith("-") and before[-1:].isdigit():
            lo = _TRAILING_NUMBER.search(before)
            assert lo is not None
            values.append(_num(lo.group(1)) * mult)
            values.append(_num(num[1:]) * mult)
            continue
        lo_match = _RANGE_BEFORE.search(before)
        if lo_match:
            values.append(_num(lo_match.group("lo")) * mult)
        values.append(_num(num) * mult)
    return values


def _distinct(values: Sequence[float]) -> list[float]:
    out: list[float] = []
    for v in values:
        if not any(abs(v - u) <= 1e-9 * max(abs(v), abs(u), 1.0) for u in out):
            out.append(v)
    return out


def extract_claim(text: str, unit_family: str) -> tuple[float | None, str]:
    """Return ``(value_in_base_units, note)``.

    Looks first at the final ``ANSWER:`` line; if that is absent, scans the
    whole text. Exactly one distinct value is required; anything else is
    reported as unparseable with a note saying why.
    """
    pattern = UNIT_FAMILIES[unit_family]["pattern"]
    answer_lines = _ANSWER_LINE.findall(text)
    if answer_lines:
        body = answer_lines[-1]
        values = _distinct(_values_in(body, pattern))
        if len(values) == 1:
            return values[0], "from ANSWER line"
        if not values:
            return None, f"ANSWER line has no {unit_family} value: {body!r}"
        return None, f"ANSWER line gives {len(values)} different values: {body!r}"

    values = _distinct(_values_in(text, pattern))
    if len(values) == 1:
        return values[0], "single value in text (no ANSWER line)"
    if not values:
        return None, f"no {unit_family} value found in text"
    return None, f"{len(values)} different values in text and no ANSWER line"


def format_quantity(value: float, unit_family: str) -> str:
    label = UNIT_FAMILIES[unit_family]["label"]
    if unit_family in ("bitrate", "distance_m"):
        for prefix, mult in (("G", 1e9), ("M", 1e6), ("k", 1e3)):
            if abs(value) >= mult:
                return f"{value / mult:.3g} {prefix}{label}"
        return f"{value:.3g} {label}"
    return f"{value:.1f} {label}"


# --------------------------------------------------------------------------- #
# Linting
# --------------------------------------------------------------------------- #


@dataclass
class LintResult:
    trial: int
    outcome: str
    claim: float | None
    note: str
    result: dict[str, Any] | None

    def verdict_lines(self) -> list[str]:
        if self.outcome == OUTCOME_UNPARSEABLE:
            return [f"UNPARSEABLE  {self.note}"]
        assert self.result is not None
        if self.outcome == OUTCOME_VIOLATION:
            r = self.result
            unit = f" {r['unit']}" if r.get("unit") else ""
            lines = [f"PHYSICS VIOLATION [{r['law_violated']}]", f"  {r['message']}"]
            if r.get("computed_limit") is not None:
                lines.append(f"  Computed limit: {r['computed_limit']:g}{unit}")
            if r.get("claimed_value") is not None:
                lines.append(f"  Claimed value:  {r['claimed_value']:g}{unit}")
            return lines
        lines = ["OK  claim is within physical limits"]
        for w in self.result.get("warnings", []):
            lines.append(f"  {'warning' if is_claim_warning(w) else 'note'}: {w}")
        return lines


def is_claim_warning(warning: str) -> bool:
    """True for warnings about the claim itself, as opposed to methodology notes.

    physbound tools return both kinds in one ``warnings`` list. Claim caveats
    ("claimed gain ... exceeds the typical-efficiency value", "claimed spectral
    efficiency ... unusual") name the claim; notes such as which beamwidth rule
    of thumb was used do not. Only the former change the outcome.
    """
    return "claim" in warning.lower()


def lint_response(scenario: Scenario, trial: int, content: str) -> LintResult:
    claim, note = extract_claim(content, scenario.claim_unit)
    if claim is None:
        return LintResult(trial, OUTCOME_UNPARSEABLE, None, note, None)
    kwargs = dict(scenario.fixed_args)
    kwargs[scenario.claim_arg] = claim
    try:
        result = scenario.tool_fn()(**kwargs)
    except ValidationError as exc:
        msgs = "; ".join(err["msg"] for err in exc.errors())
        return LintResult(trial, OUTCOME_UNPARSEABLE, claim, f"tool rejected input: {msgs}", None)
    if result.get("error"):
        return LintResult(trial, OUTCOME_VIOLATION, claim, note, result)
    if any(is_claim_warning(w) for w in result.get("warnings", [])):
        return LintResult(trial, OUTCOME_WARNING, claim, note, result)
    return LintResult(trial, OUTCOME_VALID, claim, note, result)


def lint_all(scenario: Scenario, rows: list[dict]) -> list[LintResult]:
    return [lint_response(scenario, row["trial"], row["content"]) for row in rows]


def tally(results: Sequence[LintResult]) -> Counter:
    counts: Counter = Counter({o: 0 for o in OUTCOMES})
    counts.update(r.outcome for r in results)
    return counts


# --------------------------------------------------------------------------- #
# Recording (live API calls)
# --------------------------------------------------------------------------- #


class ChatClient:
    """Minimal OpenAI-compatible chat-completions client using only the stdlib."""

    def __init__(self, endpoint: str, model: str, api_key: str | None, timeout_s: float = 120.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s

    def complete(
        self,
        prompt: str,
        system: str | None,
        temperature: float | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {"Content-Type": "application/json", "User-Agent": "physbound-llm-demo"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))


def _content_of(response: dict[str, Any]) -> str:
    choice = response["choices"][0]
    content = choice["message"].get("content")
    if isinstance(content, list):  # some servers return content parts
        content = "".join(part.get("text", "") for part in content)
    return content or ""


def record_scenario(
    scenario: Scenario,
    client: ChatClient,
    fixtures_dir: Path,
    trials: int,
    system: str | None,
    temperature: float | None,
    max_tokens: int,
    pause_s: float,
    log=print,
) -> tuple[Path, Path]:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    rows_path, meta_path = fixture_paths(fixtures_dir, scenario.id)
    prompt = scenario.full_prompt()
    started = datetime.now(UTC)
    with rows_path.open("w", encoding="utf-8") as fh:
        for trial in range(trials):
            t0 = time.perf_counter()
            response = client.complete(prompt, system, temperature, max_tokens)
            latency = time.perf_counter() - t0
            choice = response["choices"][0]
            row = {
                "trial": trial,
                "requested_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "latency_s": round(latency, 3),
                "content": _content_of(response),
                "finish_reason": choice.get("finish_reason"),
                "usage": response.get("usage"),
                "response_id": response.get("id"),
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            log(f"  [{scenario.id}] trial {trial + 1}/{trials} done ({latency:.1f}s)")
            if pause_s and trial + 1 < trials:
                time.sleep(pause_s)
    meta = {
        "scenario_id": scenario.id,
        "harness_version": HARNESS_VERSION,
        "physbound_version": physbound.__version__,
        "model": client.model,
        "endpoint": client.endpoint,
        "system_prompt": system,
        "prompt_sent": prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "trials": trials,
        "recorded_at": started.isoformat(timespec="seconds"),
        "responses_sha256": sha256_of(rows_path),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rows_path, meta_path


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _fmt_num(value: Any) -> str:
    """Plain decimal for round numbers (20000000, 0.3), general format otherwise."""
    if isinstance(value, float | int) and not isinstance(value, bool):
        return format(value, ".10g")
    return str(value)


def _field(label: str, text: str, width: int) -> list[str]:
    """``label: text`` with continuation lines aligned under the text."""
    indent = " " * (len(label) + 2)
    lines = textwrap.wrap(text, width=width, initial_indent=label + ": ", subsequent_indent=indent)
    return lines or [label + ": "]


def _wrap(text: str, width: int, indent: str) -> list[str]:
    lines: list[str] = []
    for para in text.splitlines() or [""]:
        if not para.strip():
            lines.append(indent.rstrip())
            continue
        lines.extend(
            textwrap.wrap(para, width=width, initial_indent=indent, subsequent_indent=indent)
        )
    return lines


def _conditions_line(meta: dict | None, n: int) -> str:
    if meta is None:
        return f"{n} trials, conditions file missing (recording incomplete?)"
    host = urlparse(meta["endpoint"]).netloc or meta["endpoint"]
    temp = "default" if meta.get("temperature") is None else f"{meta['temperature']:g}"
    date = meta["recorded_at"][:10]
    return f"{meta['model']} via {host}, recorded {date}, {n} trials, temperature {temp}"


def render_transcript(
    scenario: Scenario,
    rows: list[dict],
    meta: dict | None,
    results: Sequence[LintResult],
    trial: int,
    width: int,
    answer_lines: int | None,
    index: str = "",
) -> str:
    row = next((r for r in rows if r["trial"] == trial), None)
    if row is None:
        raise IndexError(f"trial {trial} not in fixtures for {scenario.id}")
    result = next(r for r in results if r.trial == trial)
    out: list[str] = []
    header = f"-- {index}{scenario.title} "
    out.append(header + "-" * max(0, width - len(header)))
    out.append("")
    out.extend(_field("Prompt ", scenario.prompt, width))
    out.extend(_field("Model  ", _conditions_line(meta, len(rows)), width))
    out.append("")
    body = _wrap(row["content"].strip(), width, "  ")
    shown = body if answer_lines is None else body[:answer_lines]
    out.append(f"Answer (trial {trial}):")
    out.extend(shown)
    if len(shown) < len(body):
        out.append(f"  [... {len(body) - len(shown)} more lines; run without --answer-lines]")
    out.append("")
    if result.claim is not None:
        args = ", ".join(f"{k}={_fmt_num(v)}" for k, v in scenario.fixed_args.items())
        claim_txt = format_quantity(result.claim, scenario.claim_unit)
        out.append(f"Claim  : {claim_txt}  ({result.note})")
        call = f"physbound {scenario.tool}({args}, {scenario.claim_arg}={_fmt_num(result.claim)})"
        out.extend(_field("Check  ", call, width))
    else:
        out.append("Claim  : none extracted")
    out.append("")
    for line in result.verdict_lines():
        indent = "  " + " " * (len(line) - len(line.lstrip()))
        out.extend(
            textwrap.wrap(
                line.strip(), width=width, initial_indent=indent, subsequent_indent=indent + "  "
            )
        )
    out.append("")
    out.append(_aggregate_line(results))
    return "\n".join(out)


def _aggregate_line(results: Sequence[LintResult]) -> str:
    c = tally(results)
    n = len(results)
    return (
        f"Across {n} trials: {c[OUTCOME_VIOLATION]} physics violations, "
        f"{c[OUTCOME_WARNING]} valid with warnings, {c[OUTCOME_VALID]} valid, "
        f"{c[OUTCOME_UNPARSEABLE]} unparseable"
    )


def render_trial_list(scenario: Scenario, results: Sequence[LintResult]) -> str:
    lines = []
    for r in results:
        claim = "-" if r.claim is None else format_quantity(r.claim, scenario.claim_unit)
        lines.append(f"  trial {r.trial:>2}  {r.outcome:<20} {claim:<14} {r.note}")
    return "\n".join(lines)


def render_summary(rows_by_scenario: dict[str, tuple[Scenario, list[dict], dict | None]]) -> str:
    head = f"{'scenario':<22} {'model':<28} {'n':>3} {'viol':>5} {'warn':>5} {'ok':>4} {'unp':>4}"
    lines = [head, "-" * len(head)]
    for sid, (scenario, rows, meta) in rows_by_scenario.items():
        c = tally(lint_all(scenario, rows))
        model = (meta or {}).get("model", "?")
        lines.append(
            f"{sid:<22} {model[:28]:<28} {len(rows):>3} {c[OUTCOME_VIOLATION]:>5} "
            f"{c[OUTCOME_WARNING]:>5} {c[OUTCOME_VALID]:>4} {c[OUTCOME_UNPARSEABLE]:>4}"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Ask a real LLM an RF question, then lint its answer with physbound.",
    )
    parser.add_argument(
        "--scenarios-file", type=Path, default=DEFAULT_SCENARIOS, help="scenario definitions"
    )
    parser.add_argument(
        "--fixtures-dir", type=Path, default=DEFAULT_FIXTURES, help="recorded responses"
    )
    sub = parser.add_subparsers(dest="mode")

    rec = sub.add_parser("record", help="call a model N times per scenario and store responses")
    rec.add_argument(
        "--endpoint",
        default=os.environ.get("PHYSBOUND_LLM_ENDPOINT", DEFAULT_ENDPOINT),
        help="OpenAI-compatible base URL (default: $PHYSBOUND_LLM_ENDPOINT or Ollama local)",
    )
    rec.add_argument(
        "--model",
        default=os.environ.get("PHYSBOUND_LLM_MODEL"),
        help="model name as the endpoint knows it (default: $PHYSBOUND_LLM_MODEL)",
    )
    rec.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="environment variable holding the bearer token (default: OPENAI_API_KEY)",
    )
    rec.add_argument("--trials", type=int, default=20, help="responses per scenario (default 20)")
    rec.add_argument(
        "--temperature", type=float, default=None, help="sampling temperature (default: omitted)"
    )
    rec.add_argument("--max-tokens", type=int, default=400, help="completion cap (default 400)")
    rec.add_argument("--system", default=None, help="optional system prompt (default: none)")
    rec.add_argument("--pause", type=float, default=0.0, help="seconds between calls")
    rec.add_argument("--timeout", type=float, default=120.0, help="per-call timeout in seconds")
    rec.add_argument("--scenario", action="append", help="record only this scenario id")

    rep = sub.add_parser("replay", help="lint recorded responses (default mode)")
    rep.add_argument("--scenario", action="append", help="replay only this scenario id")
    rep.add_argument("--trial", type=int, default=0, help="which trial to show (default 0)")
    rep.add_argument("--width", type=int, default=96, help="wrap width")
    rep.add_argument(
        "--answer-lines", type=int, default=None, help="truncate the shown answer (default: all)"
    )
    rep.add_argument("--list", action="store_true", help="also list every trial's outcome")

    sub.add_parser("summary", help="outcome counts across all recorded scenarios")
    return parser


def _select(scenarios: list[Scenario], ids: list[str] | None) -> list[Scenario]:
    if not ids:
        return scenarios
    by_id = {s.id: s for s in scenarios}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"unknown scenario id(s): {', '.join(missing)}")
    return [by_id[i] for i in ids]


def _run_record(args: argparse.Namespace, scenarios: list[Scenario]) -> int:
    if not args.model:
        print("record: --model (or $PHYSBOUND_LLM_MODEL) is required", file=sys.stderr)
        return 2
    api_key = os.environ.get(args.api_key_env)
    host = urlparse(args.endpoint).hostname or ""
    if not api_key and host not in ("localhost", "127.0.0.1", "::1"):
        print(
            f"record: ${args.api_key_env} is not set and {host!r} is not local; "
            "set the key or pass --api-key-env",
            file=sys.stderr,
        )
        return 2
    client = ChatClient(args.endpoint, args.model, api_key, args.timeout)
    print(f"Recording {args.trials} trials per scenario from {args.model} at {client.endpoint}")
    try:
        for scenario in _select(scenarios, args.scenario):
            rows_path, meta_path = record_scenario(
                scenario,
                client,
                args.fixtures_dir,
                trials=args.trials,
                system=args.system,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                pause_s=args.pause,
            )
            print(f"  wrote {rows_path.name} and {meta_path.name}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        print(f"record: HTTP {exc.code} from endpoint: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"record: cannot reach endpoint: {exc.reason}", file=sys.stderr)
        return 1
    return 0


def _missing_fixture_message(scenario: Scenario, fixtures_dir: Path) -> str:
    rows_path, _ = fixture_paths(fixtures_dir, scenario.id)
    return (
        f"no recording for {scenario.id!r} ({rows_path}). Record one with:\n"
        f"  uv run python demo/llm/run.py record --model <name> --scenario {scenario.id}"
    )


def _run_replay(args: argparse.Namespace, scenarios: list[Scenario]) -> int:
    selected = _select(scenarios, args.scenario)
    status = 0
    blocks: list[str] = []
    for i, scenario in enumerate(selected, start=1):
        try:
            rows, meta = load_fixture(args.fixtures_dir, scenario.id)
        except FileNotFoundError:
            print(_missing_fixture_message(scenario, args.fixtures_dir), file=sys.stderr)
            status = 1
            continue
        if not rows:
            print(f"replay: {scenario.id} has an empty recording", file=sys.stderr)
            status = 1
            continue
        results = lint_all(scenario, rows)
        index = f"{i}/{len(selected)}: " if len(selected) > 1 else ""
        try:
            block = render_transcript(
                scenario, rows, meta, results, args.trial, args.width, args.answer_lines, index
            )
        except IndexError as exc:
            print(f"replay: {exc}", file=sys.stderr)
            status = 1
            continue
        if args.list:
            block += "\n\n" + render_trial_list(scenario, results)
        blocks.append(block)
    print("\n\n".join(blocks))
    return status


def _run_summary(args: argparse.Namespace, scenarios: list[Scenario]) -> int:
    recorded: dict[str, tuple[Scenario, list[dict], dict | None]] = {}
    for scenario in scenarios:
        try:
            rows, meta = load_fixture(args.fixtures_dir, scenario.id)
        except FileNotFoundError:
            continue
        if rows:
            recorded[scenario.id] = (scenario, rows, meta)
    if not recorded:
        print("summary: no recordings found; run `record` first", file=sys.stderr)
        return 1
    print(render_summary(recorded))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    scenarios = load_scenarios(args.scenarios_file)
    if args.mode == "record":
        return _run_record(args, scenarios)
    if args.mode == "summary":
        return _run_summary(args, scenarios)
    if args.mode is None:
        raw = list(argv) if argv is not None else sys.argv[1:]
        args = parser.parse_args([*raw, "replay"])
    return _run_replay(args, scenarios)


if __name__ == "__main__":
    sys.exit(main())
