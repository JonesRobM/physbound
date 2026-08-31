# Security Policy

## Supported Versions

PhysBound is pre-1.0 software. Only the latest 0.x release receives security fixes.

| Version | Supported |
|---------|-----------|
| Latest 0.x release | Yes |
| Older releases | No |

## Reporting a Vulnerability

Please report vulnerabilities privately via **GitHub Security Advisories**:
[https://github.com/JonesRobM/physbound/security/advisories/new](https://github.com/JonesRobM/physbound/security/advisories/new)

Do **not** open a public issue for a security problem.

You can expect an initial response within **7 days**. If the report is confirmed, a fix will be developed privately and released with credit to the reporter (unless you prefer to remain anonymous), followed by public disclosure through the advisory.

## Scope

PhysBound is a deliberately small attack surface: it is a physics calculator exposed as a **stdio MCP server**. It

- opens no network sockets (transport is stdin/stdout only),
- executes no shell commands and evaluates no user-supplied code,
- reads and writes no files at runtime,
- performs deterministic numerical computation on validated (Pydantic) inputs.

Reports most likely to be relevant are therefore input-validation flaws (e.g. inputs that crash the server or bypass Pydantic validation), denial-of-service via pathological numeric inputs, or vulnerabilities in the dependency chain (FastMCP, SciPy, NumPy, Pint, Pydantic). Incorrect physics results are quality bugs, not security issues — please report those as ordinary [bug reports](https://github.com/JonesRobM/physbound/issues).
