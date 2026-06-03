# System Invariants

## Memory Bounds

| ID | Rule | Status |
|----|------|--------|
| MEM-BOUND-001 | `trace_window.MAX_ARCHIVED_SEGMENTS = 100` | Active |
| MEM-BOUND-002 | `telemetry_store.WARM_MAX = 500` | Active |
| MEM-BOUND-003 | `panic_detector.MAX_EVENTS = 1000` | Active |
| MEM-BOUND-004 | `pattern_miner.MAX_SEEN_SIGNATURES = 100000` | Active |
| MEM-BOUND-005 | `failure_signature.MAX_SEEN_CHAINS = 50000` | Active |
| MEM-BOUND-006 | `decision_fingerprint.MAX_SEEN_HASHES = 50000` | Active |
| MEM-BOUND-007 | `event_queue.MAX_DEAD_LETTER = 1000` | Active |

## Runtime Daemon

| ID | Rule | Status |
|----|------|--------|
| DAEMON-STATE-001 | Lifecycle transitions guarded by `LifecycleTransition.assert_transition` | Active |
| DAEMON-OWNERSHIP-001 | Daemon owns RuntimeLoop exclusively (composition, not sharing) | Active |
| DAEMON-STATUS-001 | `RuntimeStatus` is frozen dataclass (immutable once constructed) | Active |
| RECOVERY-AUTH-001 | Only daemon may initiate recovery; no direct recovery from pipeline | Active |

## External Contracts

| ID | Rule | Status |
|----|------|--------|
| CONTRACT-LEAK-001 | No contract may expose RuntimeLoop, RuntimeDaemon, RecoveryCoordinator, P4, GovernanceEngine, TelemetryStore, IntelligenceStore — DTO/Snapshot/Receipt/ViewModel only | Active |
| GATEWAY-IMMUTABILITY-001 | Gateway must not retain correlation state, pending futures map (unless explicitly bounded), execution cache, session memory | Active |

## Console

| ID | Rule | Status |
|----|------|--------|
| CONSOLE-LEAK-001 | Console must never expose P4 reasoning, internal trace data, telemetry metrics, governance scores, runtime internal objects — only DTOs allowed | Active |
| CONSOLE-IMMUTABILITY-001 | Console does not modify runtime state except via submit_event and lifecycle status requests | Active |
| CONSOLE-RENDER-001 | Console rendering must be deterministic, pure function (DTO → string), no conditional intelligence formatting | Active |

## Pipeline Integrity

| ID | Rule | Status |
|----|------|--------|
| FIRST-BOOT-SAFETY-001 | External event must NOT modify architecture, runtime structure, governance logic, P4 rules, or execution pipeline | Active |
| REAL-WORKLOAD-ISOLATION-001 | Real event execution must be fully isolated from system self-modification, deterministic across runs, replayable without divergence | Active |
| NO-INTERNAL-LEAK-001 | No internal system components (P3, P4, Sandbox internals, Telemetry store, Governance engine, Recovery coordinator) may appear in output — only DTOs allowed | Active |
| PIPELINE-COMPLETENESS-001 | Event must traverse full pipeline (submit_event → P3 → Preflight → P4 → Sandbox → Trace → DTO) — any shortcut or bypass = FAILURE | Active |

## Workload Validation

| ID | Rule | Status |
|----|------|--------|
| PUBLIC-REPO-BOUNDARY-001 | No file in public GitHub package may contain runtime internal references, cognitive reasoning structures, debugging-only artifacts, or architectural evolution notes | Active |
| LOAD-STABILITY-001 | 1000+ events executed without system panic, memory violation, or architectural drift | Active |
| DETERMINISM-001 | Same input → same pipeline behavior + same DTO structure + same decision outcome (internal UUIDs excluded from determinism contract) | Active |
| REAL-WORKLOAD-ENDURANCE-001 | Runtime must process sustained workloads (1000+ events) without architectural degradation, lifecycle corruption, or invariant violations | Active |

## Architecture Boundaries

| ID | Rule | Status |
|----|------|--------|
| LEGACY-BOUNDARY-001 | Any module not part of the active runtime graph must reside under /legacy and must not be imported by runtime, gateway, contracts, console, or capabilities | Active |
| CAPABILITY-ISOLATION-001 | Capability providers are execution workers only — they do work and return dicts; they must NOT influence P4, governance, daemon lifecycle, or runtime state | Active |
| INTERNAL-BOUNDARY-001 | Internal engineering tooling must reside under `.internal/` and must not participate in the active runtime graph | Active |
