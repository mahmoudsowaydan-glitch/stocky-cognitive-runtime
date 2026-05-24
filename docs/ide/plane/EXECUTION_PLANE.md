# Stocky Engineering OS — Execution Plane (CLI/TUI) v0.1

---

> هذا الملف يحدد **طائرة التنفيذ (Execution Plane)** — واجهة CLI/TUI المباشرة مع الـ Runtime والتحكمات الآمنة.
>
> This file defines the **Execution Plane** — the CLI/TUI interface for direct Runtime interaction and safe controls.

---

## Core Principle — المبدأ الأساسي

```
The Execution Plane is the nervous system access point.
طائرة التنفيذ هي نقطة الوصول إلى الجهاز العصبي.

Low latency · Live stream · Direct control · Minimal overhead
```

---

## Cognitive Session Context (Refinement #3) — سياق الجلسة الإدراكية

### Why Session Context?
بدون Session Context، الـ IDE يعاني من:
- mixed executions غير مرتبطة
- unclear user intent continuity
- broken reasoning history بين الأوامر

### Session Structure
```yaml
CognitiveSession:
  id: string                    # Unique session ID
  started_at: datetime
  last_active: datetime
  
  intent_vector: {              # ما الذي يحاول المستخدم تحقيقه في هذه الجلسة
    primary: string,            # التعديل الرئيسي (مثلاً: إضافة auth module)
    secondary: [string],        # مهام ثانوية
    confidence: float           # مدى وضوح الـ intent
  }
  
  active_context: {             # سياق التفكير النشط
    files_touched: [string],
    recent_decisions: [string],  # IDs من Decision Lineage
    current_focus: string,       # ما الذي يركز عليه المستخدم الآن
    related_incidents: [string]  # Incidents مفتوحة
  }
  
  execution_scope: {            # حدود التنفيذ لهذه الجلسة
    allowed_layers: [Enum],     # ما هي الـ Layers المسموح بتنفيذها
    max_budget_tier: Enum,       # أقصى Budget Tier مسموح
    sandbox_required: boolean,   # هل التنفيذ في Sandbox؟
    governance_override: boolean # هل يمكن تخطي Governance؟
  }
  
  history: [                    # سجل أوامر هذه الجلسة
    {
      command: string,
      timestamp: datetime,
      result: string,
      execution_id: string|null
    }
  ]
```

### Session Lifecycle
```
SESSION_START
    │
    ▼
INTENT_DEFINITION  ← المستخدم يحدد الـ intent (صراحة أو ضمنيًا)
    │
    ▼
ACTIVE            ← التنفيذ والمراقبة
    │
    ├──→ PAUSED   ← إيقاف مؤقت
    │       │
    │       └──→ ACTIVE
    │
    ├──→ COMPLETED ← اكتملت المهمة
    │
    └──→ ABANDONED ← المستخدم ترك الجلسة
```

### Session Rules
```
1. Session واحدة نشطة في كل مرة (single focus)
2. Session تنتهي تلقائيًا بعد 30 دقيقة من inactivity
3. Intent Vector يُحدَّث مع كل أمر جديد
4. Session History يُخزَّن في P3 Memory (type = SESSION_RECORD)
5. كل Execution Plan يرتبط بـ Session ID
```

---

## CLI Views — المشاهد النصية

### Main Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  STOCKY ENGINEERING OS  │  State: EXECUTING  │  Session: a3f │
├─────────────────────────────────────────────────────────────┤
│  ⚡ P3 State Machine: EXECUTING (step 4/12)                │
│  🛡 P4 Control: STABLE   │  Budget: MEDIUM (5 steps left)  │
│  🧠 P5 Identity: COHERENT (0.96)                           │
├─────────────────────────────────────────────────────────────┤
│  [00:00:01] Step 1/12: modify auth.js          ✓ DONE      │
│  [00:00:03] Step 2/12: update imports           ✓ DONE      │
│  [00:00:05] Step 3/12: add middleware          ✓ DONE      │
│  [00:00:07] Step 4/12: update routes           ◉ RUNNING   │
│  [00:00:09] Step 5/12: add tests               ⏳ PENDING   │
├─────────────────────────────────────────────────────────────┤
│  [PAUSE] [BUDGET +] [BUDGET -] [REASONING] [LOG] [Q:QUIT]  │
└─────────────────────────────────────────────────────────────┘
```

### Alert View
```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️ ALERT: Soft Drift detected in module auth              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Type:    ARCHITECTURAL_BOUNDARY                     │    │
│  │ Law:     AL-01 (Domain independence from runtime)   │    │
│  │ Source:  Drift Suppression Engine                   │    │
│  │ Severity: SOFT                                      │    │
│  │ Action:  WARNING — checkpoint added                 │    │
│  └────────────────────────────────────────────────────┘    │
│  [ACK] [INSPECT] [IGNORE]                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## CLI Commands — أوامر CLI

| Command | Description | Authority |
|---|---|---|
| `pause` | Pause execution | ✅ Safe |
| `resume` | Resume execution | ✅ Safe |
| `budget up` | Increase budget tier | ✅ Safe (max HIGH) |
| `budget down` | Decrease budget tier | ✅ Safe (min LOW) |
| `ack` | Acknowledge alert | ✅ Safe |
| `inspect <id>` | Open reasoning trace | ✅ Safe |
| `status` | Show system status | ✅ Safe |
| `session` | Show current session | ✅ Safe |
| `exit` | End session | ✅ Safe |

---

## Execution Plane Architecture

```
User Input (CLI)
    │
    ▼
┌──────────────────────────────────┐
│      CLI Command Parser          │
│  يقرأ الأمر ويصنفه:              │
│  - CONTROL (pause/resume)        │
│  - QUERY (status/inspect)        │
│  - NAVIGATION (view switch)      │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│      Session Manager            │
│  يحدّث Cognitive Session Context │
│  يربط الأمر بـ Session ID       │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│      Authority Check            │
│  هل الأمر مسموح؟ ← CONTROL_AUTHORITY.md
│  هل الـ UI action override ممكن؟
│  هل P4 يسمح بهذا الإجراء؟
└──────────┬───────────────────────┘
           │ if ALLOWED
           ▼
┌──────────────────────────────────┐
│      Action Router              │
│  يوجّه الأمر إلى الـ Layer المناسب
│  P3 (pause/resume)              │
│  P4 (budget adjust)             │
│  P2 (inspect reasoning)         │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│      Live Stream Manager        │
│  WebSocket / EventSource        │
│  يرسل التحديثات إلى CLI         │
│  يعرض الـ trace + state + alerts│
└──────────────────────────────────┘
```

---

## Live Stream Protocol

### Stream Events
| Event | Source | Content |
|---|---|---|
| `state_change` | P3 State Machine | `{ from, to, trigger }` |
| `step_update` | P3 Execution | `{ step_id, status, duration }` |
| `drift_alert` | P4 Drift Suppression | `{ type, severity, scope }` |
| `stability_change` | P4 Stability Monitor | `{ score, level }` |
| `budget_update` | P4 Budget System | `{ tier, steps_left, mode }` |

### Stream Format (JSON over WebSocket)
```json
{
  "type": "state_change",
  "timestamp": "2026-05-24T14:30:00.000Z",
  "data": {
    "from": "EXECUTING",
    "to": "VERIFYING",
    "trigger": "step_complete"
  },
  "session_id": "a3f1b2"
}
```

---

*The Execution Plane is the live nerve center of Stocky Engineering OS. Every cognitive event, every execution step, every control decision is visible in real-time.*

*طائرة التنفيذ هي مركز الأعصاب الحي للنظام. كل حدث إدراكي، كل خطوة تنفيذ، كل قرار تحكم — مرئي في الوقت الفعلي.*
