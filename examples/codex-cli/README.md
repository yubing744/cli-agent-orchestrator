# Codex CLI Example (Supervisor / Worker)

This example demonstrates a simple **supervisor/worker** workflow using CAO with the `codex` provider.

## Prerequisites

1. Start the CAO server:

```bash
cao-server
```

2. Ensure Codex CLI is installed and authenticated on your machine (the `codex` command must work).

## Setup

Install the example agent profiles for the `codex` provider:

```bash
cao install examples/codex-cli/supervisor.md --provider codex
cao install examples/codex-cli/worker.md --provider codex
cao install examples/codex-cli/reviewer.md --provider codex
```

## Run

Launch the supervisor:

```bash
cao launch --agents codex_supervisor --provider codex
```

In the supervisor terminal, paste a concrete task, for example:

```
Add a small feature with minimal diff and include tests.
```

The supervisor will:

1. Handoff implementation to `codex_worker`
2. Handoff review to `codex_reviewer`
3. Iterate until the reviewer approves
