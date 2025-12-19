# Codex CLI (codex provider)

This document describes how to use **Codex CLI** via CAO's `codex` provider.

> Note: The `codex` provider is an optional provider. If your installed CAO build/branch does not include it, the commands below will fail until the provider is available.

## Overview

When using `--provider codex`, CAO runs agent sessions inside tmux and drives them through the **Codex CLI** executable (`codex`).

Common use cases:

- Code generation / refactors with a CLI-driven agent
- Supervisor/worker workflows where the supervisor delegates implementation to a worker and optionally requests a review

## Prerequisites

1. **CAO server running**

```bash
cao-server
```

2. **Codex CLI installed and authenticated**

- Ensure the `codex` command is available in your `PATH`.
- Configure authentication as required by Codex CLI (for example, `OPENAI_API_KEY`).

## Provider selection

You can select the provider in both installation and launch.

### Install agents for `codex`

```bash
cao install developer --provider codex
cao install reviewer --provider codex
cao install code_supervisor --provider codex
```

### Launch an agent with `codex`

```bash
cao launch --agents code_supervisor --provider codex
```

## API reference (provider parameter)

CAO exposes an HTTP API (default base URL: `http://localhost:9889`). To select Codex CLI, pass `provider=codex`.

Example:

```http
POST /sessions?agent_profile=developer&provider=codex
```

For the full API surface, see [docs/api.md](api.md).

## Example: Supervisor / Worker workflow

See [examples/codex-cli](../examples/codex-cli) for a runnable supervisor/worker example that demonstrates:

- A supervisor agent delegating implementation work to a worker agent
- Optional review pass by a reviewer agent
- Using CAO MCP tools (`handoff`, `assign`, `send_message`) for orchestration
