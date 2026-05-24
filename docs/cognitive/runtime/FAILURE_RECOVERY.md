# Stocky Engineering OS — Failure Recovery Engine v0.1

---

> هذا الملف يحدد **محرك استرداد الفشل** — المسؤول عن إعادة النظام إلى حالة مستقرة عند أي فشل أثناء التنفيذ.
>
> This file defines the **Failure Recovery Engine** — responsible for returning the system to a stable state upon any execution failure.

---

## Core Principle — المبدأ الأساسي

```
Recovery rules:
  1. Recovery must NEVER mutate Doctrine files (SL-03)
  2. Recovery must be deterministic (AL-02)
  3. Every failure must produce a traceable root cause (CL-01)
  4. System must default to FAILED if recovery path is unclear (SL-04)
```

---

## Recovery Strategies — استراتيجيات الاسترداد

### Strategy Matrix

| Strategy | الوصف | Use Case |
|---|---|---|
| **rollback_step** | التراجع عن خطوة واحدة فقط | فشل في خطوة معزولة |
| **rollback_chain** | التراجع عن سلسلة خطوات حتى آخر checkpoint | فشل مع تأثير متسلسل |
| **full_rollback** | التراجع عن جميع الخطوات — إعادة التنفيذ من البداية | فشل كارثي في منتصف التنفيذ |
| **compensate** | تعويض تأثير الخطوة بدلاً من التراجع عنها | عمليات غير قابلة للتراجع (مثل إرسال بريد) |
| **safe_retry** | إعادة المحاولة مع تخفيض timeout/memory | فشل مؤقت (timeout, resource) |
| **quarantine** | عزل الحالة الفاشلة ومنع انتشارها | فشل مع احتمال state corruption |
| **skip** | تخطي الخطوة الفاشلة — إكمال الباقي | خطوة non-critical (مثل تحليل اختياري) |

### Strategy Selection Logic
```
if failure == PRECONDITION_FAILED:
    if node.retry_count > 0:
        strategy = safe_retry
    else:
        strategy = rollback_step

if failure == EXECUTION_ERROR:
    if error is recoverable (timeout, resource):
        strategy = safe_retry
    else:
        strategy = rollback_chain

if failure == POSTCONDITION_FAILED:
    if node.checkpoint:
        strategy = rollback_step (to checkpoint)
    else:
        strategy = rollback_chain (to last checkpoint)

if failure == STATE_CORRUPTION:
    strategy = quarantine (then full_rollback)

if failure == ANOMALY_CRITICAL:
    strategy = full_rollback

if no clear strategy:
    strategy = quarantine (default safe)
```

---

## 🟦 Rollback Execution — تنفيذ التراجع

### Rollback Flow
```
trigger_recovery(failed_node, reason, error_data):
    1. Log failure in Memory (type = FAILURE)
    2. Observer records anomaly (type = NODE_FAIL)
    3. State Machine: EXECUTING → RECOVERING
    4. Select recovery strategy based on failure type
    5. Execute recovery:
```

### Rollback Step (Single)
```
rollback_step(node):
    1. Execute node.rollback.action
    2. Verify rollback success
    3. If rollback fails → escalate to rollback_chain
    4. Record rollback in Memory (type = RECOVERY)
    5. Mark node.status = ROLLED_BACK
```

### Rollback Chain (To Checkpoint)
```
rollback_chain(from_node, to_checkpoint_node):
    1. Collect all nodes from from_node back to to_checkpoint_node
    2. Reverse order (last executed first)
    3. For each node in reverse order:
        a. Execute rollback
        b. Verify success
        c. If any rollback fails:
           - Mark all as ROLLED_BACK (partial)
           - State Machine → FAILED
           - Alert Governance Layer
    4. If all rollbacks succeed:
        a. State Machine → PLANNING
        b. Rebuild execution plan from checkpoint
```

### Full Rollback
```
full_rollback():
    1. Collect all executed nodes (status = SUCCESS or FAILED)
    2. Sort by reverse execution order
    3. Rollback each node
    4. Restore initial state snapshot (if available)
    5. State Machine → IDLE
    6. Record full rollback in Memory
    7. Notify Governance Layer
```

---

## 🟩 Safe Retry — إعادة المحاولة الآمنة

### Retry Rules
| Rule | التفاصيل |
|---|---|
| Max retries per node | 2 (configurable) |
| Backoff between retries | Exponential: 100ms, 500ms, 2s |
| Timeout multiplier | 1.5x each retry |
| State preservation | Retry does NOT change current state |
| Retry limit reached | Escalate to rollback |

### Retry Flow
```
safe_retry(node, failure_reason):
    1. Decrement node.retry_count
    2. Log retry attempt in Memory
    3. Apply backoff delay
    4. Check preconditions again
    5. Re-execute node.action
    6. Check postconditions again
    7. If success → continue execution normally
    8. If failure again → escalate to rollback strategy
```

### Retryable vs Non-Retryable Failures
| Retryable | Non-Retryable |
|---|---|
| Timeout | Compilation error |
| Resource temporarily unavailable | State corruption |
| Network transient failure | Permission denied |
| File temporarily locked | File not found |
| Rate limited | Invalid action type |

---

## 🟪 Quarantine Protocol — بروتوكول العزل

### When to Quarantine
```
1. State corruption detected
2. Memory integrity check failed
3. Irreversible failure with uncertain state
4. Anomaly with propagation_scope = runtime_wide
5. Recovery attempt failed
```

### Quarantine Flow
```
quarantine(affected_state):
    1. FREEZE current execution
    2. ISOLATE affected state:
        - Copy to quarantine zone
        - Disconnect from active execution
        - Mark as QUARANTINED
    3. RECORD quarantine in Memory:
        - state_snapshot
        - failure_reason
        - timestamp
    4. ANALYZE root cause:
        - Run diagnostics on quarantined state
        - Compare with expected state
        - Determine if recoverable
    5. DECIDE:
        - If recoverable → attempt recovery in sandbox
        - If not recoverable → FAILED (keep quarantine for investigation)
    
    IMPORTANT: Quarantine NEVER mutates active system state
```

### Quarantine State Lifecycle
```
QUARANTINED
    │
    ├──→ RECOVERED (after successful sandbox recovery)
    ├──→ MERGED (if state was valid after analysis)
    └──→ PURGED (after investigation + documentation)
```

---

## 🟨 Recovery Logging — تسجيل الاسترداد

### Recovery Record Structure
```yaml
RecoveryRecord:
  id: string
  execution_id: string
  failed_node_id: string
  failure_type: Enum              # PRECONDITION_FAILED | EXECUTION_ERROR | 
                                  # POSTCONDITION_FAILED | STATE_CORRUPTION | ANOMALY
  failure_reason: string
  strategy_used: Enum             # Strategy selected
  strategy_result: Enum           # SUCCESS | PARTIAL | FAILED
  rollback_nodes: [string]        # Nodes that were rolled back
  retry_attempts: number
  quarantine_used: boolean
  root_cause: string              # Determined root cause
  duration_ms: number             # Recovery duration
  timestamp: datetime
  integrity_hash: string          # SHA-256 of the record
```

---

## 📊 Recovery Scenarios — سيناريوهات الاسترداد

### Scenario 1: Timeout أثناء Compilation
```
Failure: Step 2 (compilation) times out after 30s
Strategy: safe_retry
  → Retry 1: timeout after 45s
  → Retry 2: timeout after 67s
  → Max retries reached
  → Escalate to rollback_step
  → Rollback Step 2 (revert file change)
  → Continue execution from Step 3 (if independent)
Result: PARTIAL (Step 2 rolled back, rest completed)
```

### Scenario 2: State Corruption بعد تعديل
```
Failure: Post-validation detects state inconsistency
Strategy: quarantine + full_rollback
  → Quarantine affected modules
  → Full rollback all executed steps
  → Restore initial snapshot
  → State Machine → IDLE
  → Notify Governance Layer
Result: FULL_ROLLBACK (system returned to pre-execution state)
```

### Scenario 3: Network Transient Failure
```
Failure: Step 4 (network call) fails with timeout
Strategy: safe_retry
  → Retry 1: success after 2s
  → Continue execution
Result: RECOVERED (normal continuation)
```

### Scenario 4: Non-Critical Step Failure
```
Failure: Step 6 (optional analysis) fails
Strategy: skip
  → Mark step as SKIPPED
  → Continue with remaining steps
  → Log warning in execution result
Result: COMPLETED_WITH_WARNINGS
```

---

## Recovery Rules Summary — ملخص قواعد الاسترداد

| Rule | Enforcement |
|---|---|
| Recovery never mutates Doctrine | Governance Layer verification |
| Recovery is deterministic | Same failure → same recovery strategy |
| Every failure has traceable root cause | Root cause recorded in RecoveryRecord |
| Default to FAILED if unclear | Fail-closed principle (SL-04) |
| Quarantine before state corruption spread | Automatic trigger |
| All recovery actions recorded in Memory | Append-only, immutable |

---

*The Failure Recovery Engine ensures that Stocky Engineering OS can withstand execution failures and return to a stable state without data loss or architectural drift.*

*محرك استرداد الفشل يضمن أن النظام يستطيع تحمل فشل التنفيذ والعودة إلى حالة مستقرة دون فقدان البيانات أو انحراف معماري.*
