# Stocky Engineering OS — Action Flow v0.1

---

> هذا الملف يحدد **تدفق الإجراءات** — كيف تنتقل الأوامر من الـ IDE Surface Layer عبر طبقات النظام إلى التنفيذ.
>
> This file defines the **Action Flow** — how commands travel from the IDE Surface Layer through the system layers to execution.

---

## Core Flow — التدفق الأساسي

```
USER (IDE)
   │
   │  Command
   ▼
┌─────────────────────────────────────┐
│      1. USER ACTION LAYER           │
│  - Parse command from CLI/Web       │
│  - Validate syntax                  │
│  - Identify action type             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      2. AUTHORITY CHECK             │
│  - Is action in SAFE_CONTROLS?      │
│  - Is user allowed?                 │
│  - Is state appropriate?            │
└──────────────┬──────────────────────┘
               │ if ALLOWED
               ▼
┌─────────────────────────────────────┐
│      3. SESSION CONTEXT             │
│  - Update CognitiveSession          │
│  - Link to active session           │
│  - Record intent                    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      4. P4 AUTHORITY OVERRIDE       │
│  - Does P4 block this action?       │
│  - Authority Precedence Stack       │
│  - (P4 > P3 > UI)                   │
└──────────────┬──────────────────────┘
               │ if NOT overridden
               ▼
┌─────────────────────────────────────┐
│      5. ACTION ROUTER               │
│  - Direct to appropriate layer      │
│  - pause/resume → P3 Engine         │
│  - budget adjust → P4 Budget        │
│  - ack alert → P4 Drift            │
│  - query → P3 Memory / P5 Lineage  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      6. EXECUTE & MONITOR           │
│  - Execute the action               │
│  - Observer records trace           │
│  - Memory records outcome           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      7. FEEDBACK TO USER            │
│  - Return result                    │
│  - Update IDE display               │
│  - Notify if failure                │
└─────────────────────────────────────┘
```

---

## Action Types — أنواع الإجراءات

### Type 1: Control Actions (Pause/Resume/Budget)
```
مسار:
  CLI/Web → Authority Check → Session → P4 Override Check → P3 (or P4) → Feedback

خطورة: MEDIUM
مدة: < 100ms
تسجيل: إلزامي في P3 Memory
```

### Type 2: Query Actions (Inspect/Search/Status)
```
مسار:
  CLI/Web → Authority Check → Layer Query → Memory/P5 → Format → Feedback

خطورة: LOW
مدة: < 500ms
تسجيل: اختياري
```

### Type 3: Governance Actions (Approve/Reject)
```
مسار:
  CLI/Web → Authority Check → Session → P4 Override Check → P2 Governance → P5 Lineage → Feedback

خطورة: HIGH
مدة: < 1s
تسجيل: إلزامي + Lineage تحديث
```

### Type 4: Navigation Actions (View Switch)
```
مسار:
  CLI/Web → Session (update focus) → Load view → Feedback

خطورة: LOW
مدة: < 200ms
تسجيل: Session history only
```

---

## Action Flow Examples

### Example 1: User pauses execution
```
[CLI] pause
    → AUTHORITY CHECK: pause allowed? ✓
    → SESSION: session:a3f, action:pause
    → P4 CHECK: P4 not blocking pause? ✓
    → ROUTE to P3: Pause Execution Engine
    → P3: State Machine EXECUTING → PAUSED
    → OBSERVER: records state_change
    → MEMORY: records UserAction
    → FEEDBACK: "Execution paused at step 4/12"
```

### Example 2: User adjusts budget up
```
[Web] budget up
    → AUTHORITY CHECK: budget adjust allowed? ✓
    → STATE CHECK: is EXECUTING? ✓
    → RANGE CHECK: can go MEDIUM→HIGH? ✓
    → SESSION: session:a3f, action:budget_up
    → P4 CHECK: P4 not in COMPRESS mode? ✓
    → ROUTE to P4: Adjust Budget tier
    → P4: Budget MEDIUM → HIGH, steps 5→12
    → MEMORY: records UserAction
    → FEEDBACK: "Budget increased to HIGH (12 steps)"
```

### Example 3: User inspects incident
```
[Web] inspect inc-a3f1
    → AUTHORITY CHECK: inspect allowed? ✓
    → ROUTE to P5: Query Decision Lineage for inc-a3f1
    → P5: Returns lineage chain + identity context
    → ROUTE to P3: Query Memory for related records
    → P3: Returns execution traces + reasoning output
    → FORMAT: Combine into incident detail view
    → FEEDBACK: Render incident detail in IDE
```

---

## Action Timeouts

| Action Type | Timeout | On Timeout |
|---|---|---|
| Control (pause/resume) | 2s | Retry 1x → then FAIL + notify |
| Query (inspect/search) | 5s | Return partial results + warning |
| Governance (approve) | 10s | FAIL + notify user |
| Budget adjust | 2s | FAIL + keep current budget |

---

## Action Sequencing Rules

```
1. Cannot pause if already paused
2. Cannot resume if not paused
3. Cannot budget up if already on HIGH tier
4. Cannot budget down if already on LOW tier
5. Cannot approve if no pending governance request
6. Cannot inspect if incident ID is invalid
```

---

## Error Handling

| Error | User Feedback | System Action |
|---|---|---|
| Action not allowed | "This action is not available" | Log attempt |
| Wrong state | "Cannot pause when system is IDLE" | No change |
| P4 override | "Control Plane prevents this action: [reason]" | Record conflict |
| Timeout | "Action timed out — please try again" | Retry handler |
| Invalid input | "Invalid command: [details]" | No change |

---

*The Action Flow defines the complete journey of every user command through the Stocky Engineering OS — from IDE click to system execution to user feedback.*

*تدفق الإجراءات يحدد الرحلة الكاملة لكل أمر مستخدم عبر النظام — من نقرة IDE إلى تنفيذ النظام إلى ردود الفعل للمستخدم.*
