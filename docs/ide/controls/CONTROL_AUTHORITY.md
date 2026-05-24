# Stocky Engineering OS — Control Authority Model v0.1

---

> هذا الملف يحدد **نموذج سلطة التحكم** — من يمكنه اتخاذ القرارات، من يمكنه تجاوز من، ومتى يتم حل النزاعات بين المصادر المختلفة.
>
> This file defines the **Control Authority Model** — who can make decisions, who can override whom, and when conflicts between different sources are resolved.

---

## Core Principle — المبدأ الأساسي

```
No UI action can override Control Plane decisions.
لا يمكن لأي إجراء من الـ UI تجاوز قرارات طبقة التحكم.
```

---

## Authority Precedence Stack (Refinement #2) — سلم الأولويات

### The Stack
```
Priority 1 (HIGHEST):  P4 — Control Plane
Priority 2:             P3 — Execution Engine
Priority 3:             UI — User Actions (via IDE)
Priority 4:             P5 — Coherence Observer (read-only)
Priority 5:             P2 — Doctrine (constraints source, not active controller)
```

### What This Means
```
P4 (Control) > P3 (Execution) > UI (User Actions) > P5 (Observer) > P2 (Doctrine Source)

أي قرار من مستوى أعلى يلغي أي قرار من مستوى أدنى.
Any decision from a higher level overrides any decision from a lower level.
```

### Examples
| Conflict | Resolution |
|---|---|
| UI يقول "resume" و P4 يقول "HALT" | P4 يكسب → يبقى HALT |
| UI يقول "budget HIGH" و P3 يقول "EXECUTING" | P3 يكسب → انتظر حتى IDLE |
| UI يقول "pause" و P5 يقول "coherent" | UI يكسب (P5 read-only) |
| P4 يقول "BLOCK" و P3 يقول "allow" | P4 يكسب → BLOCK |

---

## CAN / CANNOT Matrix — مصفوفة المسموح والممنوع

### By Layer

| Action | P2 Doctrine | P3 Runtime | P4 Control | P5 Coherence | UI (User) |
|---|---|---|---|---|---|
| Modify Laws | ✅ (via ADR) | ❌ | ❌ | ❌ | ❌ |
| Pause Execution | ❌ | ✅ | ✅ (override) | ❌ | ✅ (safe) |
| Resume Execution | ❌ | ✅ | ✅ (override) | ❌ | ✅ (safe) |
| Adjust Budget | ❌ | ❌ | ✅ | ❌ | ✅ (safe range) |
| HALT Execution | ❌ | ✅ | ✅ (override) | ❌ (read-only) | ❌ |
| BLOCK Execution | ❌ | ❌ | ✅ | ❌ | ❌ |
| Issue Drift Verdict | ❌ | ❌ | ✅ | ❌ | ❌ |
| Approve Governance | ❌ | ❌ | ❌ | ❌ | ✅ (limited) |
| Record Memory | ❌ | ✅ | ❌ | ❌ | ❌ |
| Query Lineage | ❌ | ❌ | ❌ | ✅ | ✅ (read-only) |
| Calculate Identity | ❌ | ❌ | ❌ | ✅ | ❌ |
| Delete Memory | ❌ | ❌ | ❌ | ❌ | ❌ |
| Override P4 Decision | ❌ | ❌ | ❌ | ❌ | ❌ |

### By Entity Type

| Entity | Can Read | Can Write | Can Control | Can Override |
|---|---|---|---|---|
| **P4 Control Plane** | All layers | P3 (pause/resume), P4 self | All layers | P3, UI |
| **P3 Execution Engine** | P2, P3, P4 (monitor) | P3 self | P3 self | UI |
| **UI (User via IDE)** | All layers | P3 (pause/resume), P4 (safe budget) | Limited (safe controls) | Nothing |
| **P5 Coherence** | All layers | Nothing | Nothing | Nothing |
| **P2 Doctrine** | P2 self | P2 self (via ADR) | Nothing (constraint source) | Nothing |

---

## Authority Conflict Resolution

### Conflict Detection
```
When two entities issue conflicting commands:
1. Identify the priority level of each source
2. Higher priority wins automatically
3. Lower priority source is notified of the override
4. Conflict is recorded in P3 Memory (type = AUTHORITY_CONFLICT)
```

### Conflict Record
```yaml
AuthorityConflict:
  id: string
  timestamp: datetime
  entities: [string]            # Conflicting sources
  commands: [string]            # Conflicting commands
  resolution: {
    winner: string,             # Entity that won
    reason: string,             # Why (priority level)
    loser_notified: boolean
  }
  memory_id: string
```

### UI-Specific Conflict Rules
```
Rule 1: UI pause request while P4 active HALT → BLOCK + "P4 has halted execution"
Rule 2: UI resume request while P4 active PAUSE → BLOCK + "P4 has paused execution"
Rule 3: UI budget adjust while P4 in COMPRESS mode → BLOCK + "P4 is in compression mode"
Rule 4: UI approve while P5 detected contradiction → BLOCK + "Coherence conflict detected"
Rule 5: UI action during RECOVERING → BLOCK + "System is recovering"
```

---

## Control Privilege Escalation

### Normal Operation
```
User ← Safe Controls only
P3 ← Normal execution
P4 ← Normal monitoring
```

### Emergency Override (P4 only)
P4 يمكنه:
- HALT أي execution (حتى لو المستخدم قال resume)
- BLOCK أي plan (حتى لو Governance قال ALLOW)
- تخفيض Budget (حتى لو المستخدم رفعه)
- عزل Module (حتى لو P3 ينفذ فيه)

### P4 Cannot
- تعديل Laws
- حذف Memory
- تغيير State Machine rules
- تجاوز P5 identity calculation

---

## Authority Audit Trail

كل Authority Conflict يُسجل مع:
```yaml
AuthorityRecord:
  id: string
  timestamp: datetime
  action: string
  initiator: string             # Entity that initiated
  target_layer: string
  allowed: boolean
  override_source: string|null  # If overridden
  override_reason: string|null
  session_id: string|null
  memory_id: string
```

---

*The Control Authority Model ensures that Stocky Engineering OS remains safe even when multiple entities issue commands. The stack is clear: Control > Execution > UI > Observation.*

*نموذج سلطة التحكم يضمن أن النظام يبقى آمنًا حتى عندما تصدر كيانات متعددة أوامر. السلم واضح: التحكم > التنفيذ > واجهة المستخدم > المراقبة.*
