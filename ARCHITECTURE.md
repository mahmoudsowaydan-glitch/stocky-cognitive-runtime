# Architecture

## System Layers

```
┌──────────────────────────────────────────────────────┐
│                    Console                            │
│  cmd_status / cmd_submit_event                       │
│  cmd_show_result / cmd_show_trace                    │
│  Pure DTO→string rendering (no internal types)       │
├──────────────────────────────────────────────────────┤
│                  Gateway (Stateless)                  │
│  RuntimeAPI   — daemon status, health, version       │
│  ExecutionAPI — submit_event, get_result             │
│  ObservationAPI — get_trace_by_id, list_traces       │
│  AgentAPI     — register_agent, get_agent            │
│  DTO boundary enforced at this layer                 │
├──────────────────────────────────────────────────────┤
│               RuntimeDaemon (Lifecycle Host)          │
│  STOPPED → BOOTING → RUNNING ↔ PAUSED                │
│  → RECOVERING → SHUTDOWN                             │
│  CrashBoundary: classifies + handles crashes          │
│  HeartbeatMonitor: observation-only                   │
├──────────────────────────────────────────────────────┤
│               RuntimeLoop (Pipeline)                  │
│  Stage 1: P3 Context Builder — proposal from event   │
│  Stage 2: Preflight Analyzer — validity gate         │
│  Stage 3: P4 Authority — risk-based ALLOW/BLOCK      │
│  Stage 4: Sandbox Execution — isolated worker        │
│  Stage 5: CapabilityRegistry → provider execution    │
│  Stage 6: Trace Building → PublicTraceDTO            │
└──────────────────────────────────────────────────────┘
```

## Event Processing Pipeline

```
submit_event → HostEvent → EventQueue.push()
  → Daemon pop → P3 (build proposal)
    → PreflightAnalyzer (validity + capability check)
      → P4 Authority (risk-based ALLOW/BLOCK)
        → SandboxPool → ExecutionCell → CapabilityProvider
          → Trace → PublicTraceDTO
```

## Capability Layer

Stateless async providers live in `capabilities/`. Each follows the contract:

```python
async def execute(proposal: ExecutionProposal, decision: PolicyDecision) -> dict
```

Dispatch is handled by `CapabilityRegistry` — an explicit mapping from action
name to worker function (no dynamic imports, no reflection).

| Provider | Action | Description |
|----------|--------|-------------|
| `repository.py` | `analyze` | Scan directory, list entries, count by extension |
| `search.py` | `search` | Glob pattern search, bounded results |
| `count.py` | `count` | Line and file counting |
| `discovery.py` | `discover_tests` | Discover pytest tests, count functions |
| `report.py` | `generate_report` | Walk repo tree, produce architecture overview |

## Public DTO Model

| DTO | Purpose | Fields |
|-----|---------|--------|
| `PublicTraceDTO` | Sanitized execution result | event_id, session_id, status, risk_score, total_time_ms, error, created_at |
| `ReceiptDTO` | Submission confirmation | receipt_id, event_id, correlation_id, submitted_at |
| `DaemonStatusDTO` | Runtime health snapshot | lifecycle, uptime, cycle_count, health, panic_count |
| `HealthDTO` | Health check | status, cycle_count, uptime, panic_count, recovery_count |
| `SubmitEventDTO` | Event submission transport | session_id, source, payload, correlation_id |
| `EventStatusDTO` | Event status query | event_id, status, receipt_id |
| `AgentProfileDTO` | Agent registration | agent_id, name, capability, status, created_at |
| `RegisterAgentDTO` | Agent registration request | name, capability, metadata |
| `PaginatedTracesDTO` | Paginated trace list | traces, next_cursor, total |

## Safety Guarantees

1. **No internal leak**: Public DTOs never expose RuntimeLoop, P4 reasoning,
   telemetry, governance scores, or sandbox internals.
2. **Gateway statelessness**: Gateway retains no execution cache, session
   memory, or correlation state beyond a bounded pending map (MAX_PENDING=1000).
3. **Pipeline completeness**: Every submitted event traverses the full
   P3→Preflight→P4→Sandbox→Trace→DTO pipeline.
4. **Deterministic rendering**: Console output is a pure function of DTO
   state — no adaptive or conditional formatting.
5. **Lifecycle safety**: Daemon state transitions are guarded by
   `LifecycleTransition.assert_transition`.
6. **Capability isolation**: Providers are stateless workers — they return
   `dict` and never influence P4, governance, daemon lifecycle, or runtime state.

## Invariant Map

| Layer | Invariant | Enforcement |
|-------|-----------|-------------|
| Public contracts | CONTRACT-LEAK-001 | DTO field audit + `trace_to_public()` sanitizer |
| Gateway | GATEWAY-IMMUTABILITY-001 | No state beyond `_pending` OrderedDict |
| Console | CONSOLE-LEAK-001 | Console accesses Gateway only |
| Pipeline | PIPELINE-COMPLETENESS-001 | Every event hits all pipeline stages |
| Capability | CAPABILITY-ISOLATION-001 | Providers return `dict` only, no runtime access |
| Memory | MEM-BOUND-001–007 | 7 bounded data structures with LRU eviction |
| Load | LOAD-STABILITY-001 | 1000+ events without architectural drift |
| Legacy | LEGACY-BOUNDARY-001 | Non-runtime modules in `/legacy` |
| Internal | INTERNAL-BOUNDARY-001 | Internal tooling in `.internal/`, never imported by runtime |

## Repository Boundary Model

| Zone | Directory | Purpose |
|------|-----------|---------|
| **Active Runtime** | `cognitive_runtime/`, `tests/`, `contracts/public/` | Core cognitive runtime, gateway, console, capabilities, and their tests |
| **Internal Tooling** | `.internal/` | CI gate, doctrine JSON, archived docs, phase reports, engineering notes (excluded from GitHub release) |
| **Legacy Components** | `legacy/` | Archived modules from pre-Phase-J architecture — not imported by any active runtime code |

## Execution Philosophy

- **Runtime is deterministic** — same input yields same output, always
- **Gateway is stateless** — no cache, no session memory, only a bounded pending map
- **P4 is single authority** — all governance flows through a single risk-based decision layer
- **Sandbox is execution-only** — capability workers run in isolation, never touch runtime state
- **Internal tools never participate in runtime graph** — `.internal/` is strictly CI/documentation
