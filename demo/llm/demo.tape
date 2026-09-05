# PhysBound LLM demo — a real model's answers, linted by physbound.
# Render from the repo root with:  vhs demo/llm/demo.tape
# Requires: vhs, `uv sync`, and recorded fixtures in demo/llm/fixtures/
# (see demo/llm/README.md for how they were recorded). Replay mode needs
# no network and no API key.

Output demo/llm/physbound-llm-demo.gif

Set Shell "bash"
Set FontSize 15
Set Width 1200
Set Height 820
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms

Type "# Ask a real LLM an RF question, then lint its answer with physbound."
Enter
Type "# Every response was recorded once, unedited; trial 0 is shown by default."
Enter
Sleep 1.5s

Type "uv run python demo/llm/run.py replay --scenario wifi-throughput --answer-lines 8"
Sleep 500ms
Enter
Sleep 9s

Type "clear"
Enter
Type "uv run python demo/llm/run.py replay --scenario dish-gain --answer-lines 8"
Sleep 500ms
Enter
Sleep 9s

Type "clear"
Enter
Type "# How often does the model get it wrong? Outcome counts across all trials:"
Enter
Type "uv run python demo/llm/run.py summary"
Sleep 500ms
Enter
Sleep 6s
