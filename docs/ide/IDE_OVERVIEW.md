# Stocky Engineering OS — Cognitive Visibility Layer Overview v0.1

---

> هذا الملف هو **الخريطة الرئيسية لـ P5-B IDE Surface Layer** — طبقة الرؤية الإدراكية التي تجعل النظام المعرفي مرئيًا وتفاعليًا وآمنًا.
>
> This file is the **master map of P5-B IDE Surface Layer** — the cognitive visibility layer that makes the cognitive system visible, interactive, and safe.

---

## Core Philosophy — الفلسفة الأساسية

```
P5-B does not add intelligence — it makes it visible.
P5-B لا يضيف ذكاء — بل يجعله مرئيًا.

P5-B is the Control Room for a Self-Aware Computational System.
P5-B هو غرفة التحكم لنظام حاسوبي واعٍ بذاته.
```

---

## Dual-Plane Architecture — بنية المستويين

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       P5-B COGNITIVE VISIBILITY LAYER                    │
│                                                                          │
│  ┌───────────── EXECUTION PLANE (LIVE) ────────────────────────┐       │
│  │  Platform: CLI / TUI                                         │       │
│  │  Timing: Live stream (WebSocket)                              │       │
│  │  Content: P3 state · P4 alerts · execution traces            │       │
│  │  Interaction: Pause · Resume · Budget adjust · Ack alerts    │       │
│  │  Session: Active Cognitive Session context tracking          │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  ┌───────────── COGNITION PLANE (ON-DEMAND) ───────────────────┐       │
│  │  Platform: Web Dashboard (localhost)                          │       │
│  │  Timing: On-demand queries                                    │       │
│  │  Content: P2 reasoning · P5 lineage · identity · history      │       │
│  │  Interaction: Browse · Inspect · Analyze · Explore             │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  ┌───────────── REPLAY BOUNDARY (FORENSIC) ────────────────────┐       │
│  │  Reconstruct execution timeline at any point T                │       │
│  │  Rebuild decision graph as it existed at time T               │       │
│  │  Simulate alternative decisions for analysis                  │       │
│  └──────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
                │                   │                    │
                ▼                   ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
    │  READS FROM  │    │  WRITES TO   │    │  READS FROM P3   │
    │  ALL LAYERS  │    │  (SAFE)      │    │  + P5 Lineage    │
    │  P2-P3-P4-P5 │    │  P3 · P4     │    │  + P2 Reasoning  │
    └──────────────┘    └──────────────┘    └──────────────────┘
```

---

## The 3 Refinements — التحسينات الثلاثة

### 1. Event Replay Boundary (في DATA_FLOW.md)
إعادة بناء أي لحظة في تاريخ النظام — كاملة مع الـ state والـ decisions والـ context.

### 2. Authority Precedence Stack (في CONTROL_AUTHORITY.md)
P4 (Control) > P3 (Execution) > UI Actions — لا يمكن للـ UI تجاوز Control Plane.

### 3. Cognitive Session Context (في EXECUTION_PLANE.md)
Session ID, Intent Vector, Active Reasoning Context, Execution Scope Boundary لكل جلسة IDE.

---

## The 5 Views — المشاهد الخمسة

| View | Plane | Layer | Content |
|---|---|---|---|
| **Doctrine View** | Cognition | P2 | Manifest, Laws, Events, Vocabulary |
| **Reasoning View** | Cognition | P2 | 7-Layer Pipeline, classification, risk analysis |
| **Runtime Console** | Execution | P3 | State machine, execution graph, trace stream |
| **Control Dashboard** | Execution | P4 | Budget, drift alerts, stability score, rate limiter |
| **Coherence Monitor** | Cognition | P5 | Lineage graph, identity score, contradictions |

---

## File Map — خريطة الملفات

```
docs/ide/
├── IDE_OVERVIEW.md              ← أنت هنا
│
├── plane/
│   ├── EXECUTION_PLANE.md       — CLI Core + Cognitive Session (Refinement #3)
│   └── COGNITION_PLANE.md       — Web Dashboard structure
│
├── views/
│   ├── DOCTRINE_VIEW.md         — P2 viewer
│   ├── REASONING_VIEW.md        — P2 pipeline visualization
│   ├── RUNTIME_CONSOLE.md       — P3 live view
│   ├── CONTROL_DASHBOARD.md     — P4 control view
│   └── COHERENCE_MONITOR.md     — P5 identity view
│
├── controls/
│   ├── SAFE_CONTROLS.md         — Allowed actions
│   ├── CONTROL_AUTHORITY.md     — CAN/CANNOT + Authority Precedence (Refinement #2)
│   └── ACTION_FLOW.md           — Action propagation
│
└── data/
    └── DATA_FLOW.md             — Data flow + Event Replay (Refinement #1)
```

---

## Interaction Model — نموذج التفاعل

```
User
  │
  ├──● Observation (Read):
  │     CLI live stream → P3 + P4
  │     Web on-demand  → P2 + P5
  │
  ├──● Safe Control (Write):
  │     pause/resume   → P3 (Execution Engine)
  │     budget adjust  → P4 (Budget System)
  │     ack alerts     → P4 (Drift Suppression)
  │     approve        → P2 (Governance Layer)
  │
  └──● Exploration (Read + Query):
        replay history → P3 + P5
        lineage browse → P5
        memory search  → P3
```

---

*The Cognitive Visibility Layer is the human window into the Stocky Engineering OS mind. It shows what the system thinks, why it acts, and how it stays coherent over time.*

*طبقة الرؤية الإدراكية هي نافذة البشر على عقل النظام. تظهر ما يفكر فيه النظام، لماذا يتصرف، وكيف يبقى متسقًا عبر الزمن.*
