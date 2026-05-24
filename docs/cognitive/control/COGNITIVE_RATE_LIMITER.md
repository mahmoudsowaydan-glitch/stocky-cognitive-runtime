# Stocky Engineering OS — Cognitive Rate Limiter v0.1

---

> هذا الملف يحدد **محدد التدفق الإدراكي** — Context-aware throttling system الذي ينظم تدفق الأحداث والتفكير بناءً على نوع الحدث وحالة النظام ومستوى الخطورة.
>
> This file defines the **Cognitive Rate Limiter** — a context-aware throttling system that regulates event flow and reasoning based on event type, system state, and risk level.

---

## Core Principle — المبدأ الأساسي

```
ليس كل الأحداث متساوية.
Not all events are equal.

Rate = f(event_type, system_state, risk_level)
Rate ≠ constant
```

---

## Load Calculation — حساب الحِمل

### Formula
```
Load = f(event_type, system_state, risk_level) × priority_factor

حيث:
  event_type_weight: وزن نوع الحدث (جدول أدناه)
  system_state: حالة الـ Runtime الحالية (IDLE, EXECUTING, RECOVERING, ...)
  risk_level: مستوى الخطورة الحالي (LOW, MEDIUM, HIGH, CRITICAL)
  priority_factor: user_request > system_agent > telemetry
```

### Event Type Weights
| Event Type | Weight | Typical Frequency |
|---|---|---|
| USER_REQUEST | 1.0 | Low |
| USER_OVERRIDE | 1.0 (ignores limit) | Very Low |
| SYSTEM_AGENT | 0.7 | Medium |
| RUNTIME_OBSERVER | 0.4 | High |
| DRIFT_DETECTOR | 0.6 | Medium |
| TELEMETRY | 0.2 | Very High |
| ANOMALY_SIGNAL | 0.8 | Low |
| EXTERNAL_INTEGRATION | 0.5 | Low |

### System State Multipliers
| State | Multiplier | Reason |
|---|---|---|
| IDLE | 1.0 | Normal operation |
| PLANNING | 0.7 | System busy thinking |
| EXECUTING | 0.5 | System busy executing |
| VERIFYING | 0.6 | Under verification |
| RECOVERING | 0.2 | Critical — تقليل التحميل |
| FAILED | 0.1 | Almost zero — فقط أساسي |
| COMPLETED | 1.0 | Ready for new tasks |

### Risk Level Multipliers
| Risk Level | Multiplier | Reason |
|---|---|---|
| LOW | 1.0 | Normal throughput |
| MEDIUM | 0.7 | Reduce non-critical |
| HIGH | 0.4 | Only essential events |
| CRITICAL | 0.1 | Emergency mode |

---

## Throttling Strategies — استراتيجيات التحديد

| Strategy | الوصف | متى يُستخدم |
|---|---|---|
| **QUEUE** | وضع الحدث في طابور انتظار | Load > 0.7 |
| **DELAY** | تأخير معالجة الحدث بمدة | Load > 0.8 |
| **SAMPLE** | معالجة عينة فقط من الأحداث (مثلاً كل 3) | Telemetry flood |
| **DROP** | تجاهل الحدث (غير مهم) | Non-critical + Load > 0.9 |
| **BACKOFF** | Exponential backoff — تأخير متزايد | Repetitive anomalies |

### Strategy Selection
```
إذا كان event_type = TELEMETRY و Load > 0.8:
    strategy = SAMPLE (rate = 1:3)
إذا كان event_type = RUNTIME_OBSERVER و Load > 0.9:
    strategy = SAMPLE (rate = 1:2)
إذا كان هناك anomaly متكرر (نفس type 3x في دقيقة):
    strategy = BACKOFF (base = 1s, factor = 2x)
إذا كان Load > 0.8:
    strategy = DELAY (delay = 500ms × load_factor)
إذا كان Load > 0.95:
    strategy = QUEUE (قدرة queue = 100 event)
إذا كان event غير مهم + Load > 0.9:
    strategy = DROP (مع تسجيل)
إذا كان event = USER_REQUEST:
    strategy = PASS (دائمًا)
```

---

## Backoff Algorithm — خوارزمية التأخير المتزايد

```
BackoffSchedule:
  base_delay: 1s
  max_delay: 30s
  factor: 2.0                    # مضاعف التأخير
  reset_after: 60s               # إعادة تعيين بعد 60 ثانية من الهدوء
  
  backoff(attempt):
    delay = min(base_delay × (factor ^ attempt), max_delay)
    return delay
```

### Backoff States
| Attempt | Delay | Cumulative |
|---|---|---|
| 1 | 1s | 1s |
| 2 | 2s | 3s |
| 3 | 4s | 7s |
| 4 | 8s | 15s |
| 5 | 16s | 31s |
| 6 | 30s (max) | 61s |
| 7+ | 30s | — |

---

## Queue Management — إدارة الطابور

```yaml
EventQueue:
  capacity: 100                 # الحد الأقصى للأحداث في الطابور
  current_load: number          # عدد الأحداث حاليًا
  strategy: Enum                # FIFO | PRIORITY (حسب event_type)
  drop_policy: Enum             # DROP_OLDEST | DROP_LOWEST_PRIORITY
  max_wait_ms: 30000            # أقصى مدة انتظار في الطابور (بعدها DROP)
```

### Queue Rules
```
1. إذا queue ممتلئة → طبق drop_policy
2. USER_REQUEST دائمًا في المقدمة (priority)
3. أي event ينتظر > max_wait_ms → DROP + تسجيل
4. queue تُفرّغ عندما يعود Load < 0.5
```

---

## Rate Limit Data Structure

```yaml
RateLimitState:
  current_load: float           # 0.0 - 1.0
  strategy: Enum                # PASS | QUEUE | DELAY | SAMPLE | DROP | BACKOFF
  active_backoff: {             # إذا strategy = BACKOFF
    event_type: string,
    attempt: number,
    next_available_at: datetime
  }
  queue_depth: number           # If strategy = QUEUE
  sample_rate: string           # If strategy = SAMPLE (e.g., "1:3")
  delay_ms: number              # If strategy = DELAY
  last_action: datetime
  events_dropped_total: number  # Counter
```

---

*The Cognitive Rate Limiter ensures the system maintains a healthy cognitive load — preventing flood, prioritizing users, and protecting recovery states.*

*محدد التدفق الإدراكي يضمن أن النظام يحافظ على حمل إدراكي صحي — يمنع الفيضان، يعطي الأولوية للمستخدمين، ويحمي حالات الاسترداد.*
