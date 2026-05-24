# Stocky Engineering OS — Safe Controls v0.1

---

> هذا الملف يحدد **التحكمات الآمنة** التي يمكن للمستخدم تنفيذها من IDE Surface Layer: ما هي الإجراءات المسموحة، نطاقها، وشروطها.
>
> This file defines the **Safe Controls** that the user can execute from the IDE Surface Layer: what actions are allowed, their scope, and conditions.

---

## Safe Action Catalog — كتالوج الإجراءات الآمنة

### Execution Controls

| Action | يؤثر على | Safe Range | متى؟ |
|---|---|---|---|
| `pause` | P3 Execution Engine | Full stop | Only during EXECUTING or VERIFYING |
| `resume` | P3 Execution Engine | Continue from pause | Only when state = PAUSED |
| `step_forward` | P3 Execution Engine | Next single step | Only when PAUSED (debug mode) |

### Budget Controls

| Action | يؤثر على | Safe Range | متى؟ |
|---|---|---|---|
| `budget up` | P4 Budget System | LOW → MEDIUM → HIGH | Only during PLANNING or EXECUTING |
| `budget down` | P4 Budget System | HIGH → MEDIUM → LOW | Only during PLANNING or EXECUTING |
| `budget reset` | P4 Budget System | Back to default | Only when IDLE |

### Alert Controls

| Action | يؤثر على | Safe Range | متى؟ |
|---|---|---|---|
| `ack alert` | P4 Drift Suppression | Acknowledge + remove from active | Only for SOFT/MEDIUM drifts |
| `ignore alert` | P4 Drift Suppression | Dismiss | Only for SOFT drifts |
| `inspect alert` | P5 Lineage (read) | Read-only | Always |

### Governance Controls

| Action | يؤثر على | Safe Range | متى؟ |
|---|---|---|---|
| `approve pending` | P2 Governance Layer | Accept pending plan | Only if verdict = REQUIRE_APPROVAL |
| `reject pending` | P2 Governance Layer | Reject pending plan | Only if verdict = REQUIRE_APPROVAL |
| `modify plan` | P2 Governance Layer | Add conditions | Only if verdict = REQUIRE_APPROVAL |

---

## Action Execution Flow

```
User Action
    │
    ▼
1. PARSE — Identify action type
    │
    ▼
2. AUTHORITY CHECK — Is action in Safe Controls catalog?
    │  If NO → BLOCK + "Action not available"
    ▼
3. CONTEXT CHECK — Is state appropriate for this action?
    │  If NO → BLOCK + "Action not available in current state"
    ▼
4. P4 OVERRIDE CHECK — Does P4 allow this action?
    │  If NO → BLOCK + "Control Plane prevents this action"
    ▼
5. EXECUTE — Route to appropriate layer
    │
    ▼
6. RECORD — Log action in P3 Memory
    │
    ▼
7. FEEDBACK — Return result to IDE
```

---

## Action State Matrix

| Action | IDLE | PLANNING | EXECUTING | VERIFYING | RECOVERING | FAILED | COMPLETED |
|---|---|---|---|---|---|---|---|
| pause | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| resume | ❌ | ❌ | ❌[^1] | ❌ | ❌ | ❌ | ❌ |
| budget up | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| budget down | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| ack alert | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| inspect | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| approve | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌[^2] |

[^1]: Resume only possible when state is explicitly PAUSED (a sub-state of EXECUTING)
[^2]: Approve only available when Governance verdict = REQUIRE_APPROVAL

---

## Parameter Limits

### Budget Adjust Limits
```
Maximum: HIGH tier (cannot set to CRITICAL)
Minimum: LOW tier (cannot set to ZERO)
Step: 1 tier per action
Cooldown: 5 seconds between adjustments
```

### Approval Limits
```
Approve: Only for REQUIRE_APPROVAL verdicts
Reject: Only for REQUIRE_APPROVAL verdicts
Modify: Only within alternative options provided by P2 Layer 4
```

---

## Safety Failure Modes

| Situation | نظامي | يحدث |
|---|---|---|
| User tries CRITICAL budget | BLOCK | Budget remains unchanged |
| User pauses when IDLE | BLOCK | No effect |
| User ignores HARD drift | BLOCK | Drift remains active |
| Action times out | BLOCK | User notified |
| P4 blocks user action | BLOCK | P4 reason displayed |

---

## Audit Logging

كل Safe Control يُسجل:
```yaml
UserActionRecord:
  action: string
  timestamp: datetime
  session_id: string
  state_before: Enum
  state_after: Enum
  result: Enum                  # SUCCESS | BLOCKED | FAILED
  block_reason: string|null     # If BLOCKED
  layer_affected: Enum
  memory_id: string             # Reference in P3 Memory
```

---

*Safe Controls define exactly what the user can and cannot do through the IDE. Any action outside this catalog is automatically blocked.*

*التحكمات الآمنة تحدد بالضبط ما يمكن للمستخدم وما لا يمكنه فعله من خلال الـ IDE. أي إجراء خارج هذا الكتالوج يتم منعه تلقائيًا.*
