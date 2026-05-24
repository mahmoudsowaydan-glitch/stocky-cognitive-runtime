# Stocky Engineering OS — Reasoning View v0.1

---

> هذا الملف يحدد **Reasoning View** — visualization كاملة لـ P2 Reasoning Pipeline الـ 7 Layers: كيف يفكر النظام خطوة بخطوة.
>
> This file defines the **Reasoning View** — complete visualization of the P2 7-Layer Reasoning Pipeline: how the system thinks step by step.

---

## Core Content — المحتوى الأساسي

| العنصر | المصدر |
|---|---|
| 7-Layer Pipeline Flow | P2 REASONING_PIPELINE.md |
| Current active incident | P2 EngineeringIncident |
| Classification details | P2 Layer 2 |
| Context resolution | P2 Layer 3 |
| Root cause analysis | P2 Layer 4 |
| Governance verdict | P2 Layer 5 |
| Execution plan | P2 Layer 6 |

---

## Pipeline Flow Visualization

### Web Dashboard
```
┌────────────────────────────────────────────────────────────────────────────┐
│  Reasoning Pipeline                                 Incident: inc-a3f1     │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  │
│  │Signal  │  │Classify│  │Context │  │Reason  │  │Govern  │  │Plan    │  │
│  │Intake  │──│        │──│Resolve │──│        │──│        │──│        │  │
│  │  ✓     │  │  ✓     │  │  ✓     │  │  ●     │  │  ⏳    │  │  ⏳    │  │
│  │ L1     │  │ L2     │  │ L3     │  │ L4     │  │ L5     │  │ L6     │  │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘  │
│       │           │           │           │           │           │       │
│       ▼           ▼           ▼           ▼           ▼           ▼       │
│  Source:    Type:          Files:       Root:       Verdict:    Steps:   │
│  DRIFT      ARCH_BOUND    5 files      AL-01       ALLOW       3 steps  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### CLI Display
```
┌──────────────────────────────────────────────────────────┐
│  REASONING PIPELINE  │  Incident: inc-a3f1               │
├──────────────────────────────────────────────────────────┤
│  L1 [✓] Signal Intake     │  Source: DRIFT_DETECTOR     │
│  L2 [✓] Classification    │  Type: ARCHITECTURE_VIOLATION│
│  L3 [✓] Context Resolve   │  Files: 5  │  Deps: 12     │
│  L4 [●] Engineering Reason│  Root Cause: analyzing...   │
│  L5 [⏳] Governance        │  Verdict: pending           │
│  L6 [⏳] Execution Plan    │  Steps: pending             │
├──────────────────────────────────────────────────────────┤
│  Confidence: 0.82  │  Risk: 0.45  │  Duration: 1.2s    │
└──────────────────────────────────────────────────────────┘
```

---

## Incident Detail View

```
┌─────────────────────────────────────────────────────────────────────┐
│  Incident: inc-a3f1                                    ● ACTIVE    │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─── L1: Signal Intake ──────────────────────────────────────┐   │
│  │  Source:          DRIFT_DETECTOR                            │   │
│  │  Type:            ARCHITECTURE_VIOLATION                    │   │
│  │  Initial Severity: CRITICAL                                 │   │
│  │  Timestamp:       2026-05-24 14:30:00                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── L2: Classification ─────────────────────────────────────┐   │
│  │  Category:  Layer dependency violation                      │   │
│  │  Confidence: 0.82                                           │   │
│  │  Pattern:   domain_layer → runtime_layer (forbidden)       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── L3: Context Resolution ────────────────────────────────┐   │
│  │  Files:       src/domain/auth.ts, src/runtime/api.ts       │   │
│  │  Dependencies: domain → runtime ✓ (circular detected)      │   │
│  │  Past incidents: 2 similar in last 24h                     │   │
│  │  Active laws:   AL-01, DL-02                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── L4: Engineering Reasoning ─────────────────────────────┐   │
│  │  Root Cause:  auth domain module imports runtime HTTP client│   │
│  │  Impact:      Breaks AL-01, may affect all domain clients  │   │
│  │  Alternatives: 1. Extract HTTP to infrastructure layer      │   │
│  │                2. Add interface in domain                   │   │
│  │  Risk Score:  0.45                                          │   │
│  │  Confidence:  0.85                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── L5: Governance Verdict ────────────────────────────────┐   │
│  │  Verdict:      ALLOW  (with modified plan)                 │   │
│  │  Conditions:   Must extract HTTP client first              │   │
│  │  Violations:   None (plan addresses the issue)             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── L6: Execution Plan ────────────────────────────────────┐   │
│  │  Steps:  3  │  Checkpoints: 1  │  Rollback: sequential    │   │
│  │  1. Extract HTTP client to infra/                          │   │
│  │  2. Add domain interface                                   │   │
│  │  3. Update imports                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Reasoning History

### Recent Incidents List (Web)
```
┌──────────────────────────────────────────────────────────────────────┐
│  Recent Reasoning History                    Filter: [All Types ▼] │
├──────────────────────────────────────────────────────────────────────┤
│  ID        │ Type              │ Severity │ Status   │ Time       │
├──────────────────────────────────────────────────────────────────────┤
│  inc-a3f1  │ Architecture Viol │ CRITICAL │ ● ACTIVE │ 2 min ago  │
│  inc-a3f0  │ State Corruption  │ HIGH     │ ✓ RES    │ 15 min ago │
│  inc-a3ef  │ Compile Failure   │ MEDIUM   │ ✓ RES    │ 1 hour ago │
│  inc-a3ee  │ Runtime Anomaly   │ MEDIUM   │ ✓ RES    │ 2 hours ago│
└──────────────────────────────────────────────────────────────────────┘
```

### Incident Status Legend
| Status | Meaning |
|---|---|
| ● ACTIVE | قيد المعالجة |
| ✓ RESOLVED | تم الحل |
| ⏳ PENDING | ينتظر Governance |
| ❌ FAILED | فشل — لم يُحل |
| 🔄 ROLLED_BACK | تم التراجع عنه |

---

## Alternative Comparison View

```
┌──────────────────────────────────────────────────────────────────────┐
│  Alternative Solutions for inc-a3f1                                   │
├──────────────────────────────────────────────────────────────────────┤
│  ┌── Alternative 1 (RECOMMENDED) ───────────────────────────────┐   │
│  │  Extract HTTP to infrastructure layer                         │   │
│  │  Risk: 0.20  │  Effort: MEDIUM  │  Alignment: 0.95           │   │
│  │  ✓ Does not violate any Law                                  │   │
│  │  ✓ Preserves domain independence                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  ┌── Alternative 2 ────────────────────────────────────────────┐   │
│  │  Add interface in domain (keep HTTP in runtime)              │   │
│  │  Risk: 0.35  │  Effort: LOW  │  Alignment: 0.80             │   │
│  │  ⚠ Partial fix — still has runtime dependency               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

| View Element | يقرأ من |
|---|---|
| Pipeline flow | P2 Reasoning Pipeline current state |
| Incident detail | P2 EngineeringIncident (all layers) |
| Reasoning history | P3 Memory (type = EXECUTION_RECORD) |
| Alternative analysis | P2 Layer 4 reasoning_output.alternatives |
| Governance conditions | P2 Layer 5 governance_verdict |

---

*The Reasoning View is the mind-reading window of Stocky Engineering OS. It shows not just what the system decided, but the entire chain of thought that led to the decision.*

*عرض التفكير هو نافذة قراءة العقل للنظام. لا يظهر فقط ما قرره النظام، بل سلسلة التفكير الكاملة التي أدت إلى القرار.*
