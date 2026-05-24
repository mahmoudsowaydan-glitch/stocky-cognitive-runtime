# Stocky Engineering OS — Runtime State Machine v0.1

---

> هذا الملف يحدد **حالات الـ Runtime الرسمية** للنظام. كل عملية تنفيذ تمر عبر State Machine صارمة — لا يُسمح بتخطي أي حالة أو انتقال غير مصرح به.
>
> This file defines the **official Runtime states** of the system. Every execution passes through a strict State Machine — no state skipping or unauthorized transitions are allowed.

---

## State Definitions — تعريفات الحالات

```
                          ┌─────────┐
                          │  IDLE   │
                          └────┬────┘
                               │ plan received
                               ▼
                          ┌──────────┐
              ┌──────────▶│ PLANNING │◀──────────┐
              │           └─────┬────┘            │
              │                 │ graph ready     │
              │                 ▼                 │
              │           ┌───────────┐           │
              │           │ EXECUTING │           │
              │           └──┬───┬────┘           │
              │              │   │                │
              │     success  │   │  anomaly       │
              │              │   ▼                │
              │              │  ┌────────────┐   │
              │              │  │ VERIFYING   │   │
              │              │  └──┬──────┬───┘   │
              │              │     │      │       │
              │         pass │     │ fail │       │
              │              │     │      │       │
              │              ▼     ▼      │       │
              │         ┌──────────┐      │       │
              │         │COMPLETED │      │       │
              │         └──────────┘      │       │
              │                           ▼       │
              │                    ┌────────────┐ │
              │                    │ RECOVERING │─┘
              │                    └──┬──────┬──┘
              │                       │      │
              │                success│      │fail
              │                       │      │
              │                       ▼      ▼
              │                    ┌──────────┐
              └────────────────────│  FAILED  │
                                   └──────────┘
```

### State Descriptions

| State | المعنى | مسموح بالتنفيذ؟ |
|---|---|---|
| **IDLE** | النظام في حالة سكون — ينتظر Execution Plan | لا |
| **PLANNING** | تحويل الـ Plan إلى Execution Graph وترتيب الـ nodes | لا (تحضير فقط) |
| **EXECUTING** | تنفيذ خطوات الـ Graph — يمكن أن يكون I/O أو calculation | نعم |
| **VERIFYING** | التحقق من صحة التنفيذ — post-validation لكل خطوة | لا (تحقق فقط) |
| **RECOVERING** | استرداد النظام بعد فشل — rollback أو تعويض | نعم (عمليات استرداد فقط) |
| **FAILED** | الفشل النهائي — الـ Execution Plan لم يكتمل | لا |
| **COMPLETED** | النجاح — الـ Execution Plan اكتمل بالكامل | لا |

---

## Strict Transition Rules — قواعد الانتقال الصارمة

### Allowed Transitions

| From | To | الشرط |
|---|---|---|
| IDLE | PLANNING | استلام Execution Plan صحيح من Reasoning Pipeline |
| PLANNING | EXECUTING | اكتمال بناء Execution Graph + اجتياز Governance validation |
| EXECUTING | EXECUTING | خطوة جديدة في الـ Graph (تكرار مسموح) |
| EXECUTING | VERIFYING | اكتمال جميع steps في الـ Graph |
| EXECUTING | RECOVERING | اكتشاف anomaly أثناء التنفيذ |
| EXECUTING | FAILED | فشل غير قابل للاسترداد (no recovery path) |
| VERIFYING | COMPLETED | اجتياز جميع post-validations |
| VERIFYING | RECOVERING | فشل post-validation |
| RECOVERING | PLANNING | نجاح الاسترداد → إعادة تخطيط الـ Recovery Plan |
| RECOVERING | FAILED | فشل الاسترداد — لا يمكن التعافي |
| RECOVERING | IDLE | نجاح الاسترداد + عدم وجود further steps للتنفيذ |
| FAILED | IDLE | إعادة تعيين يدوي (manual reset) |
| COMPLETED | IDLE | إعادة تعيين تلقائي (auto-reset) |

### Forbidden Transitions (Violations)

| From | To | سبب المنع |
|---|---|---|
| IDLE | EXECUTING | تخطي Planning = تنفيذ بدون خطة |
| IDLE | COMPLETED | تنفيذ بدون بدء |
| PLANNING | COMPLETED | تخطي التنفيذ والتحقق |
| PLANNING | RECOVERING | لا يوجد فشل بعد — لم يبدأ التنفيذ |
| EXECUTING | COMPLETED | يجب المرور على VERIFYING |
| EXECUTING | IDLE | لا يمكن العودة مباشرة إلى الخمول أثناء التنفيذ |
| RECOVERING | COMPLETED | يجب العودة إلى PLANNING أولاً |
| FAILED | EXECUTING | لا يمكن متابعة التنفيذ بعد الفشل النهائي |
| FAILED | COMPLETED | لا يمكن إعلان النجاح بعد الفشل |
| COMPLETED | EXECUTING | لا يمكن إعادة التنفيذ بدون reset |

---

## State Machine Validation Rules

### Rule 1: No State Skipping
```
Transition path must be contiguous.
Violation → governance_verdict = BLOCK + incident recorded
```

### Rule 2: Single Active State
```
Only one state can be active at any time.
Parallel execution is isolated within EXECUTING state only.
```

### Rule 3: State Timeout
| State | Max Duration | Action on Timeout |
|---|---|---|
| PLANNING | 5s | Log warning + return to IDLE |
| EXECUTING | 30s (configurable) | Force transition to RECOVERING |
| VERIFYING | 10s | Force transition to RECOVERING |
| RECOVERING | 30s | Force transition to FAILED |

### Rule 4: State Entry/Exit Hooks
```
Every state transition triggers:
  - onEnter(state): Observer records entry event
  - onExit(state): Observer records exit event + duration
  - onError(state, error): Recovery Engine evaluates
```

---

## State Data Structure — هيكل بيانات الحالة

```yaml
RuntimeState:
  current: Enum           # IDLE | PLANNING | EXECUTING | VERIFYING | RECOVERING | FAILED | COMPLETED
  previous: Enum          # الحالة السابقة (للتراجع)
  transitions: [          # سجل جميع الانتقالات
    {
      from: Enum,
      to: Enum,
      timestamp: datetime,
      trigger: string,      # سبب الانتقال
      duration_ms: number
    }
  ]
  execution_id: string    # معرف عملية التنفيذ الحالية
  started_at: datetime
  updated_at: datetime
  error: object|null      # آخر خطأ (إن وجد)
```

---

## State Machine Guards — حراس الحالة

### Pre-Transition Guard
```
قبل أي انتقال، الـ Guard يتحقق:
  1. هل الانتقال مصرح به؟ (Transition Matrix)
  2. هل الحالة الحالية == المطلوبة؟
  3. هل انتهى Timeout الحالي؟
  4. هل هناك أي pending locks أو operations؟

إذا فشل أي شرط → BLOCK + تسجيل Violation
```

### Post-Transition Guard
```
بعد أي انتقال، الـ Guard يسجل:
  1. الانتقال في Audit Trail
  2. الوقت المستغرق في الحالة السابقة
  3. أي pending anomalies من Observer
  4. تحديث الحالة في Memory Record
```

---

*The Runtime State Machine is the backbone of all execution in Stocky Engineering OS. Any modification to states or transitions must pass through Governance Layer and be recorded in an ADR.*

*هذه الـ State Machine هي العمود الفقري لكل تنفيذ في النظام. أي تعديل في الحالات أو الانتقالات يجب أن يمر عبر طبقة Governance ويُسجل في ADR.*
