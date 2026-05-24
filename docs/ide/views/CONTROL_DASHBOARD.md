# Stocky Engineering OS — Control Dashboard View v0.1

---

> هذا الملف يحدد **Control Dashboard** — view P4 في طائرة التنفيذ: الميزانية، الانحراف، الاستقرار، ومحدد التدفق.
>
> This file defines the **Control Dashboard** — the P4 view in the Execution Plane: budget, drift, stability, and rate limiter.

---

## Core Content — المحتوى الأساسي

| العنصر | المصدر | Live؟ |
|---|---|---|
| Budget allocation + tier | P4 EXECUTION_BUDGET_SYSTEM.md | ✅ Live |
| Drift alerts (active) | P4 DRIFT_SUPPRESSION_ENGINE.md | ✅ Live |
| Stability Score + Level | P4 STABILITY_MONITOR.md | ✅ Live |
| Rate Limiter status | P4 COGNITIVE_RATE_LIMITER.md | ✅ Live |
| Risk Dampening signal | P4 RISK_DAMPENING_SYSTEM.md | ✅ Live |

---

## Budget System View

### CLI Display
```
┌──────────────────────────────────────────────────┐
│  🎯 EXECUTION BUDGET SYSTEM                      │
├──────────────────────────────────────────────────┤
│  Tier:       MEDIUM    [▲] [▼]                   │
│  Mode:       NORMAL                              │
│  Steps used: 4 / 7 allocated                     │
│  Time used:  7.2s / 15s timeout                  │
│  Context:    12 files in scope                   │
│  Elasticity: ━━━━●━━━━━ NORMAL                   │
├──────────────────────────────────────────────────┤
│  Risk: 0.42  │  Confidence: 0.78  │  Stable ✓   │
└──────────────────────────────────────────────────┘
```

### Budget Adjust Controls
| Control | Action | Safe Range |
|---|---|---|
| `[▲]` | Increase budget tier | LOW → MEDIUM → HIGH |
| `[▼]` | Decrease budget tier | HIGH → MEDIUM → LOW |
| Reset | Reset to default | Only when IDLE |

---

## Drift Suppression View

### CLI Display
```
┌──────────────────────────────────────────────────┐
│  🛡️ DRIFT SUPPRESSION ENGINE                     │
├──────────────────────────────────────────────────┤
│  Active drifts: 1                                 │
│                                                  │
│  ⚠️ [id: drf-a3f2] SOFT DRIFT                    │
│     Type: Architectural Boundary                 │
│     Module: src/auth/middleware.js               │
│     Scope: LOCAL                                 │
│     Status: ● WARN (checkpoint added)            │
│     [ACK] [INSPECT]                              │
│                                                  │
│  Resolved last hour: 3  │  Total today: 7       │
└──────────────────────────────────────────────────┘
```

### Drift Detail (on inspect)
```
┌──────────────────────────────────────────────────┐
│  DRIFT: drf-a3f2                                 │
├──────────────────────────────────────────────────┤
│  Detected:   2026-05-24 14:30:01                 │
│  Type:       ARCHITECTURAL_BOUNDARY              │
│  Severity:   SOFT                                │
│  Law:        AL-01                               │
│  Source:     src/auth/api.ts → src/domain/       │
│  Intervention: WARNING + checkpoint added        │
│  Isolated:   false                               │
│  Resolved:   false                               │
└──────────────────────────────────────────────────┘
```

---

## Stability Monitor View

### CLI Display
```
┌──────────────────────────────────────────────────┐
│  🧠 STABILITY MONITOR                            │
├──────────────────────────────────────────────────┤
│  Score:  0.94  ●━━━━━━━━━━○━━━ COHERENT          │
│                                                  │
│  Metrics:                                        │
│  ┌─────────────┬───────┬────────┐               │
│  │ Metric      │ Value │ Status │               │
│  ├─────────────┼───────┼────────┤               │
│  │ Loops       │ 0     │ ✓      │               │
│  │ Anomalies/h │ 2     │ ✓      │               │
│  │ Retries     │ 1     │ ✓      │               │
│  │ Transitions │ 8/min │ ✓      │               │
│  │ Memory      │ 0.2%  │ ✓      │               │
│  └─────────────┴───────┴────────┘               │
│                                                  │
│  HALT: not active                                │
└──────────────────────────────────────────────────┘
```

---

## Rate Limiter View

### CLI Display
```
┌──────────────────────────────────────────────────┐
│  ⏱ COGNITIVE RATE LIMITER                        │
├──────────────────────────────────────────────────┤
│  Load:  0.32  ●━━━━━━━━━━━━━━━ LOW               │
│  Strategy: PASS (no throttling)                   │
│  Queue:  0/100                                    │
│  Events dropped: 0                                │
│  Backoff: not active                              │
├──────────────────────────────────────────────────┤
│  Event Rate: 12/sec  │  Limit: 100/sec           │
└──────────────────────────────────────────────────┘
```

---

## Combined Control Summary

### CLI Display
```
┌──────────────────────────────────────────────────────────────┐
│  CONTROL PLANE SUMMARY                                       │
├──────────────────────────────────────────────────────────────┤
│  🎯 Budget:  MEDIUM  │  🛡 Drift: 1 active (SOFT)          │
│  🧠 Stability: 0.94  │  ⏱ Rate: 0.32 (PASS)              │
│  📉 Risk Baseline: 0.35  │  Trend: STABLE                  │
├──────────────────────────────────────────────────────────────┤
│  🟢 ALL SYSTEMS NOMINAL                                      │
└──────────────────────────────────────────────────────────────┘
```

### Web Dashboard Widget
```
┌──────────────────────────────────────────────────────────────────────┐
│  Control Plane Dashboard                                            │
├──────────────────────────────────────────────────────────────────────┤
│  ┌──── Budget ────┐  ┌──── Drift ─────┐  ┌── Stability ──┐       │
│  │  MEDIUM    ▲▼  │  │  1 active (S)  │  │  0.94 ● COH   │       │
│  │  4/7 steps     │  │  ┌────────────┐│  │  HALT: OFF    │       │
│  │  7.2/15s       │  │  │ auth/bound ││  └───────────────┘       │
│  │  NORMAL        │  │  └────────────┘│                          │
│  └────────────────┘  └────────────────┘  ┌──── Rate ──────┐      │
│  ┌──── Risk ──────┐                      │  0.32 ● PASS   │      │
│  │  Baseline: 0.35│                      │  Queue: 0      │      │
│  │  Trend: STABLE │                      │  Dropped: 0    │      │
│  └────────────────┘                      └────────────────┘      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Control Actions from Dashboard

| Action | يؤثر على | Safe Range |
|---|---|---|
| Adjust budget tier | P4 Budget System | LOW / MEDIUM / HIGH (ليس CRITICAL) |
| Acknowledge drift | P4 Drift Suppression | Removes from active list |
| Acknowledge anomaly | P4 Stability Monitor | Clears anomaly flag |
| Inspect drift detail | P4 Drift → P5 Lineage | Read-only |
| Reset budget | P4 Budget System | Only when IDLE |

---

## Data Sources

| View Element | يقرأ من | التنسيق |
|---|---|---|
| Budget status | P4 Budget System allocation | Live update |
| Drift list | P4 Drift Suppression active records | Live list |
| Stability score | P4 Stability Monitor report | Every 60s |
| Rate limiter state | P4 Rate Limiter current state | Live update |
| Risk baseline | P4 Risk Dampening System | Every 60s |

---

*The Control Dashboard is the command center of the Stocky Engineering OS safety systems. It shows how the system is protecting itself in real-time.*

*لوحة التحكم هي مركز قيادة أنظمة الأمان في النظام. تظهر كيف يحمي النظام نفسه في الوقت الفعلي.*
