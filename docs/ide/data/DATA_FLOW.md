# Stocky Engineering OS — Data Flow & Event Replay v0.1

---

> هذا الملف يحدد **تدفق البيانات** من الـ 5 طبقات إلى IDE Surface Layer، و **حدود إعادة تشغيل الأحداث (Event Replay Boundary)** — القدرة على إعادة بناء أي لحظة في تاريخ النظام.
>
> This file defines the **Data Flow** from the 5 layers to the IDE Surface Layer, and the **Event Replay Boundary** — the ability to reconstruct any moment in the system's history.

---

## Part 1: Data Flow Architecture — تدفق البيانات

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          IDE SURFACE LAYER (P5-B)                        │
│                                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐   │
│  │ CLI/TUI     │  │ Web         │  │ Replay      │  │ Query        │   │
│  │ (Execution) │  │ Dashboard   │  │ Interface   │  │ Interface    │   │
│  │ Live Stream │  │ On-Demand   │  │ Forensic    │  │ Search       │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────┬───────┘   │
│         │                │                │                │           │
└─────────┼────────────────┼────────────────┼────────────────┼───────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         DATA INTEGRATION LAYER                            │
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Event Stream │  │ Query Router │  │ Replay       │  │ Cache       │  │
│  │ Distributor  │  │ (layer-based)│  │ Engine       │  │ Layer       │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │                 │          │
└─────────┼─────────────────┼─────────────────┼─────────────────┼──────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐
│  P2      │ │  P3      │ │  P4      │ │  P5      │ │  Replay Store    │
│ Doctrine │ │ Runtime  │ │ Control  │ │Coherence │ │  (Event Log +    │
│          │ │ Engine   │ │ Plane    │ │ Layer    │ │   Snapshots)     │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘
```

---

## Data Sources Per View

| View | يقرأ من | التنسيق | التحديث |
|---|---|---|---|
| **Doctrine View** | P2 files (static) | Markdown | On page load |
| **Reasoning View** | P2 Incident + P3 Memory | JSON | On-demand |
| **Runtime Console** | P3 State + Execution + Observer | JSON stream | Live (WebSocket) |
| **Control Dashboard** | P4 Budget + Drift + Stability | JSON stream | Live (WebSocket) |
| **Coherence Monitor** | P5 Lineage + Identity + Contradictions | JSON | On-demand |
| **Memory Browser** | P3 Memory Store | JSON | On-demand |
| **Replay Interface** | Replay Store (P3 + P5) | JSON | On-demand |

---

## Streaming vs Query

### Live Stream Data (WebSocket)
```
من: P3 State Machine, P3 Execution Engine, P4 Drift, P4 Stability, P4 Budget, P3 Observer
إلى: CLI/TUI + Web Dashboard
تنسيق: JSON event stream
تحديث: Real-time (< 100ms latency)
```

### On-Demand Query Data (REST)
```
من: P3 Memory, P5 Lineage, P5 Identity, P2 Incidents
إلى: Web Dashboard
تنسيق: JSON response
تحديث: On user action or refresh
```

### Static Data (File Read)
```
من: ENGINEERING_LAWS.md, STOCKY_MANIFEST.md, SYSTEM_VOCABULARY.md
إلى: Doctrine View
تنسيق: Rendered Markdown
تحديث: Only when files change
```

---

## Part 2: Event Replay Boundary (Refinement #1)

### Why Event Replay?
بدون Replay:
- لا يمكن إعادة بناء حادثة كاملة
- لا يمكن عمل forensic debugging حقيقي
- الـ Lineage + Runtime + Control غير قابلين لإعادة التشغيل الذهني

### What Event Replay Enables
```
1. Reconstruct execution timeline at any point T
2. Rebuild decision graph as it existed at time T
3. Simulate alternative decisions for analysis
4. Forensic debugging of past failures
5. Training and auditing
```

---

### Replay Store Structure

```yaml
ReplayStore:
  stores:
    - event_log:                    # كل حدث في تاريخ النظام
        format: append-only log
        entries: [
          {
            id: string,
            timestamp: datetime,
            type: Enum,             # STATE_CHANGE | STEP_START | DRIFT | ...
            layer: Enum,            # P2 | P3 | P4 | P5
            data: object,           # Event-specific payload
            checksum: string        # SHA-256
          }
        ]
    
    - snapshots:                    # حالة النظام عند نقاط زمنية محددة
        format: periodic snapshots (every 10 steps, on demand)
        entries: [
          {
            id: string,
            timestamp: datetime,
            state_machine: object,   # Full P3 state
            execution_graph: object, # Active graph
            control_state: object,   # P4 allocations
            coherence_state: object, # P5 identity at that time
            checksum: string
          }
        ]
    
    - timeline_index:               # Index للبحث السريع
        by_time: timestamp → event_ids
        by_layer: layer → event_ids
        by_type: type → event_ids
        by_execution: execution_id → event_ids
```

### Snapshot Policy
| Frequency | Type | Retention |
|---|---|---|
| Every 10 execution steps | Auto snapshot | 7 days |
| On user demand | Manual snapshot | Until deleted |
| On HALT / BLOCK | Auto snapshot | 30 days |
| On COMPLETED | Auto snapshot | 90 days |
| On system start/stop | Auto snapshot | Permanent |

---

### Replay Engine

```yaml
ReplayEngine:
  capabilities:
    - reconstruct(point_in_time):
        # إعادة بناء الحالة الكاملة عند نقطة زمنية
        input: timestamp
        output: {
          state: RuntimeState,
          graph: ExecutionGraph,
          control: ControlState,
          identity: IdentityState,
          recent_events: [TraceEvent]
        }
    
    - rebuild_decision_graph(point_in_time):
        # إعادة بناء شجرة القرارات كما كانت في وقت معين
        input: timestamp
        output: DecisionGraph (as it existed at T)
    
    - simulate_alternative(incident_id, alternative_plan):
        # محاكاة ماذا لو تم اختيار بديل مختلف
        input: incident_id + alternative_plan
        output: SimulationResult (predicted outcome)
    
    - diff(time_a, time_b):
        # مقارنة حالتين زمنيتين
        input: timestamp_a, timestamp_b
        output: {
          state_diff: object,
          decision_diff: object,
          identity_diff: object
        }
```

### Replay Query Commands

| CLI Command | Description |
|---|---|
| `replay at <time>` | Show system state at time T |
| `replay incident <id>` | Replay full incident timeline |
| `replay diff <t1> <t2>` | Compare two points in time |
| `replay lineage <id> at <time>` | Show lineage as it existed at T |
| `replay snapshot [label]` | Force a snapshot now |

### Web Replay Interface
```
┌──────────────────────────────────────────────────────────────────────────┐
│  Event Replay                                        Timeline: ●━━━━○   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  14:29:00             14:30:00             14:31:00             │    │
│  │  ──●─────────●─────────●─────────●─────────●─────────●──       │    │
│  │    │  idle    │  plan   │  exec   │  drift  │recover  │ fail   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌── State at 14:30:05 (during EXECUTING) ─────────────────────────┐    │
│  │  State:      EXECUTING (step 4/12)                                │    │
│  │  Graph:      4 nodes complete / 8 pending                         │    │
│  │  Budget:     MEDIUM (3 steps remaining)                           │    │
│  │  Stability:  0.94                                                  │    │
│  │  Drift:      1 active (SOFT, detected at 14:30:01)                │    │
│  │  Identity:   0.96 COHERENT (DCS: 0.98)                           │    │
│  │  Events:     [NODE_START, NODE_COMPLETE, CHECKPOINT, DRIFT]      │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  [Play] [Pause] [Step Forward] [Step Back] [Restore Snapshot]           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

### Replay Rules

```
1. Replay is READ-ONLY — لا يمكن تغيير التاريخ
2. Replay يقرأ من Replay Store (P3 Memory + Snapshots)
3. Replay يمكنه محاكاة "ماذا لو" لكن لا يؤثر على النظام الحي
4. Snapshots تؤخذ تلقائيًا عند الأحداث الحرجة
5. Replay متاح لجميع المستخدمين (قراءة فقط)
6. Replay Store محمي بنفس قوانين P3 Memory (append-only, immutable)
```

---

## Data Integrity

| Guarantee | Enforcement |
|---|---|
| Live stream order | Timestamps + sequence numbers |
| Query consistency | Read from single snapshot per request |
| Replay accuracy | Checksum verification on all stored events |
| Cache freshness | TTL-based invalidation (5s for live, 1min for queries) |

---

*The Data Flow & Event Replay system ensures that Stocky Engineering OS provides complete visibility into its current state and full reconstructability of its past.*

*نظام تدفق البيانات وإعادة تشغيل الأحداث يضمن أن النظام يوفر رؤية كاملة لحالته الحالية وقابلية كاملة لإعادة بناء ماضيه.*
