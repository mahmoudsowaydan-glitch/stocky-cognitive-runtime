# Stocky Engineering OS — Cognitive Memory Coherence Engine v0.1

---

> هذا الملف يحدد **محرك تماسك الذاكرة الإدراكية** — المسؤول عن بناء Decision Graph شامل، كشف التناقضات بين القرارات، وتتبع تطور التفكير عبر الزمن.
>
> This file defines the **Cognitive Memory Coherence Engine** — responsible for building a comprehensive Decision Graph, detecting contradictions between decisions, and tracking the evolution of reasoning across time.

---

## Core Principle — المبدأ الأساسي

```
الذاكرة ليست مجرد تخزين — بل هي شبكة علاقات.
Memory is not just storage — it is a network of relationships.

P5 يكتشف: هل القرار الجديد يتفق مع القرار القديم أم يعارضه؟
P5 detects: Does the new decision agree with or contradict the old one?
```

---

## Decision Graph — رسم بياني للقرارات

### Graph Structure
```yaml
DecisionGraph:
  nodes: [DecisionNode]           # From Lineage Tracker
  edges: [
    {
      from: string,               # Source node ID
      to: string,                 # Target node ID
      relationship: Enum          # LEADS_TO | DERIVES_FROM | REPLACES |
                                  # CONTRADICTS | SUPPORTS | EXTENDS
      weight: float               # 0.0 - 1.0 (strength of relationship)
      detected_by: string         # How this relationship was discovered
    }
  ]
  metadata: {
    node_count: number,
    edge_count: number,
    last_updated: datetime,
    coherence_score: float        # Overall graph coherence
  }
```

### Relationship Types
| Relationship | المعنى | مثال |
|---|---|---|
| **LEADS_TO** | قرار يؤدي مباشرةً إلى آخر | Reasoning → Execution Plan |
| **DERIVES_FROM** | قرار مشتق من آخر | Budget Allocation ← Governance Verdict |
| **REPLACES** | قرار يحل محل آخر | New rule replaces old interpretation |
| **CONTRADICTS** | قراران في تعارض | Same incident, different root cause |
| **SUPPORTS** | قرار يدعم آخر | QA verdict supports Architecture decision |
| **EXTENDS** | قرار يوسّع قرارًا سابقًا | Adding new files to existing refactor plan |

---

## Contradiction Detection — كشف التناقضات

### Types of Contradictions

| Type | الوصف | مثال |
|---|---|---|
| **Direct** | Decision A says X, Decision B says ¬X | "Allow import" vs "Block import" |
| **Temporal** | Past decision + new context gives different result | Same input, different output |
| **Scope** | Two decisions that overlap and conflict | Refactor Module A from 2 different agents |
| **Law Conflict** | Decision violates a Law that was upheld before | Same Law, different enforcement |
| **Rationale Shift** | Same action, different rationale | Why did we change our reasoning? |

### Detection Algorithms

#### Algorithm 1: Direct Contradiction
```
1. Compare new DecisionNode against all ACTIVE nodes in same scope
2. Look for opposite outcomes:
   - ALLOW vs BLOCK on same action
   - HIGH severity vs LOW على same incident type
   - MODIFY vs KEEP على same file
3. If opposite found → CONTRADICTS edge + alert
```

#### Algorithm 2: Temporal Inconsistency
```
1. Find decisions with same input pattern + context
2. Compare outputs over time
3. If same input → different output without context change:
   → Temporal Contradiction warning
4. If context changed → document shift (identity evolution, not contradiction)
```

#### Algorithm 3: Law Enforcement Inconsistency
```
1. Scan all GOVERNANCE_VERDICT nodes for a specific Law (e.g., AL-01)
2. Compare verdicts across similar violations
3. If same violation → different verdicts:
   → Law Enforcement Contradiction
4. Check if context justifies the difference
```

### Contradiction Record
```yaml
ContradictionRecord:
  id: string
  type: Enum                    # DIRECT | TEMPORAL | SCOPE | LAW_CONFLICT | RATIONALE_SHIFT
  node_a_id: string             # First decision
  node_b_id: string             # Second decision (contradicting)
  description: string           # What is the contradiction
  severity: Enum                # LOW | MEDIUM | HIGH | CRITICAL
  resolution: null | {
    resolved: boolean,
    resolution_type: Enum,      # INVALIDATE_OLD | MERGE | CONTEXT_DIFF | AMBIGUITY
    resolved_by: string,        # GOVERNANCE | USER | AUTOMATIC
    resolved_at: datetime
  }
  detected_at: datetime
  memory_id: string             # Reference in P3 Memory
```

---

## Evolution Mapping — رسم تطور التفكير

### Purpose
تتبع كيف تطور تفكير النظام حول موضوع معين عبر الزمن.

### Evolution Chain Structure
```yaml
EvolutionChain:
  topic: string                 # What is evolving (e.g., "auth module architecture")
  nodes: [DecisionNode]         # Ordered by timestamp
  milestones: [
    {
      node_id: string,
      change: string,           # What changed at this point
      reason: string,           # Why it changed
      timestamp: datetime
    }
  ]
  current_state: string         # Latest understanding
  trend: Enum                   # STABLE | EVOLVING | OSCILLATING | STALLED
```

### Trend Detection
```
Trend = f(decision_frequency, direction_changes, invalidation_rate)

إذا كان هناك:
  - قرارات جديدة متكررة على نفس الموضوع → EVOLVING
  - قرارات تلغي بعضها البعض → OSCILLATING (تحذير)
  - نفس القرار يبقى في ACTIVE لمدة طويلة → STABLE
  - لا قرارات جديدة → STALLED
```

---

## Pattern Identification — التعرف على الأنماط

### Identified Patterns
| Pattern | الوصف | Action |
|---|---|---|
| **Oscillation** | نفس القرار يتغير ذهابًا وإيابًا | إبلاغ Stability Monitor |
| **Contradiction cluster** | 3+ تناقضات على نفس الموضوع | إبلاغ Governance Layer |
| **Rationale decay** | الـ rationale يقل تفصيلاً مع الوقت | WARNING |
| **Scope creep** | القرارات تتوسع في النطاق باستمرار | إبلاغ Drift Suppression |
| **Decision echo** | نفس القرار يُعاد اكتشافه (بدون علم بالسابق) | إبلاغ Lineage Tracker |
| **Identity shift** | تغير في مبادئ القرار الأساسية | Identity Alert |

---

## Coherence Report — تقرير التماسك

### Periodic Report Structure
```yaml
CoherenceReport:
  timestamp: datetime
  graph_metrics: {
    node_count: number,
    edge_count: number,
    active_nodes: number,
    invalidated_nodes: number,
    coherence_score: float      # Based on contradiction ratio
  }
  contradictions: {
    open: [ContradictionRecord],      # Unresolved
    resolved_last_24h: number,
    critical_open: number             # HIGH/CRITICAL unresolved
  }
  evolution_chains: [EvolutionChain]
  patterns_detected: [{
    pattern: string,
    affected_nodes: [string],
    severity: Enum
  }]
  recommendation: string
```

---

*The Cognitive Memory Coherence Engine ensures that Stocky Engineering OS maintains intellectual consistency — not just data consistency — across its entire lifetime.*

*محرك تماسك الذاكرة الإدراكية يضمن أن النظام يحافظ على الاتساق الفكري — وليس فقط اتساق البيانات — عبر عمره بالكامل.*
