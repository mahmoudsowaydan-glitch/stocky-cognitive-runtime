# Stocky Engineering OS

## Vision

Stocky Engineering OS is a **Self-Observing Cognitive Runtime System**.
It is not an IDE. It is not a framework. It is a runtime architecture.

## Architecture Model

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

Events flow through a deterministic pipeline: submit → P3 (proposal) → Preflight (validity) → P4 (authority) → Sandbox (execution) → Capabilities (work) → Trace (recording) → DTO (sanitized output).

## Core Guarantees

- **Deterministic execution** — same input always produces same pipeline behavior, DTO structure, and decision outcome
- **P4 single authority** — risk-based ALLOW/BLOCK decisions are the sole governance mechanism
- **Sandbox isolation** — execution cells are isolated from runtime state
- **DTO-only external boundary** — no internal fields (P4 reasoning, telemetry, governance) ever leak to public output
- **Internal tooling isolation** — `.internal/` contains engineering notes and CI tooling, never imported by runtime code
- **Capability providers are stateless** — they return dicts, never influence P4, governance, lifecycle, or runtime state

## Quick Start

```sh
python -m cognitive_runtime.console.main status
python -m cognitive_runtime.console.main submit_event analyze_repository '{"target": ".", "risk_score": 0.1}'
python -m cognitive_runtime.console.main show_result <receipt_id>
python -m cognitive_runtime.console.main show_trace <event_id>
```

Requires Python 3.12+. No external dependencies.

## Status

**v0.1.0-rc1** — Release Candidate. Architecture locked, boundaries enforced, 1872 tests passing.

```sh
python -m pytest
```

## License

MIT
