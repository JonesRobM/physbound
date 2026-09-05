# PhysBound LLM demo

A real language model is asked an RF engineering question. Its answer is
linted by the same physbound tool functions the MCP server and CLI use. The
demo only *reports*; it does not correct the model. The point is to show, with
evidence rather than a hand-picked screenshot, that models produce numbers that
violate hard physical limits and that physbound catches them.

## How it works

Each entry in `scenarios.json` fixes every input of one physbound tool except a
single claim. For example the Wi-Fi scenario fixes a 20 MHz channel and 15 dB
SNR and leaves the throughput as the model's claim. The harness:

1. Sends the scenario prompt to a model `N` times (`record`).
2. Stores every response verbatim in `fixtures/<scenario>.jsonl`.
3. Extracts the one number with a unit from each response using a
   deterministic unit-aware parser. No second model is involved in judging.
4. Calls the physbound tool with the fixed inputs plus the extracted claim.
5. Reports one transcript and the outcome counts across all trials (`replay`).

Outcomes are `violation` (the tool returned a `PhysicalViolationError`),
`valid_with_warnings` (the tool accepted the claim but attached a caveat about
it, such as an unusually high implied aperture efficiency), `valid`, or
`unparseable`. Methodology notes the tool emits regardless of the claim, such
as which beamwidth rule of thumb it used, are shown as notes and do not change
the outcome. A response is unparseable when it gives a range, several different
values, or no value in the expected unit. Those are counted and shown, not
dropped.

## Honesty policy

- **Nothing is edited after recording.** The response file is written during
  the run and its SHA-256 is stored in the `.meta.json` conditions file.
- **No cherry-picking.** `replay` shows trial 0 by default. `--trial N` shows
  another, and `--list` prints every trial's claim and outcome.
- **Conditions are data, not prose.** `.meta.json` records the model, endpoint,
  exact prompt sent (including the format suffix), system prompt, temperature,
  max tokens, trial count, timestamp, physbound version and response hash.
- **The prompt constrains format, not physics.** Every prompt ends with a
  request to finish with `ANSWER: <number> <unit>`. This is so extraction is
  reliable; it does not hint at the right answer. The full prompt is in the
  conditions file.

Whatever hit rate the model produces is what gets shown, including a model that
gets it right every time.

## Replaying (no key, no network)

From the repository root, after `uv sync`:

```bash
uv run python demo/llm/run.py                      # all scenarios, trial 0
uv run python demo/llm/run.py replay --scenario wifi-throughput --trial 3 --list
uv run python demo/llm/run.py summary              # outcome counts per scenario
```

`replay` exits 1 if a scenario has no recording, and tells you how to make one.

## Recording

`record` talks to any OpenAI-compatible chat-completions endpoint using only the
Python standard library, so there is nothing extra to install. Three free or
near-free options:

**Local model with Ollama** (free, no key):

```bash
ollama pull <model>
uv run python demo/llm/run.py record --model <model> --trials 20
```

The default endpoint is Ollama's local server. Local models are the most
reproducible option because anyone can pull the same model tag.

**OpenRouter** (has free-tier models, needs a key):

```bash
export OPENROUTER_API_KEY=...
uv run python demo/llm/run.py record \
  --endpoint https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
  --model <provider/model> --trials 20
```

**OpenAI or any other compatible provider**:

```bash
export OPENAI_API_KEY=...
uv run python demo/llm/run.py record --endpoint https://api.openai.com/v1 \
  --model <model> --trials 20
```

Useful flags: `--temperature` (omitted from the request unless given, so the
provider default applies and is recorded as `null`), `--system` for an optional
system prompt (default none), `--pause` seconds between calls, and `--scenario`
to record a single scenario.

Recording overwrites that scenario's fixture and conditions files. Commit both
so replay works for everyone.

## Rendering the GIF

```bash
vhs demo/llm/demo.tape
```

The tape runs `replay` with `--answer-lines 8`, which truncates long answers on
screen and says so. The full answer is always in the fixture file.

## Files

| Path | Purpose |
|------|---------|
| `run.py` | The harness: `record`, `replay`, `summary` |
| `scenarios.json` | Prompts, fixed tool inputs, and which argument the claim fills |
| `fixtures/<id>.jsonl` | One JSON row per trial: verbatim content, finish reason, token usage, latency |
| `fixtures/<id>.meta.json` | Recording conditions and the SHA-256 of the response file |
| `demo.tape` | VHS script that renders `physbound-llm-demo.gif` from replay mode |
