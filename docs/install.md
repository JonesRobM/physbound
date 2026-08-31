# Installation

PhysBound is a standard stdio MCP server published on [PyPI](https://pypi.org/project/physbound/). The recommended launch command is [`uvx physbound`](https://docs.astral.sh/uv/), which fetches and runs the latest release in an isolated environment — no manual install step.

!!! note "First run"
    `uvx` downloads ~60 MB of dependencies (SciPy, NumPy) the first time. Run `uvx physbound` once in a terminal to pre-cache them (Ctrl-C to exit); subsequent starts are instant.

## Claude Code

```bash
claude mcp add physbound -- uvx physbound
```

## Claude Desktop

Add to `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "physbound": {
      "command": "uvx",
      "args": ["physbound"]
    }
  }
}
```

## Cursor, Windsurf, and other MCP clients

Use the same JSON server entry as above in your client's MCP configuration file:

| Client | Configuration file |
|--------|--------------------|
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |

Any other MCP-compatible client works the same way: register a stdio server with command `uvx` and arguments `["physbound"]`.

## Without uv

If you prefer a plain Python install (requires Python 3.12+):

```bash
pip install physbound
```

then set `"command": "physbound"` (with no `args`) in the client configuration.

## Verify the connection

Once configured, ask your assistant an RF question — *"Can a 20 MHz channel with 15 dB SNR support 500 Mbps?"* — and it will answer with physics-validated numbers (in this case: no, the Shannon limit is 100.6 Mbps).

You can also validate claims directly from the terminal — see the [CLI](cli.md).
