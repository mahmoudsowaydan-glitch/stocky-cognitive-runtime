# Stocky Engineering OS — Agent Memory Model v0.1

---

> هذا الملف يحدد **نموذج ذاكرة الـ Agents** — كيف يتم فصل الذاكرة الخاصة عن المشتركة، وكيف تتفاعل الـ Agents مع P3 Memory و P5 Lineage.
>
> This file defines the **Agent Memory Model** — how private memory is separated from shared memory, and how Agents interact with P3 Memory and P5 Lineage.

---

## Core Principle — المبدأ الأساسي

```
لو Shared Memory بالكامل:
  → agents will contaminate each other's reasoning
لو Isolated بالكامل:
  → no coordination, no shared learning

الحل: Three-Tier Memory
```

---

## Three-Tier Memory Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       AGENT MEMORY MODEL                                 │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  TIER 1: PRIVATE WORKING MEMORY (Isolated per Agent)            │    │
│  │                                                                  │    │
│  │  Agent A                    Agent B                    Agent C  │    │
│  │  ┌──────────────────┐      ┌──────────────────┐      ┌────────┐ │    │
│  │  │ current_context   │      │ current_context   │      │ ...    │ │    │
│  │  │ reasoning_chain   │      │ reasoning_chain   │      │        │ │    │
│  │  │ intermediate_data │      │ intermediate_data │      │        │ │    │
│  │  │ draft_proposal    │      │ draft_proposal    │      │        │ │    │
│  │  │ session_state     │      │ session_state     │      │        │ │    │
│  │  └──────────────────┘      └──────────────────┘      └────────┘ │    │
│  │  لا يطلع بره الـ Agent أبدًا                                    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                    │                                       │
│                                    ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  TIER 2: SHARED OUTPUT MEMORY (P3 Append-Only)                  │    │
│  │                                                                  │    │
│  │  كل Agent يكتب outputsه هنا بعد validation                       │    │
│  │  جميع الـ Agents يقرؤون من هنا                                   │    │
│  │  P3 Memory مع type = AGENT_OUTPUT                                │    │
│  │  Append-only — لا تعديل ولا حذف                                 │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                    │                                       │
│                                    ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  TIER 3: GLOBAL LINEAGE (P5 Read-Only)                          │    │
│  │                                                                  │    │
│  │  Decision Graph الكامل للنظام                                    │    │
│  │  جميع الـ Agents يقرؤون (لا يكتبون)                               │    │
│  │  لمعرفة:                                                         │    │
│  │    - تاريخ القرارات السابقة                                      │    │
│  │    - علاقات الـ parent-child بين الـ incidents                  │    │
│  │    - هوية النظام والتناقضات                                      │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Tier 1: Private Working Memory

### Structure
```yaml
PrivateWorkingMemory:
  agent_id: string
  session_id: string
  
  current_context: {
    active_incident_id: string|null,
    files_in_scope: [string],
    risk_level: Enum,
    budget_remaining: number
  }
  
  reasoning_chain: [             # سلسلة الاستدلال الداخلي للـ Agent
    {
      step: number,
      observation: string,
      inference: string,
      confidence: float
    }
  ]
  
  intermediate_data: object      # بيانات مؤقتة (أي شيء يحتاجه الـ Agent)
  
  draft_proposal: {              # الاقتراح قبل الإرسال
    type: string,
    content: object,
    confidence: float,
    alternatives: [object]
  }
  
  state: Enum                    # FRESH | IN_USE | STALE | COMPLETED
```

### Rules
```
1. Private Memory لا يطلع خارج الـ Agent أبدًا
2. Private Memory يُمسح عند اكتمال المهمة (COMPLETED)
3. Private Memory ليس له persistence — يعيش فقط خلال الجلسة
4. Orchestrator لا يقرأ Private Memory
5. Private Memory مشفر — لا يمكن لأي Agent آخر الوصول إليه
```

---

## Tier 2: Shared Output Memory

### Structure (extends P3 MemoryEntry)
```yaml
SharedOutputMemory:
  type: "AGENT_OUTPUT"
  agent_id: string              # Source agent
  execution_id: string          # Related execution (if any)
  incident_id: string|null      # Related incident (if any)
  
  proposal: {                   # الاقتراح النهائي
    summary: string,
    details: object,
    confidence: float,
    alternatives: [object],
    risk_estimate: float
  }
  
  validation: {                 # نتائج تحقق Orchestrator
    p2_validated: boolean,
    p4_validated: boolean,
    p5_notified: boolean,
    verdict: Enum               # ALLOW | BLOCK | MODIFIED
    p4_decision: string|null    # If P4 made a decision
  }
  
  conflict: {                   # إذا تم اكتشاف تعارض
    conflicted_with: string|null, # Agent ID
    resolved_by: string|null,     # P4 | Orchestrator
    resolution: string|null
  } | null
  
  lineage_id: string|null       # Link to P5 Decision Lineage (if applicable)
```

### Visibility Rules
```
1. أي Agent يستطيع قراءة أي SharedOutputMemory
2. أي Agent لا يستطيع تعديل أو حذف SharedOutputMemory
3. Orchestrator هو الوحيد القادر على كتابة validation fields
4. P3 Memory يحافظ على append-only
```

---

## Tier 3: Global Lineage (P5)

### What Agents Read from P5
| Data | Why Agents Need It |
|---|---|
| DecisionNode (parent/child) | لمعرفة تاريخ القرارات السابقة |
| ContradictionRecords | لتجنب إعادة نفس التناقض |
| IdentityScore (DCS/CAS/DCI) | لفهم الوضع الحالي للنظام |
| EvolutionChain | لتتبع كيف تطور التفكير في موضوع معين |

### Access Rules
```
1. Agents = READ-ONLY على P5 Lineage
2. Agents لا يكتبون في P5 مباشرة
3. Agent outputs قد تؤدي إلى تحديث P5 Lineage عبر Orchestrator
   (إذا تم قبول الـ proposal → ينشئ DecisionNode جديد)
```

---

## Memory Flow Diagram

```
Agent A starts task
    │
    ▼
Loads context from P3 Memory + P5 Lineage (read)
    │
    ▼
Works in Private Working Memory (isolated)
    │
    ▼
Completes proposal → sends to Orchestrator
    │
    ▼
Orchestrator validates:
  - P2 Laws check
  - P4 Constraint check
  - P5 Identity check
    │
    ▼
If ALLOW:
  → Written to Shared Output Memory (P3 append-only)
  → If decision → P5 Lineage updated (new DecisionNode)
  → Other agents can read

If BLOCK:
  → Written to Shared Output Memory with BLOCK status
  → Source agent notified
  → No lineage update
```

---

## Memory Quotas

| Memory Type | Max Size (per agent) | Retention |
|---|---|---|
| Private Working Memory | 1 MB | Session only |
| Shared Output Memory | Unlimited | Per P3 Memory policy |
| Global Lineage Reads | No limit | Read-only |

---

*The Agent Memory Model ensures that agents can think privately, share outcomes safely, and learn from global history — without contaminating each other's reasoning.*

*نموذج ذاكرة الـ Agents يضمن أن الـ Agents يستطيعون التفكير بخصوصية، مشاركة النتائج بأمان، والتعلم من التاريخ العالمي — دون تلويث استدلال بعضهم البعض.*
