# CLI

!!! info "Availability"
    The `physbound check` CLI is available from **v0.3.0**.

Beyond the MCP server, PhysBound ships a command-line interface for validating physics claims from the terminal or from CI pipelines:

```
physbound check <tool> [options]
```

- `<tool>` selects the validator (e.g. `shannon`).
- Options are kebab-case flags mirroring the MCP tool inputs (e.g. `--bandwidth-hz`, `--snr-db`). Numeric values accept scientific notation (`20e6`, `500e6`).
- `--json` emits the full structured result (the same payload the MCP tool returns) instead of the human-readable summary.
- **Exit code `0`** when the claim is physically possible; **exit code `1`** when a physical limit is violated — so a violation fails a CI step.

## Example: catching a Shannon violation

Can a 20 MHz channel with 15 dB SNR carry 500 Mbps? No — the Shannon limit is 100.6 Mbps:

```bash
physbound check shannon \
  --bandwidth-hz 20e6 \
  --snr-db 15 \
  --claimed-throughput-bps 500e6
echo $?   # 1 — physics violation
```

The output names the violated law (Shannon–Hartley theorem), the computed capacity limit, the claimed value, and the excess percentage.

Correct the claim and the same command passes:

```bash
physbound check shannon \
  --bandwidth-hz 20e6 \
  --snr-db 15 \
  --claimed-throughput-bps 100e6
echo $?   # 0 — within the Shannon limit
```

## Machine-readable output

Add `--json` for the structured result:

```bash
physbound check shannon --bandwidth-hz 20e6 --snr-db 15 \
  --claimed-throughput-bps 500e6 --json
```

Violations are reported as structured `PhysicalViolationError` objects with `law_violated`, `computed_limit`, `claimed_value`, and a LaTeX explanation — identical to the MCP responses.

## Use in CI

Because violations exit non-zero, `physbound check` can gate an engineering pipeline:

```yaml
- name: Validate link claims
  run: |
    physbound check shannon --bandwidth-hz 20e6 --snr-db 15 \
      --claimed-throughput-bps 100e6
```

## Full flag reference

Run `physbound check <tool> --help` for the complete, authoritative flag list of each validator. The tools and their inputs correspond one-to-one with the MCP tools documented in the [Formula Reference](formulas.md).
