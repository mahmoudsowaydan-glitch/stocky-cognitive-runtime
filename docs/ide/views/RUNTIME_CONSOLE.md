# Stocky Engineering OS — Runtime Console View v0.1

---

> هذا الملف يحدد **Runtime Console** — view P3 في طائرة التنفيذ: حالة الـ State Machine، الـ Execution Graph الجاري، وتدفق الـ Trace.
>
> This file defines the **Runtime Console** — the P3 view in the Execution Plane: State Machine status, active Execution Graph, and Trace Stream.

---

## Core Content — المحتوى الأساسي

| العنصر | المصدر | Live؟ |
|---|---|---|
| State Machine visualization | P3 RUNTIME_STATE_MACHINE.md | ✅ Live |
| Current state + transitions | P3 State Machine | ✅ Live |
| Execution Graph (active) | P3 EXECUTION_ENGINE.md | ✅ Live |
| Node status (pending/running/done) | P3 Execution Engine | ✅ Live |
| Trace Stream (recent events) | P3 Live Observer | ✅ Live |
| Memory query interface | P3 MEMORY_RECORDING.md | ❌ On-Demand |

---

## State Machine View

### CLI Display
```
┌──────────────────────────────────────────────────┐
│  ⚙️ RUNTIME STATE MACHINE                        │
│                                                  │
│        ┌──────────┐                              │
│        │   IDLE   │                              │
│        └────┬─────┘                              │
│             │ plan_received                       │
│             ▼                                    │
│        ┌──────────┐                              │
│        │ PLANNING │◀──── (recovery)              │
│        └────┬─────┘                              │
│             │ graph_ready                         │
│             ▼                                    │
│     ┌──────────────┐     ⚠️ active               │
│     │  EXECUTING   │◀──── step 4/12              │
│     └──────┬───────┘                             │
│            │ step_complete                        │
│            ▼                                     │
│        ┌──────────┐                              │
│        │VERIFYING │  ● ● ●                       │
│        └──────────┘                              │
│                                                  │
│  Duration: 00:00:07  │  Steps: 4/12  │  ✓ OK    │
└──────────────────────────────────────────────────┘
```

### Web Dashboard Widget
```
┌──────────────────────────────────────────────────────────────────┐
│  Runtime State Machine                            ● EXECUTING   │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────┐  ┌──────┐  ┌──────────┐  ┌────────┐  ┌───────────┐  │
│  │ IDLE │──│PLAN  │─▶│EXECUTING │──│VERIFY  │──│ COMPLETED │  │
│  │  ✓   │  │ ✓    │  │  ACTIVE  │  │        │  │           │  │
│  └──────┘  └──────┘  └──────────┘  └────────┘  └───────────┘  │
│                       │         │                               │
│                       ▼         ▼                               │
│                  ┌────────┐  ┌──────────┐                      │
│                  │RECOVER │  │  FAILED  │                      │
│                  └────────┘  └──────────┘                      │
├──────────────────────────────────────────────────────────────────┤
│  Transitions: 8  │  Duration: 7.2s  │  Stability: 0.94        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Execution Graph View

### CLI Display
```
┌──────────────────────────────────────────────────┐
│  📊 EXECUTION GRAPH  (4/12 nodes)               │
│                                                  │
│  step-001: modify auth.js           ✓  0.8s     │
│  step-002: update imports            ✓  1.2s     │
│  step-003: add middleware            ✓  0.5s     │
│  step-004: update routes            ◉  2.1s     │
│  step-005: add tests                ⏳           │
│  step-006: verify compilation       ⏳           │
├──────────────────────────────────────────────────┤
│  ⚑ Checkpoint: step-001, step-003               │
│  Rollback: sequential-reverse                    │
│  Budget: MEDIUM (5 steps remaining)              │
└──────────────────────────────────────────────────┘
```

### Node Detail (on select)
```
┌──────────────────────────────────────────────────┐
│  STEP: step-004                                  │
├──────────────────────────────────────────────────┤
│  Action:     update routes                       │
│  File:       src/routes/auth.js                  │
│  Status:     RUNNING (2.1s)                      │
│  Pre-check:  ✓ file exists                       │
│  Post-check: ◉ waiting                           │
│  Rollback:   git checkout src/routes/auth.js     │
│  Risk:       MEDIUM                              │
└──────────────────────────────────────────────────┘
```

---

## Trace Stream View

### CLI Display (Last 10 events)
```
┌──────────────────────────────────────────────────┐
│  📜 EXECUTION TRACE STREAM                       │
├──────────────────────────────────────────────────┤
│  14:30:01  │ NODE_START    │ step-001  │ INFO   │
│  14:30:02  │ NODE_COMPLETE │ step-001  │ INFO   │
│  14:30:03  │ NODE_START    │ step-002  │ INFO   │
│  14:30:04  │ NODE_COMPLETE │ step-002  │ INFO   │
│  14:30:05  │ NODE_START    │ step-003  │ INFO   │
│  14:30:05  │ NODE_COMPLETE │ step-003  │ INFO   │
│  14:30:06  │ CHECKPOINT    │ step-003  │ INFO   │
│  14:30:07  │ NODE_START    │ step-004  │ INFO   │
│  14:30:09  │ ANOMALY       │ observer  │ ⚠️     │
│  14:30:09  │ DRIFT_ALERT   │ drift     │ ⚠️     │
├──────────────────────────────────────────────────┤
│  10 events/sec  │  Buffer: 45/100  │  ⚡ Live  │
└──────────────────────────────────────────────────┘
```

---

## Memory Query Interface

### CLI Commands
| Command | Description |
|---|---|
| `memory search <query>` | Search memory records |
| `memory get <id>` | Get specific record |
| `memory recent <n>` | Last N records |
| `memory by-execution <exec_id>` | Records for specific execution |

### Web Dashboard
```
┌──────────────────────────────────────────────────────────────────┐
│  Memory Browser                           Search: [auth module ]│
├──────────────────────────────────────────────────────────────────┤
│  ID              │ Type      │ Timestamp          │ Summary     │
├──────────────────────────────────────────────────────────────────┤
│  mem-a3f1        │ EXECUTION │ 2026-05-24 14:30   │ auth module │
│  mem-a3f2        │ CHECKPOINT│ 2026-05-24 14:30   │ step-003    │
│  mem-a3f3        │ ANOMALY   │ 2026-05-24 14:30   │ drift auth  │
│  mem-a3f4        │ RECOVERY  │ 2026-05-24 14:29   │ rollback    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

| View Element | يقرأ من | التنسيق |
|---|---|---|
| State Machine | P3 State Machine current state | JSON event |
| Execution Graph | P3 Execution Engine active graph | JSON object |
| Trace Stream | P3 Live Observer ExecutionTraceStream | JSON event stream |
| Memory Records | P3 Memory Recording Engine | Query response |

---

*The Runtime Console is the real-time window into the system's execution life. It shows exactly what is happening, step by step, from state transitions to individual node execution.*

*وحدة التحكم في Runtime هي النافذة المباشرة على حياة التنفيذ في النظام. تظهر بالضبط ما يحدث، خطوة بخطوة، من انتقالات الحالة إلى تنفيذ كل عقدة.*
