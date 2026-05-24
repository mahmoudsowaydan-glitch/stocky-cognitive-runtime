# Stocky Engineering OS — Cross-Agent Coordination v0.1

---

> هذا الملف يحدد **التنسيق بين الـ Agents** — كيف يعمل الـ Agents معًا بدون تواصل مباشر، كيف يتم اكتشاف التعارضات وحلها، وكيف يتم تنسيق المخرجات المتعددة.
>
> This file defines **Cross-Agent Coordination** — how Agents work together without direct communication, how conflicts are detected and resolved, and how multiple outputs are coordinated.

---

## Core Principle — المبدأ الأساسي

```
❌ No agent-to-agent direct communication
✅ All coordination is mediated by the Central Orchestrator
✅ Agents read each other's outputs from Shared Memory
✅ P4 resolves conflicts
```

---

## Coordination Patterns — أنماط التنسيق

### Pattern 1: Sequential Pipeline
```
Agent A → output → Shared Memory → Agent B reads → builds on it

مثال:
  Debug Agent: يحلل root cause ← يكتب output
  Architect Agent: يقرأ الـ output ← يقترح refactor بناءً على التحليل
```

### Pattern 2: Parallel Independent
```
Agent A and Agent B work in parallel on different aspects of same incident

مثال:
  Security Agent: يحلل threat level
  Runtime Agent: يحلل lifecycle impact
  → كل واحد يكتب output مستقل ← P4 يقرر
```

### Pattern 3: Review Pattern
```
Agent A → proposal → Shared Memory → Agent B reviews → feedback → Shared Memory

مثال:
  Architect Agent: اقتراح refactor
  System Integrity Agent: يراجع الاقتراح للتعارضات
  → يكتب review في Shared Memory
  → Architect Agent يقرأ الـ review ويعدّل اقتراحه
```

### Pattern 4: Aggregation Pattern
```
Multiple agents → outputs → Orchestrator يجمع → P4 يقرر

مثال:
  Debug, Security, Runtime Agents: يتنبّهون على نفس المشكلة
  Orchestrator: يجمع التحذيرات
  P4: يقرر الإجراء المناسب (BLOCK / SANDBOX / WARN)
```

---

## Cross-Agent Contradiction Detection

### Detection Flow
```
1. Agent A writes output → Shared Memory
2. Orchestrator checks existing outputs on same topic
3. If contradictory output exists:
   a. Create CrossAgentConflict record
   b. Notify System Integrity Agent
   c. System Integrity Agent analyzes both
   d. If confirmed → send both to P4
   e. P4 decides which to follow
```

### Contradiction Types
| Type | الوصف | مثال |
|---|---|---|
| **DIRECT** | Opposite recommendations | Refactor vs Keep |
| **SCOPE** | Overlapping scope with different conclusions | Same module, different analysis |
| **ASSUMPTION** | Different base assumptions | Different risk estimates |
| **PRIORITY** | Different urgency levels | Critical vs Low on same issue |
| **TIMING** | Different proposed timelines | Immediate vs Deferred |

### Contradiction Resolution Flow
```
Contradiction detected
    │
    ▼
System Integrity Agent analyzes
    │
    ├── If one is clearly wrong → INVALIDATE + notify
    ├── If both are valid but different → send to P4
    └── If both can be merged → suggest MERGE to Orchestrator
    │
    ▼
P4 decides:
  - Follow Agent A (with rationale)
  - Follow Agent B (with rationale)
  - Merge both (create new combined proposal)
  - Reject both (request new analysis)
    │
    ▼
Decision recorded in Shared Output Memory + P5 Lineage
```

---

## Multi-Agent Workflow Example

### Scenario: Architecture violation detected

```
1. Drift Detector (P4) → detects AL-01 violation
    │
    ▼
2. Orchestrator activates:
   - Architect Agent (Tier 3, on-demand)
   - Security Agent (Tier 2, automatically)
   - Runtime Agent (Tier 2, automatically)
    │
    ▼
3. Security Agent analyzes first (fast, < 2s):
   → Output: "SL-01 not violated, but AL-01 is CRITICAL"
   → Shared Memory
    │
    ▼
4. Runtime Agent analyzes state:
   → Output: "Current state EXECUTING — BLOCK recommended"
   → Shared Memory
    │
    ▼
5. Architect Agent (deep analysis, 10s):
   → Reads Security + Runtime outputs from Shared Memory
   → Proposes: "Extract HTTP client to infrastructure layer"
   → Shared Memory
    │
    ▼
6. System Integrity Agent (triggered by multiple outputs):
   → Reviews all 3 outputs for contradictions
   → Confirms: no contradiction, all aligned
   → Shared Memory
    │
    ▼
7. Orchestrator sends all outputs to P4:
   - Security: CRITICAL
   - Runtime: BLOCK recommended
   - Architect: Extract solution
   - System Integrity: No conflicts
    │
    ▼
8. P4 decides:
   - BLOCK current execution
   - Accept Architect proposal
   - Require user approval
    │
    ▼
9. Decision recorded in Shared Memory → P5 Lineage updated
```

---

## Coordination Data Structure

### CrossAgentWorkflow
```yaml
CrossAgentWorkflow:
  id: string
  trigger_event_id: string
  status: Enum                  # ACTIVE | COMPLETED | FAILED
  
  agents_involved: [{
    agent_id: string,
    state: Enum,
    started_at: datetime,
    completed_at: datetime|null,
    output_id: string|null
  }]
  
  contradictions: [{
    id: string,
    agents: [string],
    type: Enum,
    resolved: boolean,
    resolution: string|null
  }]
  
  final_output: {               # After P4 decision
    decision: string,
    rationale: string,
    timestamp: datetime
  }
  
  memory_id: string
  lineage_id: string|null
```

---

## Agent Coordination Rules

| Rule | Enforcement |
|---|---|
| No direct agent-to-agent communication | Orchestrator blocks all direct messages |
| All outputs go to Shared Memory first | Mandatory write step |
| P4 is final decision authority | Cannot be overridden by any agent |
| System Integrity Agent monitors all contradictions | Activated on multi-agent workflows |
| Agent cannot modify another agent's output | P3 append-only enforcement |
| Agent A reading Agent B's output is indirect communication | Allowed — through Shared Memory |
| Workflow has a single owner (Orchestrator) | No agent can create workflows |

---

## Coordination Performance

| Metric | Target |
|---|---|
| Time to detect contradiction | < 1s after second output |
| Time to resolve (via P4) | < 2s |
| Workflow completion (3 agents) | < 30s |
| Maximum agents in parallel | 5 |
| Coordination overhead | < 5% of agent work time |

---

*Cross-Agent Coordination ensures that the 9 specialized minds work as a single coherent intelligence — not as competing entities. The Orchestrator, Shared Memory, and P4 authority guarantee harmony.*

*التنسيق بين الـ Agents يضمن أن العقول المتخصصة التسعة تعمل كذكاء واحد متماسك — وليس ككيانات متنافسة. المنسق والذاكرة المشتركة وسلطة P4 يضمنون الانسجام.*
