# PhysBound demo recording

`demo.tape` is a [charmbracelet/VHS](https://github.com/charmbracelet/vhs) script that records `demo/physbound-demo.gif`: the `physbound check shannon` CLI rejecting a 500 Mbps claim on a 20 MHz / 15 dB SNR channel (Shannon limit: 100.6 Mbps, exit code 1), then accepting the corrected 100 Mbps claim (exit code 0).

Render it from the repository root (requires `vhs` and the `physbound` CLI, v0.3.0+, on PATH):

```bash
vhs demo/demo.tape
```

## LLM demo

`llm/` holds a second demo: a real language model is asked an RF question, every
response is recorded verbatim, and each answer is linted by physbound. See
[`llm/README.md`](llm/README.md) for the method, the honesty policy, and how to
record and replay. Render with `vhs demo/llm/demo.tape`.
