# Stocky Engineering OS — Central Cognitive Orchestrator v0.1

---

> هذا الملف يحدد **المنسق المعرفي المركزي** — القلب النابض لـ P5-A المسؤول عن توجيه الرسائل بين الـ Agents، فرض قيود P4، التحقق من صحة المخرجات وفق P2، وتسجيل كل شيء في P3 Memory.
>
> This file defines the **Central Cognitive Orchestrator** — the beating heart of P5-A responsible for routing messages between Agents, enforcing P4 constraints, validating outputs against P2 laws, and logging everything into P3 Memory.

---

## Core Principle — المبدأ الأساسي

```
All communication goes through the Orchestrator.
No agent-to-agent direct communication.

كل التواصل يمر عبر المنسق.
لا تواصل مباشر بين Agent و Agent.
```

---

## Orchestrator Architecture — بنية المنسق

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       CENTRAL COGNITIVE ORCHESTRATOR                      │
│                                                                           │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────┐   │
│  │ EVENT RECEIVER │  │ MESSAGE ROUTER │  │ CONSTRAINT VALIDATOR     │   │
│  │ يستقبل الأحداث │──│ يوجّه للـ Agent│──│ يتحقق من P4 + P2 + P5   │   │
│  └────────────────┘  └────────────────┘  └──────────┬───────────────┘   │
│                                                      │                    │
│  ┌────────────────┐  ┌────────────────┐             │                    │
│  │ OUTPUT LOGGER  │  │ CONFLICT       │◀────────────┘                    │
│  │ يسجل في P3     │  │ DETECTOR       │  يكتشف التعارضات بين المقترحات  │
│  └────────────────┘  └────────────────┘                                  │
└──────────────────────────────────────────────────────────────────────────┘
                │                        │
                ▼                        ▼
    ┌──────────────────┐    ┌────────────────────────┐
    │  Agents  │  P3    │    │  P4 (decides) │  P2    │
    └──────────────────┘    └────────────────────────┘
```

---

## Core Functions — الوظائف الأساسية

### Function 1: Event Reception & Agent Routing
```
Input: Signal from P3/P4/P5-B IDE
Process:
  1. Classify event type
  2. Determine which agent(s) should handle it
  3. Check if agent is available (not busy)
  4. Route to agent with full context snapshot

Routing Rules:
  - Compile Failure → Debug Agent + Runtime Agent
  - Architecture Violation → Architect Agent + System Integrity Agent
  - Security Violation → Security Agent (P4 notified directly)
  - Performance Degradation → Optimization Agent
  - User Query → Research Agent + Architect Agent (if architectural)
  - Identity Drift → Coherence Agent + System Integrity Agent
```

### Function 2: Constraint Validation
```
قبل إرسال أي Agent Output إلى أي مكان:
  1. Validate against P2 Laws:
     - Does output violate any active Law?
     - If YES → BLOCK + notify P4 + log
  2. Validate against P4 Constraints:
     - Is output within current Budget?
     - Is system in correct state for this output?
     - If NO → BLOCK + notify P4
  3. Validate against P5 Identity:
     - Does output cause identity contradiction?
     - If YES → WARNING + notify P5
```

### Function 3: Output Logging
```
كل Agent Output يُسجل في P3 Memory:
  Format: {
    agent_id, timestamp, proposal,
    validated_by: [P2, P4, P5],
    verdict: ALLOW | BLOCK | MODIFIED,
    decision: P4 final decision (if applicable)
  }
  Type: AGENT_OUTPUT (new entry type in P3 Memory)
```

### Function 4: Conflict Detection
```
عند استقبال multiple agent outputs عن نفس الموضوع:
  1. Compare proposals
  2. If contradictory → create CrossAgentConflict record
  3. Send both to P4 for decision
  4. Log conflict in P3 Memory
```

---

## Message Format — تنسيق الرسالة

```yaml
OrchestratorMessage:
  id: string                    # Unique message ID
  type: Enum                    # EVENT | PROPOSAL | DECISION | QUERY | ALERT
  
  source: string                # Agent ID or System Layer
  target: string                # Agent ID or Layer
  
  context: {                    # السياق المرسل مع الرسالة
    incident_id: string|null,
    execution_id: string|null,
    session_id: string|null,
    affected_files: [string],
    risk_score: float|null
  }
  
  payload: object               # محتوى الرسالة (يختلف حسب النوع)
  
  validation: {                 # نتائج التحقق
    p2_validated: boolean,
    p4_validated: boolean,
    p5_notified: boolean,
    blocked: boolean,
    block_reason: string|null
  }
  
  timestamp: datetime
  memory_id: string             # Reference in P3 Memory
```

---

## Agent Availability — توفر الـ Agent

### State Machine per Agent
```
IDLE → ACTIVATED → WORKING → OUTPUT_READY → VALIDATING → COMPLETED
                    │                       │
                    ▼                       ▼
                 WAITING                FAILED
```

### Availability Rules
| State | Can accept work? |
|---|---|
| IDLE | ✅ |
| ACTIVATED | ✅ (warming up) |
| WORKING | ❌ (busy) |
| WAITING | ❌ (waiting for external input) |
| OUTPUT_READY | ❌ (has pending output) |
| VALIDATING | ❌ (under validation) |
| COMPLETED | ✅ |
| FAILED | ❌ (needs reset) |

---

## Orchestrator Queue — طابور المنسق

```yaml
OrchestratorQueue:
  capacity: 50                  # Max pending messages
  items: [
    {
      message_id: string,
      priority: Enum            # HIGH (error/threat) | MEDIUM | LOW (background)
      status: Enum              # PENDING | ROUTED | VALIDATED | DELIVERED
      created_at: datetime,
      routed_to: string|null
    }
  ]
```

### Queue Priority Rules
```
1. HIGH priority: Security violations, Critical errors, HALT signals
2. MEDIUM priority: Architecture violations, Drift alerts, User requests
3. LOW priority: Background analysis, Research queries, Periodic checks
```

---

## Orchestrator Data Structure

```yaml
CognitiveOrchestrator:
  id: string
  
  active_agents: [{
    id: string,
    state: Enum,
    current_task: string|null,
    uptime_ms: number
  }]
  
  queue: OrchestratorQueue
  
  stats: {
    messages_routed_total: number,
    messages_blocked_total: number,
    conflicts_detected: number,
    avg_routing_latency_ms: number
  }
  
  state: Enum                   # OPERATIONAL | DEGRADED | OVERLOADED
```

---

*The Central Cognitive Orchestrator is the nervous system hub of the Controlled Agents Layer. Every thought, every proposal, every decision passes through it — ensuring order, safety, and traceability.*

*المنسق المعرفي المركزي هو مركز الجهاز العصبي لطبقة الـ Agents. كل فكرة، كل اقتراح، كل قرار يمر عبره — لضمان النظام والأمان والتتبع.*
