"""Command-line interface for PhysBound.

Provides the `physbound` console script:

- `physbound` (no arguments) — start the stdio MCP server (backward compatible
  with existing MCP client configurations).
- `physbound --version` — print the package version.
- `physbound serve [--transport {stdio,http}] [--host H] [--port P]` — run the
  MCP server over the chosen transport.
- `physbound check <tool> [flags]` — run one validation tool directly, for use
  in scripts and CI/CD pipelines. Exit code 0 for physically valid results,
  1 for a physics violation, 2 for usage errors.

The `check` subcommands call exactly the same code paths as the MCP tools.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from physbound import __version__
from physbound import server as _server

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2


def _parse_stage(value: str) -> dict[str, float]:
    """Parse a `--stage GAIN_DB:NF_DB` argument into a noise-stage dict."""
    gain_s, sep, nf_s = value.partition(":")
    if not sep:
        raise argparse.ArgumentTypeError(
            f"stage must be GAIN_DB:NF_DB (e.g. 20:1.5), got {value!r}"
        )
    try:
        return {"gain_db": float(gain_s), "noise_figure_db": float(nf_s)}
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"stage must be GAIN_DB:NF_DB with numeric values (e.g. 20:1.5), got {value!r}"
        ) from exc


def _add_check_parser(
    tool_sub: Any,
    name: str,
    tool: Any,
    help_text: str,
    arguments: Sequence[tuple[str, dict[str, Any]]],
) -> None:
    """Register one `physbound check <tool>` subcommand."""
    parser = tool_sub.add_parser(name, help=help_text, description=help_text)
    dests = []
    for flag, options in arguments:
        action = parser.add_argument(flag, **options)
        dests.append(action.dest)
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="print the full result dict as JSON instead of the human-readable summary",
    )
    parser.set_defaults(tool_fn=tool, param_dests=tuple(dests))


def _req(help_text: str) -> dict[str, Any]:
    return {"type": float, "required": True, "help": help_text}


def _opt(help_text: str, default: float | None = None) -> dict[str, Any]:
    return {"type": float, "default": default, "help": help_text}


def build_parser() -> argparse.ArgumentParser:
    """Build the physbound argument parser."""
    parser = argparse.ArgumentParser(
        prog="physbound",
        description=(
            "PhysBound — Physical Layer Linter. With no arguments, starts the stdio MCP server."
        ),
    )
    parser.add_argument("--version", action="version", version=f"physbound {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{serve,check}")

    serve = sub.add_parser("serve", help="run the MCP server", description="Run the MCP server.")
    serve.add_argument(
        "--transport", choices=["stdio", "http"], default="stdio", help="transport protocol"
    )
    serve.add_argument("--host", default="127.0.0.1", help="bind host (http transport only)")
    serve.add_argument("--port", type=int, default=8000, help="bind port (http transport only)")

    check = sub.add_parser(
        "check",
        help="validate a physics claim from the command line",
        description=(
            "Validate a physics claim. Exit code 0: physically valid; "
            "1: physics violation; 2: usage error."
        ),
    )
    tool_sub = check.add_subparsers(dest="tool", required=True, metavar="<tool>")

    _add_check_parser(
        tool_sub,
        "link-budget",
        _server.rf_link_budget,
        "Friis link budget with FSPL and antenna gain limit checks",
        [
            ("--tx-power-dbm", _req("transmit power in dBm")),
            ("--tx-antenna-gain-dbi", _req("TX antenna gain in dBi")),
            ("--rx-antenna-gain-dbi", _req("RX antenna gain in dBi")),
            ("--frequency-hz", _req("carrier frequency in Hz")),
            ("--distance-m", _req("link distance in meters")),
            ("--tx-losses-db", _opt("TX-side losses in dB", 0.0)),
            ("--rx-losses-db", _opt("RX-side losses in dB", 0.0)),
            ("--tx-antenna-diameter-m", _opt("TX antenna diameter in meters")),
            ("--rx-antenna-diameter-m", _opt("RX antenna diameter in meters")),
            ("--aperture-efficiency", _opt("efficiency for the typical-gain warning", 0.55)),
        ],
    )
    _add_check_parser(
        tool_sub,
        "shannon",
        _server.shannon_hartley,
        "Shannon-Hartley channel capacity and throughput claim validation",
        [
            ("--bandwidth-hz", _req("channel bandwidth in Hz")),
            ("--snr-linear", _opt("SNR (linear); provide this OR --snr-db")),
            ("--snr-db", _opt("SNR in dB; provide this OR --snr-linear")),
            ("--claimed-throughput-bps", _opt("throughput claim to validate in bps")),
        ],
    )
    _add_check_parser(
        tool_sub,
        "noise",
        _server.noise_floor,
        "thermal noise floor, Friis noise cascade, receiver sensitivity",
        [
            ("--bandwidth-hz", _req("receiver bandwidth in Hz")),
            ("--temperature-k", _opt("source/antenna noise temperature in K", 290.0)),
            (
                "--stage",
                {
                    "dest": "stages",
                    "action": "append",
                    "type": _parse_stage,
                    "metavar": "GAIN_DB:NF_DB",
                    "help": "receiver stage as GAIN_DB:NF_DB (repeatable, cascade order)",
                },
            ),
            ("--required-snr-db", _opt("required SNR in dB for sensitivity")),
        ],
    )
    _add_check_parser(
        tool_sub,
        "radar-range",
        _server.radar_range,
        "monostatic radar range equation and detection range claims",
        [
            ("--peak-power-w", _req("peak transmit power in W")),
            ("--antenna-gain-dbi", _req("antenna gain in dBi")),
            ("--frequency-hz", _req("operating frequency in Hz")),
            ("--rcs-m2", _req("target radar cross section in m^2")),
            ("--system-noise-temp-k", _opt("system noise temperature in K", 290.0)),
            ("--noise-bandwidth-hz", _opt("receiver noise bandwidth in Hz", 1e6)),
            ("--min-snr-db", _opt("minimum detection SNR in dB", 13.0)),
            ("--claimed-range-m", _opt("claimed detection range to validate in m")),
            (
                "--num-pulses",
                {"type": int, "default": 1, "help": "number of integrated pulses"},
            ),
            ("--losses-db", _opt("total system losses in dB", 0.0)),
        ],
    )
    _add_check_parser(
        tool_sub,
        "antenna",
        _server.antenna_gain,
        "antenna gain limits, beamwidth, far-field distance, gain claims",
        [
            ("--frequency-hz", _req("operating frequency in Hz")),
            ("--diameter-m", _opt("aperture diameter in m; provide this OR --aperture-area-m2")),
            ("--aperture-area-m2", _opt("aperture area in m^2; provide this OR --diameter-m")),
            ("--claimed-gain-dbi", _opt("gain claim to validate in dBi")),
            ("--aperture-efficiency", _opt("efficiency for the typical-gain warning", 0.55)),
        ],
    )
    _add_check_parser(
        tool_sub,
        "radar-ambiguity",
        _server.radar_ambiguity,
        "pulse-Doppler unambiguous range/velocity, Doppler aliasing, resolution",
        [
            ("--frequency-hz", _req("carrier frequency in Hz")),
            ("--prf-hz", _req("pulse repetition frequency in Hz")),
            ("--pulse-width-s", _opt("transmitted pulse width in s")),
            ("--target-velocity-m-s", _opt("target radial velocity in m/s (closing positive)")),
            ("--bandwidth-hz", _opt("compressed bandwidth in Hz")),
            ("--claimed-unambiguous-range-m", _opt("claimed unambiguous range in m")),
            ("--claimed-unambiguous-velocity-m-s", _opt("claimed unambiguous velocity in m/s")),
            ("--claimed-range-resolution-m", _opt("claimed range resolution in m")),
        ],
    )
    return parser


def _print_violation(result: dict[str, Any]) -> None:
    """Print a PhysicalViolationError result dict to stderr."""
    unit = f" {result['unit']}" if result.get("unit") else ""
    print(f"PHYSICS VIOLATION [{result['law_violated']}]", file=sys.stderr)
    print(f"  {result['message']}", file=sys.stderr)
    if result.get("computed_limit") is not None:
        print(f"  Computed limit: {result['computed_limit']:g}{unit}", file=sys.stderr)
    if result.get("claimed_value") is not None:
        print(f"  Claimed value:  {result['claimed_value']:g}{unit}", file=sys.stderr)


def _run_check(args: argparse.Namespace) -> int:
    """Run one `physbound check <tool>` invocation and return its exit code."""
    kwargs = {dest: getattr(args, dest) for dest in args.param_dests}
    try:
        result: dict[str, Any] = args.tool_fn(**kwargs)
    except ValidationError as exc:
        for err in exc.errors():
            print(f"physbound: invalid arguments: {err['msg']}", file=sys.stderr)
        return EXIT_USAGE

    is_violation = bool(result.get("error"))
    if args.as_json:
        print(json.dumps(result, indent=2))
        return EXIT_VIOLATION if is_violation else EXIT_OK
    if is_violation:
        _print_violation(result)
        return EXIT_VIOLATION
    print(result["human_readable"])
    for warning in result.get("warnings", []):
        print(f"warning: {warning}")
    return EXIT_OK


def _run_serve(args: argparse.Namespace) -> int:
    """Run the MCP server over the requested transport."""
    if args.transport == "http":
        _server.mcp.run(transport="http", host=args.host, port=args.port)
    else:
        _server.mcp.run(transport="stdio")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the `physbound` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        # Backward compatible default: plain `physbound` is the stdio MCP server.
        _server.mcp.run(transport="stdio")
        return EXIT_OK
    if args.command == "serve":
        return _run_serve(args)
    return _run_check(args)


if __name__ == "__main__":
    sys.exit(main())
