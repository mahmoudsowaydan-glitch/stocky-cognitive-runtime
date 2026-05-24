# Stocky Engineering OS — Execution Engine v0.1

---

> هذا الملف يحدد **محرك التنفيذ** — المسؤول عن تحويل الـ Execution Plan من Reasoning Pipeline إلى Graph تنفيذي وتنفيذه خطوة بخطوة.
>
> This file defines the **Execution Engine** — responsible for converting the Execution Plan from the Reasoning Pipeline into an executable Graph and executing it step by step.

---

## Core Data Structures — هياكل البيانات الأساسية

### ExecutionGraph
```yaml
ExecutionGraph:
  id: string                    # Unique identifier
  plan_id: string               # Reference to original Execution Plan
  nodes: [ExecutionNode]        # Ordered list of execution steps
  edges: [Edge]                 # Dependencies between nodes
  metadata: {
    created_at: datetime,
    node_count: number,
    estimated_duration_ms: number,
    risk_level: Enum            # LOW | MEDIUM | HIGH | CRITICAL
  }
```

### ExecutionNode
```yaml
ExecutionNode:
  id: string                    # e.g., "step-001"
  action: string                # وصف الإجراء
  action_type: Enum             # MODIFY_FILE | RUN_COMMAND | READ_ANALYSIS | VALIDATE | NETWORK_CALL
  
  preconditions: [Condition]    # شروط مسبقة يجب توفرها قبل التنفيذ
    - type: Enum                # FILE_EXISTS | STATE_IS | DEP_CLEAN | PERMISSION_OK
      target: string
      expected: string
  
  postconditions: [Condition]   # شروط لاحقة للتحقق بعد التنفيذ
    - type: Enum                # FILE_COMPILES | TEST_PASSES | STATE_VALID | DEP_OK
      target: string
      expected: string
  
  risk_level: Enum              # LOW | MEDIUM | HIGH | CRITICAL
  rollback: RollbackAction      # إجراء التراجع عن هذه الخطوة
  timeout_ms: number            # الحد الأقصى لمدة التنفيذ
  retry_count: number           # عدد محاولات إعادة المحاولة المسموحة
  checkpoint: boolean           # هل هذه نقطة تفتيش؟
  
  dependencies: [string]        # IDs of nodes that must complete first
  depends_on: [string]          # المعرّفات التي تعتمد عليها هذه الخطوة
```

### Edge
```yaml
Edge:
  from: string                  # Source node ID
  to: string                    # Target node ID
  type: Enum                    # SEQUENTIAL | PARALLEL_SAFE | DATA_DEPENDENCY
```

### RollbackAction
```yaml
RollbackAction:
  strategy: Enum                # REVERT_FILE | UNDO_COMMAND | COMPENSATE | RESTORE_SNAPSHOT
  action: string                # وصف إجراء التراجع
  data: object|null             # بيانات إضافية للتراجع (مثلاً المحتوى الأصلي للملف)
```

---

## Graph Construction — بناء الـ Graph

### Algorithm
```
Input: ExecutionPlan (from Reasoning Pipeline Layer 6)
Output: ExecutionGraph

1. For each step in Plan.steps:
     a. Create ExecutionNode with:
        - id, action, action_type
        - preconditions from step.validation
        - postconditions from step.validation
        - rollback from step.rollback
        - risk_level from step.risk_level
        - checkpoint from plan.checkpoints
        - timeout from plan.config
        - retry_count default = 1
    
     b. Add node to graph.nodes

2. For each dependency in Plan:
     a. Create Edge between dependent nodes
     b. Add edge to graph.edges

3. Validate Graph:
     a. Check for cycles (DAG verification)
     b. Check for missing dependencies
     c. Check for orphan nodes
     d. If validation fails → return to Layer 5 (Governance)

4. Calculate metadata:
     a. node_count = len(nodes)
     b. estimated_duration = sum of timeouts
     c. risk_level = max of node risk_levels
     d. Checkpoint placement validation
```

### DAG Rules — قواعد الـ Directed Acyclic Graph
| Rule | Violation consequence |
|---|---|
| No cycles | Cycle → BLOCK + rebuild graph |
| Every node reachable | Orphan → warning + auto-link to start |
| Checkpoints every N steps | Missing → warning + insert checkpoint |
| Rollback defined for mutable steps | Missing → BLOCK |
| Timeout defined for every node | Missing → BLOCK |

---

## Execution Strategies — استراتيجيات التنفيذ

| Strategy | الوصف | Use Case |
|---|---|---|
| **SEQUENTIAL** | تنفيذ node تلو الأخرى | معظم التعديلات |
| **PARALLEL_SAFE** | تنفيذ nodes في parallel (بدون تعارض) | تحليل متعدد الملفات |
| **PARALLEL_WITH_LOCK** | تنفيذ parallel مع أقفال على الموارد المشتركة | تعديلات متداخلة |
| **VALIDATE_FIRST** | تنفيذ التحقق أولاً ← ثم التعديل | عمليات عالية الخطورة |

### Strategy Selection
```
إذا كان risk_level == CRITICAL → VALIDATE_FIRST
إذا كان هناك data_dependency بين أي steps → SEQUENTIAL
إذا كان جميع steps read-only → PARALLEL_SAFE
إذا كان جميع steps modify files مختلفة → PARALLEL_WITH_LOCK
وإلا → SEQUENTIAL (الافتراضي الآمن)
```

---

## Execution Flow — تدفق التنفيذ

```
Input: ExecutionGraph + GovernanceVerdict (must be ALLOW or SANDBOX)
Output: ExecutionResult

for each node in topologically_sorted(graph.nodes):
    
    // Phase 1: Pre-validation
    for precondition in node.preconditions:
        if not check_precondition(precondition):
            trigger_recovery(node, "precondition_failed", precondition)
            break execution
    
    // Phase 2: Execute
    state_machine.transition(EXECUTING)
    observer.record_node_start(node)
    
    try:
        result = execute_action(node.action, node.action_type, timeout=node.timeout_ms)
    catch TimeoutError:
        trigger_recovery(node, "timeout", null)
        break execution
    catch ExecutionError as e:
        trigger_recovery(node, "execution_error", e)
        break execution
    
    observer.record_node_complete(node, result)
    
    // Phase 3: Post-validation
    for postcondition in node.postconditions:
        if not check_postcondition(postcondition):
            if node.retry_count > 0:
                retry(node)
            else:
                trigger_recovery(node, "postcondition_failed", postcondition)
                break execution
    
    // Phase 4: Checkpoint
    if node.checkpoint:
        memory.save_checkpoint(graph, executed_nodes)
        observer.record_checkpoint(node)
    
    // Phase 5: Record
    memory.record_step(node, result, duration)

// All nodes completed successfully
state_machine.transition(VERIFYING)
state_machine.transition(COMPLETED)
return ExecutionResult(success=true, summary)
```

---

## Node Execution Timeout Handling

| Timeout Type | Default | Action |
|---|---|---|
| I/O operation | 10s | Retry 1x → then fail |
| Compilation | 30s | Fail immediately |
| Test run | 60s | Fail immediately |
| Network call | 5s | Retry 2x → then fail |
| Analysis | 15s | Retry 1x → then fail |
| User confirmation | ∞ | Wait indefinitely (asynchronous) |

---

## Execution Result — نتيجة التنفيذ

```yaml
ExecutionResult:
  success: boolean
  execution_id: string
  graph_id: string
  state: Enum                  # COMPLETED | FAILED
  summary: string              # ملخص التنفيذ
  nodes: [
    {
      node_id: string,
      status: Enum              # PENDING | RUNNING | SUCCESS | FAILED | ROLLED_BACK | SKIPPED
      duration_ms: number,
      result: object|null,
      error: object|null
    }
  ]
  checkpoints_passed: number
  checkpoints_total: number
  recovery_triggered: boolean
  rollback_executed: boolean
  memory_id: string            # Reference in Memory Recording Engine
  timestamp: datetime
```

---

*The Execution Engine is the bridge between reasoning and action. It must be deterministic, safe, and fully observable.*

*محرك التنفيذ هو الجسر بين التفكير والفعل. يجب أن يكون حتميًا وآمنًا وقابلًا للمراقبة الكاملة.*
