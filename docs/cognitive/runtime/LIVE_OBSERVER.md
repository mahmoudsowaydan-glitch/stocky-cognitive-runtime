# Stocky Engineering OS — Live Observer Engine v0.1

---

> هذا الملف يحدد **محرك المراقبة المباشر** — المسؤول عن تتبع التنفيذ في الوقت الفعلي، كشف الانحراف (Drift)، وتوليد إشارات الشذوذ (Anomaly Signals).
>
> This file defines the **Live Observer Engine** — responsible for real-time execution tracing, drift detection, and anomaly signal generation.

---

## Core Principle — المبدأ الأساسي

```
المراقبة يجب أن تكون:
  - Passive: لا تؤثر على التنفيذ (RL-01)
  - Real-time: تأخير أقل من 100ms
  - Complete: جميع steps و transitions
  - Immutable: الـ trace لا يُعدّل بعد التسجيل
```

---

## Module Architecture — بنية الـ Module

```
┌──────────────────────────────────────────────────────────┐
│                    LIVE OBSERVER ENGINE                     │
│                                                            │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │ ExecutionTrace   │  │ StateChange      │                 │
│  │ Stream           │  │ Listener         │                 │
│  └────────┬────────┘  └────────┬────────┘                 │
│           │                    │                           │
│           ▼                    ▼                           │
│  ┌──────────────────────────────────────────────┐         │
│  │           Drift Detector (Runtime)            │         │
│  └──────────────────┬───────────────────────────┘         │
│                     │                                      │
│                     ▼                                      │
│  ┌──────────────────────────────────────────────┐         │
│  │         Anomaly Signal Generator               │         │
│  │  → Generates EngineeringEvent to Layer 1       │         │
│  └──────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────┘
```

---

## 🟦 ExecutionTraceStream — تدفق تتبع التنفيذ

### Purpose
تسجيل كل حدث يحدث أثناء التنفيذ في تدفق زمني واحد.

### TraceEvent Structure
```yaml
TraceEvent:
  id: string                    # Unique trace event ID
  execution_id: string          # Reference to execution
  timestamp: datetime           # وقت الحدث (nanosecond precision)
  event_type: Enum              # NODE_START | NODE_COMPLETE | NODE_FAIL |
                                # STATE_TRANSITION | CHECKPOINT | ANOMALY |
                                # RECOVERY_START | RECOVERY_COMPLETE | ROLLBACK
  source: string                # Component that emitted the event
  data: object                  # Event-specific data
  severity: Enum                # INFO | WARNING | ERROR | CRITICAL
```

### Trace Stream Rules
| Rule | Enforcement |
|---|---|
| Append-only | لا يمكن حذف أو تعديل TraceEvent بعد إضافته |
| Ordered | جميع الأحداث مرتبة زمنيًا |
| Non-blocking | الـ Observer لا يمنع التنفيذ أبدًا |
| Bounded | حجم الـ Stream محدود (10K events) — بعدها يُضغط ويُؤرشَف |

---

## 🟩 StateChangeListener — مستمع تغيير الحالة

### Purpose
الاستماع إلى تغييرات Runtime State Machine وتسجيلها.

### Listener Logic
```
onStateChange(new_state, previous_state, trigger):
    1. Create TraceEvent:
       - event_type = STATE_TRANSITION
       - data = { from: previous_state, to: new_state, trigger }
       - severity = INFO
    
    2. Check transition validity:
       - If forbidden transition → Create Anomaly Signal (CRITICAL)
    
    3. Record state duration:
       - Calculate time in previous state
       - If exceeded timeout → Create Anomaly Signal (WARNING)
    
    4. Push to ExecutionTraceStream
```

### Monitored State Metrics
| Metric | المصدر | Threshold |
|---|---|---|
| State duration | StateChangeListener | Per-state timeout |
| Transition count | StateChangeListener | > 10 transitions/min → warning |
| Invalid transition | StateChangeListener | Any → CRITICAL anomaly |

---

## 🟨 DriftDetector (Runtime Level) — كاشف الانحراف التشغيلي

### Purpose
كشف الانحرافات في Runtime أثناء التنفيذ — ليس معماريًا، بل تشغيليًا.

### Detected Drift Types
| Drift Type | الوصف | Detection Method |
|---|---|---|
| **Execution delay** | خطوة تستغرق وقتًا أطول من المتوقع | Timeout comparison |
| **State inconsistency** | حالة الـ Runtime تختلف عن المتوقع | State comparison |
| **Resource leak** | زيادة غير طبيعية في الموارد | Resource monitoring |
| **Event flood** | عدد غير طبيعي من الأحداث | Rate limiting check |
| **Memory growth** | زيادة مستمرة في الذاكرة | Memory polling |
| **Lost checkpoint** | Checkpoint متوقع لم يحدث | Checkpoint verification |

### Detection Rules
| Rule | Threshold | Action |
|---|---|---|
| Execution delay | > 2x expected duration | WARNING anomaly |
| State inconsistency | Any mismatch | CRITICAL anomaly → trigger recovery |
| Resource leak | > 80% of limit | WARNING anomaly |
| Event flood | > 100 events/sec | WARNING anomaly + rate limit |
| Memory growth | > 500MB growth in 1min | CRITICAL anomaly |
| Lost checkpoint | Expected but not received within timeout | CRITICAL anomaly |

---

## 🟥 AnomalySignalGenerator — مولد إشارات الشذوذ

### Purpose
تحويل أي اكتشاف غير طبيعي إلى EngineeringEvent وإرساله إلى Layer 1 (Signal Intake) لإعادة التقييم.

### Signal Generation Flow
```
Drift Detector triggers anomaly
    │
    ▼
AnomalySignalGenerator:
    1. Determines anomaly severity
    2. Creates EngineeringEvent:
       - source = RUNTIME_OBSERVER
       - type = RUNTIME_ANOMALY (or specific type)
       - initial_severity = based on anomaly severity
       - snapshot = current RuntimeState + trace context
    3. Pushes event to Layer 1 (Signal Intake)
    4. Records anomaly in Memory
    5. If severity >= HIGH → triggers immediate Recovery Engine
```

### Anomaly → Event Mapping
| Anomaly Type | EngineeringEvent Type | Initial Severity |
|---|---|---|
| Execution delay | RUNTIME_ANOMALY | MEDIUM |
| State inconsistency | STATE_CORRUPTION | CRITICAL |
| Resource leak | MEMORY_PRESSURE | HIGH |
| Event flood | RUNTIME_ANOMALY | MEDIUM |
| Memory growth | MEMORY_PRESSURE | CRITICAL |
| Lost checkpoint | LIFECYCLE_LEAK | HIGH |
| Invalid transition | RUNTIME_ANOMALY | CRITICAL |

---

## Observer Performance Model — نموذج أداء المراقب

| Operation | Target Latency | Impact on Execution |
|---|---|---|
| TraceEvent recording | < 1ms | Non-blocking (async) |
| StateChange detection | < 5ms | Negligible |
| Drift detection | < 50ms | Parallel (separate thread) |
| Anomaly signal generation | < 20ms | Non-blocking |
| Memory recording integration | < 10ms | Non-blocking |

### Resource Budget
| Resource | Limit | Notes |
|---|---|---|
| Trace Stream memory | 50 MB max | Circular buffer |
| Drift detector CPU | 5% max | Sampling-based |
| State listener memory | 10 MB max | Stateless |

---

*The Live Observer Engine is the sensory nervous system of Stocky Engineering OS. It must be passive, accurate, and never interfere with execution.*

*محرك المراقبة المباشر هو الجهاز العصبي الحسي للنظام. يجب أن يكون سلبيًا ودقيقًا ولا يتداخل مع التنفيذ أبدًا.*
