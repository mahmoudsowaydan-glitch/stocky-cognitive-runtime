# Stocky Engineering OS

Stocky Engineering OS is a **self-observing cognitive runtime system** — a deterministic execution engine that processes events through a governed pipeline, records decisions as traces, and exposes only sanitized DTOs externally. It is not an IDE, a framework, or an agent platform. It is a runtime architecture.

## Architecture

```
Console (CLI)
  │  status, submit_event, show_result, show_trace
  ▼
Gateway (Stateless)
  │  RuntimeAPI, ExecutionAPI, ObservationAPI, AgentAPI
  ▼
RuntimeDaemon (Lifecycle Host)
  │  STOPPED → BOOTING → RUNNING ↔ PAUSED → RECOVERING → SHUTDOWN
  ▼
RuntimeLoop (Pipeline)
  P3 → Preflight → P4 → Sandbox → CapabilityRegistry → Trace → DTO
```

Every event traverses the full pipeline: submit → P3 (proposal) → Preflight (validity) → P4 (authority) → Sandbox (execution) → Capabilities (work) → Trace (recording) → DTO (sanitized output). The pipeline is deterministic — same input always produces the same behavior, structure, and decision.

## Quick Start

Requires Python 3.12+. No external dependencies.

```sh
python -m cognitive_runtime.console.main status
python -m cognitive_runtime.console.main submit_event analyze_repository '{"target": ".", "risk_score": 0.1}'
python -m cognitive_runtime.console.main show_result <receipt_id>
python -m cognitive_runtime.console.main show_trace <event_id>
```

Run tests:

```sh
python -m pytest
```

## What It Is Not

- Not an IDE — no editor, no debugger, no language server
- Not a framework — no web server, no routing, no ORM
- Not an agent platform — no agent lifecycle management, no multi-agent orchestration
- Not a database — no persistent query engine, no schema migrations

Stocky Engineering OS is a **runtime kernel** that brings deterministic governance and observation to event-driven engineering workflows.

## License

MIT
