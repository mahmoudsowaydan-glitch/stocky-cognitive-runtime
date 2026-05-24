# Stocky Engineering OS — Stability Monitor v0.1

---

> هذا الملف يحدد **مراقب الاستقرار** — المسؤول عن اكتشاف حلقات التفكير اللانهائية، عدم الاستقرار الإدراكي، وإصدار أمر HALT عند الضرورة.
>
> This file defines the **Stability Monitor** — responsible for detecting infinite reasoning loops, cognitive instability, and issuing HALT commands when necessary.

---

## Core Principle — المبدأ الأساسي

```
الاستقرار هو شرط أساسي للذكاء الآمن.
Stability is a prerequisite for safe intelligence.

Stability Monitor لديه السلطة الوحيدة لـ HALT أي تنفيذ.
```

---

## Monitored Signals — الإشارات المراقبة

| Signal | المصدر | التأثير على Stability |
|---|---|---|
| **Loop Detection** | Trace Stream | تكرار نفس الـ pattern 3+ times |
| **State Oscillation** | Runtime State | State يتغير بين حالتين باستمرار |
| **Execution Retry Rate** | Execution Engine | Retries > threshold |
| **Anomaly Frequency** | Live Observer | Anomalies في فترة زمنية قصيرة |
| **Transition Velocity** | State Machine | Transitions/sec > threshold |
| **Memory Growth Rate** | Memory Recording | نمو سريع غير طبيعي |
| **Drift Recurrence** | Drift Suppression | نفس الـ drift يتكرر باستمرار |
| **Budget Saturation** | Budget System | استهلاك كامل للـ Budget دون تقدم |

---

## Stability Score Calculation — حساب درجة الاستقرار

### Formula
```
StabilityScore = 1.0 - (
    (loop_weight * 0.30) +
    (anomaly_weight * 0.25) +
    (retry_weight * 0.15) +
    (transition_weight * 0.15) +
    (drift_weight * 0.15)
)

حيث:
  loop_weight      = detected_loops / max_allowed_loops (0.0 - 1.0)
  anomaly_weight   = anomaly_count / hour (capped at 1.0)
  retry_weight     = retry_count / max_retries_allowed (0.0 - 1.0)
  transition_weight= transitions_per_sec / 10 (capped at 1.0)
  drift_weight     = recurring_drifts / max_allowed_drifts (0.0 - 1.0)
```

### Stability Levels
| StabilityScore | Level | الوصف |
|---|---|---|
| 0.9 — 1.0 | **STABLE** | System正常运行 |
| 0.7 — 0.9 | **CAUTION** | Mild instability — مراقبة |
| 0.5 — 0.7 | **UNSTABLE** | تدخل مطلوب — إبلاغ Arbitration |
| 0.3 — 0.5 | **CRITICAL** | تدخل فوري — تخفيض Budget |
| < 0.3 | **COLLAPSING** | HALT فوري |

---

## Loop Detection — كشف الحلقات

### Detection Algorithm
```
1. اقرأ آخر N من TraceEvents (N = 20)
2. ابحث عن repeating patterns:
   - نفس الـ action_type يتكرر 3+ مرات
   - نفس state cycle (A→B→A→B→A)
   - نفس error يتكرر مع retry
3. إذا وجد loop:
   a. احسب loop_duration
   b. احسب loop_iterations
   c. سجل LoopRecord في Memory
   d. إذا iterations > 3 → إبلاغ Arbitration
   e. إذا iterations > 5 → HALT فوري
```

### Loop Record
```yaml
LoopRecord:
  id: string
  execution_id: string
  pattern: [string]             # Sequence of events forming the loop
  iterations: number
  duration_ms: number
  detected_at: datetime
  severity: Enum                # MILD | MODERATE | SEVERE
  halting: boolean              # Did this trigger HALT?
```

---

## HALT Authority — سلطة الإيقاف

### HALT Triggers
| Trigger | Threshold | Action |
|---|---|---|
| StabilityScore < 0.3 | COLLAPSING level | HALT فوري |
| Loop iterations > 5 | SEVERE loop | HALT فوري |
| Consecutive Critical anomalies > 3 | Anomaly storm | HALT فوري |
| Memory growth > 1GB in 1min | Memory leak | HALT + Quarantine |
| State machine invalid transition | Forbidden transition | HALT + Governance |

### HALT Flow
```
HALT triggered:
  1. Freeze Execution Engine فورًا
  2. Freeze State Machine (force IDLE)
  3. سجل HALTRecord في Memory (immutable)
  4. أبلغ Governance Layer (CRITICAL)
  5. أبلغ Drift Suppression (عزل إذا لزم الأمر)
  6. أبلغ المستخدم (Reason + Scope)
  
  HALT لا يمكن رفعه إلا عن طريق:
    1. Governance Layer review
    2. Root cause identified and fixed
    3. Explicit user confirmation
```

### HALT Record
```yaml
HALTRecord:
  id: string
  timestamp: datetime
  reason: string
  trigger: Enum                 # LOOP | INSTABILITY | LEAK | TRANSITION | OTHER
  affected_execution_id: string
  stability_score_at_halt: float
  scope: string                 # What was halted
  recovery_plan: string         # Steps to resume
  resolved: boolean
  resolved_at: datetime|null
```

---

## Stability Report — تقرير الاستقرار

### Periodic Report
```
كل 60 ثانية، Stability Monitor يصدر تقرير:
  - current StabilityScore
  - recent anomalies count
  - active loops (if any)
  - memory trend
  - recommendation: CONTINUE | CAUTION | INTERVENE | HALT
```

### Report Structure
```yaml
StabilityReport:
  timestamp: datetime
  score: float                  # 0.0 - 1.0
  level: Enum                   # STABLE | CAUTION | UNSTABLE | CRITICAL | COLLAPSING
  metrics: {
    loop_count: number,
    anomaly_count_1h: number,
    retry_rate: float,
    transition_rate: float,
    drift_recurrence: number,
    memory_growth_mb: number
  }
  active_loops: [LoopRecord]
  recommendation: string
  halting: boolean              # Is HALT active?
```

---

*The Stability Monitor is the self-preservation instinct of Stocky Engineering OS. It ensures the system maintains cognitive health and halts before collapse.*

*مراقب الاستقرار هو غريزة الحفاظ على الذات للنظام. يضمن أن النظام يحافظ على صحة إدراكية ويتوقف قبل الانهيار.*
