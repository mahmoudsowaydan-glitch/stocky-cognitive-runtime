# Stocky Engineering OS — Decision Lineage Tracker v0.1

---

> هذا الملف يحدد **متتبع سلالة القرارات** — طبقة extension فوق P3 Memory تسجل العلاقات بين القرارات: من أين جاء كل قرار، لماذا اتخذ، ومتى تم إبطاله.
>
> This file defines the **Decision Lineage Tracker** — an extension layer above P3 Memory that records relationships between decisions: where each decision came from, why it was made, and when it was invalidated.

---

## Core Principle — المبدأ الأساسي

```
كل قرار له أصل.
Every decision has an origin.

P3 Memory يخزن "ماذا حدث".
P5 Lineage يخزن "لماذا حدث" و "ما الذي أدى إليه".
```

---

## Lineage Tree Structure — هيكل شجرة السلالة

```yaml
DecisionNode:
  id: string                    # Unique node ID
  incident_id: string           # Reference to the EngineeringIncident
  memory_id: string             # Reference to P3 MemoryEntry
  
  parent_ids: [string]          # IDs of decisions/premises that led to this
                                # (0 or more — root decisions have none)
  
  children_ids: [string]        # IDs of decisions that derived from this
                                # (0 or more — leaf decisions)
  
  decision_type: Enum           # REASONING_OUTPUT | GOVERNANCE_VERDICT |
                                # EXECUTION_PLAN | CONTROL_ACTION |
                                # BUDGET_ALLOCATION | DRIFT_INTERVENTION |
                                # RECOVERY_ACTION | IDENTITY_REPORT
  
  rationale: string             # Why this decision was made
  
  alternatives_considered: [string]  # Other options that were evaluated
  
  state: Enum                   # ACTIVE | SUPERSEDED | INVALIDATED | REVERTED
  
  invalidation: null | {        # If state = INVALIDATED or SUPERSEDED
    reason: string,
    replaced_by: string,        # ID of the replacing decision
    detected_by: Enum           # COHERENCE_ENGINE | GOVERNANCE | USER
  }
  
  timestamp: datetime           # When the decision was made
  context_snapshot: string      # Brief summary of context at decision time
  
  lineage_hash: string          # SHA-256 of (parent_ids + rationale + decision_type)
                                # Ensures lineage integrity
```

## Tree Types — أنواع الأشجار

### Single Lineage Chain
```
[A] → [B] → [C] → [D]
قرارات متسلسلة — كل قرار يبني على سابقه
```

### Branching Tree
```
        ┌── [B] ──┐
[A] ────┤         ├── [D] ── [E]
        └── [C] ──┘
قرار A يؤدي إلى فرعين B و C → يتجمّعان في D
```

### Replacement Chain
```
[A] ── [B] (invalidated) ── [C] (replaces B)
قرار B أبطل ← C حل محله
```

### Root Decision
```
[A] (no parent)
قرار أساسي — ليس له سابقة (مثلاً: أول قرار في النظام)
```

---

## Lineage Construction — بناء السلالة

### Algorithm
```
عند كل EngineeringIncident يتم إنشاؤه (P2 Layer 5):

1. جمع parent_ids:
   - ابحث في Memory عن incidents سابقة مرتبطة بنفس execution context
   - ابحث عن نفس type + نفس affected files (إذا وجد)
   - ابحث عن أي incident لم يُحل بعد (open)
   - ابحث عن Governance_verdict سابق على نفس القانون

2. إنشاء DecisionNode مع:
   - incident_id = current incident
   - parent_ids = found parents
   - rationale = from reasoning_output
   - decision_type = حسب type
   - state = ACTIVE

3. تحديث parent nodes:
   - لكل parent في parent_ids:
     - أضف current id إلى children_ids
     - إذا state = ACTIVE و الجديد يحل محل القديم:
       state = SUPERSEDED

4. ربط MemoryEntry بالـ Lineage Node:
   - أضف lineage_id إلى MemoryEntry.metadata
```

### Parent Discovery Rules
```
1. إذا كان الـ Incident من نفس type خلال آخر 10 دقائق → parent
2. إذا كان الـ Incident يمس نفس الـ file(s) خلال آخر ساعة → parent
3. إذا كان الـ Incident هو GOVERNANCE_VERDICT على نفس الـ LAW → parent
4. إذا كان الـ Incident هو RECOVERY لنفس الـ execution_id → parent
5. إذا كان الـ Incident هو CONTROL_ACTION على نفس النطاق → parent
6. إذا لم يوجد parent → root decision
```

---

## Invalidation Tracking — تتبع الإبطال

### When Invalidation Occurs
```
1. قرار جديد يتعارض مع قرار سابق → السابق INVALIDATED
2. Governance تلغي قرارًا → INVALIDATED
3. User explicitly reverts → INVALIDATED
4. Context expired (time-based) → INVALIDATED
5. الـ Coherence Engine يكتشف تناقضًا → INVALIDATED
```

### Invalidation Record
```yaml
InvalidationRecord:
  invalidated_node_id: string
  invalidated_at: datetime
  invalidated_by: Enum          # NEW_DECISION | GOVERNANCE | USER | COHERENCE | EXPIRY
  reason: string
  replacing_node_id: string|null
  detected_by: Enum             # LINEAGE_TRACKER | COHERENCE_ENGINE | GOVERNANCE
  evidence: string              # Why this invalidation is correct
```

---

## Lineage Queries — استعلامات السلالة

| Query | Example | Returns |
|---|---|---|
| **Ancestors** | `get_ancestors("node-D")` | All parent chain up to root |
| **Descendants** | `get_descendants("node-A")` | All children + grandchildren |
| **Active lineage** | `get_active_lineage("exec-123")` | Only active (not invalidated) nodes |
| **Decision history** | `get_history("file-A")` | All decisions affecting file-A over time |
| **Contradictions** | `get_contradictions("node-B")` | Any nodes that contradict B |
| **Root decisions** | `get_root_decisions(time_range)` | All decisions with no parent |

---

## Lineage Data Extension to P3 Memory

### New Fields in P3 MemoryEntry
```yaml
MemoryEntry (extended for P5):
  ... (existing P3 fields)
  lineage: {
    node_id: string,              # Reference to DecisionNode
    parent_ids: [string],         # Quick reference (cached)
    decision_state: Enum,         # ACTIVE | SUPERSEDED | INVALIDATED | REVERTED
    lineage_hash: string
  }
```

### New Index in P3
```
Lineage Index:
  by_node_id: DecisionNode
  by_incident_id: DecisionNode
  by_decision_type: [DecisionNode]
  by_state (ACTIVE): [DecisionNode]
  by_file: [DecisionNode]       # Resolved from incident snapshot
```

---

## Integrity Guarantees

| Guarantee | Enforcement |
|---|---|
| Lineage is append-only | New nodes added, existing nodes never deleted |
| Parent references are immutable | Once set, parent_ids لا تتغير |
| Invalidation is reversible | Can REINSTATE إذا الخطأ في الـ invalidation |
| Lineage hash chain | كل node يحتوي hash من parents |
| No orphan nodes | كل node إما له parent أو root مسمى |

---

*The Decision Lineage Tracker gives Stocky Engineering OS a complete genetic map of every decision — where it came from, why it was made, and what it led to.*

*متتبع سلالة القرارات يعطي النظام خريطة جينية كاملة لكل قرار — من أين جاء، لماذا اتخذ، وإلى ماذا أدى.*
