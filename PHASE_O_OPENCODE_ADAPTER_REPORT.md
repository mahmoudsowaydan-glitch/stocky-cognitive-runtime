# Phase O — OpenCode Adapter Foundation

## Goal

Create the first host adapter for Stocky Engineering OS, connecting a real development environment to the Runtime through the Gateway contract layer — without modifying runtime internals.

## Architecture

```
OpenCode (real repository)
    │
    ▼
OpenCodeAdapter
    │  WorkspaceSnapshot + EditorEvent → SubmitEventDTO
    ▼
LocalRuntimeGateway
    │  ReceiptDTO + PublicTraceDTO
    ▼
RuntimeDaemon → RuntimeLoop → Sandbox → Capability
```

## Deliverables

| Component | File | Status |
|-----------|------|--------|
| WorkspaceSnapshot DTO | `cognitive_runtime/adapters/opencode/workspace_snapshot.py` | ✅ |
| EditorEvent DTO | `cognitive_runtime/adapters/opencode/editor_event.py` | ✅ |
| OpenCodeAdapter | `cognitive_runtime/adapters/opencode/opencode_adapter.py` | ✅ |
| Package exports | `cognitive_runtime/adapters/opencode/__init__.py` | ✅ |
| Unit tests (33) | `tests/adapters/opencode/test_*.py` | ✅ |
| E2E test (ADAPTER-E2E-001) | `tests/adapters/opencode/test_real_repository_adapter_flow.py` | ✅ |
| Invariant ADAPTER-ISOLATION-001 | `INVARIANTS.md` | ✅ |

## Design Decisions

### 1. Capability Mapping (Existing Only)

| Editor Event | Runtime Action | Capability |
|---|---|---|
| REPOSITORY_OPENED | `analyze` | filesystem.read |
| FILE_OPENED | `analyze` | filesystem.read |
| FILE_SAVED | `analyze` | filesystem.read |
| FILE_CLOSED | `analyze` | filesystem.read |
| BRANCH_SWITCHED | `analyze` | filesystem.read |
| SELECTION_CHANGED | `search` | filesystem.read |
| CURSOR_MOVED | (not submitted) | — |

No new capabilities were added. Phase O validates the adapter pattern, not capability expansion.

### 2. Poll Model (Not Async/Await)

```python
adapter.poll_result(receipt_id, max_attempts=50) → Optional[PublicTraceDTO]
```

Consistent with the existing Async Receipt Model used by Gateway. No Futures or Awaitable integration.

### 3. No Git Integration

`WorkspaceSnapshot.git_branch` excluded by design. Phase O is a **Host Adapter**, not a Git integration.

## Invariant: ADAPTER-ISOLATION-001

> Adapters may observe hosts and translate events but may never access RuntimeLoop, P4, GovernanceEngine, SandboxPool, TelemetryStore, IntelligenceStore, RecoveryCoordinator, or any runtime internal — gateway contracts only.

Enforced in tests via `TestADAPTER_ISOLATION_001`:
- No `_loop`, `_p4`, `_daemon`, `_runtime`, `_sandbox`, `_governance`, `_recovery`, `_telemetry`, or `_intelligence` attributes on adapter
- Gateway-only method calls verified
- Public interface limited to: `capture_workspace`, `submit_editor_event`, `submit_analyze`, `submit_search`, `get_result`, `get_status`, `poll_result`

## E2E Validation: ADAPTER-E2E-001

```python
test_adapter_e2e_001_real_repository_flow  ✓ PASSED  (2.23s)
```

Full pipeline executed on Stocky Engineering OS repository:

1. **WorkspaceSnapshot.capture(".")** → `root_path=<abs_path>`, `collected_at=timestamp`
2. **adapter.submit_analyze(root_path)** → `ReceiptDTO(receipt_id, event_id)`
3. **Runtime processes** via real EventQueue → P3 → Preflight → P4 → Sandbox → Trace
4. **adapter.poll_result(receipt_id)** → `PublicTraceDTO(event_id, status="ALLOW", total_time_ms≥0)`
5. **No internal leakage**: no `p4_verdict`, `preflight_valid`, or `governance_score`
6. **Daemon lifecycle preserved**: `RUNNING` throughout

## Not Included (Phase O)

- ❌ Desktop Shell
- ❌ VSCode Extension
- ❌ Multi IDE support
- ❌ Federation
- ❌ Networking / Cloud
- ❌ AI Coding Assistant
- ❌ New Capabilities
- ❌ Git integration
- ❌ CURSOR_MOVED event submission

## Files Created

| Path | Lines |
|------|-------|
| `cognitive_runtime/adapters/__init__.py` | 0 |
| `cognitive_runtime/adapters/opencode/__init__.py` | 8 |
| `cognitive_runtime/adapters/opencode/workspace_snapshot.py` | 31 |
| `cognitive_runtime/adapters/opencode/editor_event.py` | 53 |
| `cognitive_runtime/adapters/opencode/opencode_adapter.py` | 73 |
| `tests/adapters/__init__.py` | 0 |
| `tests/adapters/opencode/__init__.py` | 0 |
| `tests/adapters/opencode/test_workspace_snapshot.py` | 59 |
| `tests/adapters/opencode/test_editor_event.py` | 109 |
| `tests/adapters/opencode/test_opencode_adapter.py` | 151 |
| `tests/adapters/opencode/test_real_repository_adapter_flow.py` | 106 |

**Total: 11 files, ~590 lines**

## Modified Files

| Path | Change |
|------|--------|
| `INVARIANTS.md` | Added ADAPTER-ISOLATION-001 (Architecture Boundaries section) |

## Test Summary

| Suite | Tests | Status |
|-------|-------|--------|
| test_workspace_snapshot.py | 7 | ✅ PASS |
| test_editor_event.py | 12 | ✅ PASS |
| test_opencode_adapter.py | 14 | ✅ PASS |
| test_real_repository_adapter_flow.py | 1 | ✅ PASS (2.23s) |

**Phase O — Complete.** 🚀
