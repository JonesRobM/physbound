# PhysBound CLI demo — catching a Shannon-Hartley violation.
# Render from the repo root with:  vhs demo/demo.tape
# Requires: vhs (https://github.com/charmbracelet/vhs) and the physbound
# CLI on PATH (`uv sync --all-extras` / `pip install physbound`, v0.3.0+).

Output demo/physbound-demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 650
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms

# --- An impossible claim: 500 Mbps through a 20 MHz channel at 15 dB SNR ---
Type "# Can a 20 MHz channel with 15 dB SNR really carry 500 Mbps?"
Enter
Sleep 1s

Type "physbound check shannon --bandwidth-hz 20e6 --snr-db 15 --claimed-throughput-bps 500e6"
Sleep 500ms
Enter
Sleep 3.5s

Type "echo exit code: $?"
Enter
Sleep 2s

# --- The corrected claim passes: Shannon limit here is 100.6 Mbps ---
Type "# No — the Shannon limit is 100.6 Mbps. A 100 Mbps claim is fine:"
Enter
Sleep 1s

Type "physbound check shannon --bandwidth-hz 20e6 --snr-db 15 --claimed-throughput-bps 100e6"
Sleep 500ms
Enter
Sleep 3.5s

Type "echo exit code: $?"
Enter
Sleep 4s
