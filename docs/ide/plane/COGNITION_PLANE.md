# Stocky Engineering OS — Cognition Plane (Web Dashboard) v0.1

---

> هذا الملف يحدد **طائرة الإدراك (Cognition Plane)** — واجهة Web Dashboard للاستعلام والتحليل المتعمق في طبقات P2 و P5.
>
> This file defines the **Cognition Plane** — the Web Dashboard interface for deep query and analysis across P2 and P5 layers.

---

## Core Principle — المبدأ الأساسي

```
The Cognition Plane is the deep analysis surface.
طائرة الإدراك هي سطح التحليل العميق.

On-demand · Visual · Exploratory · Historical
```

---

## Architecture

```
User (Browser)
    │
    ▼
┌─────────────────────────────────────────────┐
│           WEB DASHBOARD (localhost)          │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Doctrine │  │ Reasoning│  │ Coherence │  │
│  │ View     │  │ View     │  │ Monitor   │  │
│  └──────────┘  └──────────┘  └───────────┘  │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │           Navigation Bar             │   │
│  │  [Doctrine] [Reasoning] [Coherence]  │   │
│  └──────────────────────────────────────┘   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           DASHBOARD API SERVER               │
│  REST + WebSocket to all layers              │
│  Query translation + Response formatting     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
    ┌──────────┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ P2   │ │ P2     │ │ P3     │ │ P4     │ │ P5     │
│ Laws │ │ Reason │ │ Memory │ │ Control│ │Coherence│
└──────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

---

## Web Routes

| Route | View | Layer | Content |
|---|---|---|---|
| `/` | Overview | All | System status summary |
| `/doctrine` | Doctrine View | P2 | Manifest, Laws, Events, Vocabulary |
| `/reasoning` | Reasoning View | P2 | Pipeline visualization |
| `/reasoning/:id` | Reasoning Detail | P2 | Single incident analysis |
| `/coherence` | Coherence Monitor | P5 | Lineage, Identity, Contradictions |
| `/coherence/lineage` | Lineage Graph | P5 | Decision tree visualization |
| `/coherence/identity` | Identity Dashboard | P5 | Metrics + trends |
| `/memory` | Memory Browser | P3 | Search + browse records |
| `/control/history` | Control History | P4 | Past control decisions |
| `/replay` | Replay Interface | All | Event Replay (Refinement #1) |

---

## Navigation Bar

```
┌─────────────────────────────────────────────────────────────────────┐
│  🧠 STOCKY ENGINEERING OS  │  [Doctrine] [Reasoning] [Coherence]   │
│  [Memory] [Control] [Replay]            Identity: 0.96 ● COHERENT  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Overview Page (`/`)

```
┌─────────────────────────────────────────────────────────────────────┐
│  System Overview                                        ● COHERENT │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │ Doctrine    │  │ Reasoning   │  │ Execution   │  │ Coherence │ │
│  │ 23 Laws ✓   │  │ 7 Layers ✓  │  │ 4/12 steps  │  │ 0.96      │ │
│  │ 11 Event Ty │  │ Last: 2 min │  │ State: EXEC │  │ DCS: 0.98 │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
│                                                                     │
│  Recent Activity:                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 14:30 │ auth module refactor      │ Reasoning → Execution   │  │
│  │ 14:28 │ drift detected (SOFT)     │ Drift Suppression       │  │
│  │ 14:25 │ budget adjusted to MEDIUM │ User action             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Navigation Patterns

### From View to View
```
Doctrine View → click a Law → Reasoning View (show incidents for this law)
Reasoning View → click an incident → Runtime Console (show execution trace)
Coherence Monitor → click a decision → Reasoning View (show what led to it)
Memory Browser → click a record → Runtime Console (show execution context)
Control History → click a decision → Coherence Monitor (show lineage)
```

### Search Bar (Global)
```
[🔍 Search across all layers...                ]
  ┌─────────────────────────────────────────────┐
  │ 🔍 auth module                              │
  │   Doctrine: Law AL-01 · Law DL-03          │
  │   Reasoning: 2 incidents                   │
  │   Runtime:  3 executions · 12 memory recs  │
  │   Coherence: lineage chain (7 nodes)       │
  └─────────────────────────────────────────────┘
```

---

## Dashboard API Server

### Endpoints
| Method | Endpoint | Returns |
|---|---|---|
| GET | `/api/status` | System status summary |
| GET | `/api/doctrine/laws` | All laws |
| GET | `/api/doctrine/laws/:id` | Single law + related incidents |
| GET | `/api/doctrine/events` | All event types |
| GET | `/api/reasoning/incidents` | Recent incidents |
| GET | `/api/reasoning/incidents/:id` | Single incident + full trace |
| GET | `/api/coherence/identity` | Current identity metrics |
| GET | `/api/coherence/lineage/:id` | Lineage tree for decision |
| GET | `/api/memory/search?q=` | Memory search results |
| GET | `/api/replay?execution_id=` | Full execution timeline |
| POST | `/api/controls/budget` | Adjust budget |
| POST | `/api/controls/ack` | Acknowledge alert |

### Authentication
- Localhost-only (no external access)
- No authentication required for read endpoints
- Control endpoints verify session context

---

*The Cognition Plane is the analytical brain of the IDE. It provides deep visibility into why the system thinks what it thinks and how its identity evolves over time.*

*طائرة الإدراك هي العقل التحليلي للـ IDE. توفر رؤية عميقة لسبب اعتقاد النظام بما يعتقده وكيف تتطور هويته عبر الزمن.*
