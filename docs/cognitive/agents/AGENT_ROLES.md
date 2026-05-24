# Stocky Engineering OS — Agent Roles v0.1

---

> هذا الملف يحدد **الأدوار التسعة الرسمية** لـ P5-A Agents — كل Agent:Domain, Authority, Triggers, وحدود عمله.
>
> This file defines the **nine official roles** of P5-A Agents — each Agent: Domain, Authority, Triggers, and boundaries.

---

## Agent Role Catalog — كتالوج أدوار الـ Agents

---

### Agent 1: Architect Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | On-demand (Tier 3) |
| **Domain** | Structure, layers, dependencies, boundaries |
| **Authority** | Propose, Review |
| **Trigger** | User request, Major architectural event, Governance request |
| **Private Memory Retention** | Session only |
| **P5 Lineage Access** | Full (needs history of architectural decisions) |

**Responsibilities:**
- Analyze architecture violations (P2 AL-01 to AL-05)
- Propose refactoring plans
- Review dependency graphs
- Ensure layer boundary compliance
- Suggest contract definitions

**Input Context:** Dependency graph, current layer structure, affected files, P5 lineage for similar past decisions.

**Output Proposal Format:**
```yaml
ArchitectProposal:
  type: REFACTOR | RESTRUCTURE | CONTRACT_CHANGE | NEW_MODULE
  scope: [string]               # Affected modules
  changes: [{
    action: string,
    target: string,
    rationale: string,
    law_compliance: [string]    # Which laws are satisfied
  }]
  risk_estimate: float
  effort_estimate: string       # LOW | MEDIUM | HIGH
  alternatives: [object]
```

---

### Agent 2: Runtime Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | Event-triggered (Tier 2) |
| **Domain** | Lifecycle, state machine, execution, memory |
| **Authority** | Monitor, Alert |
| **Trigger** | State inconsistency, Lifecycle leak, Execution anomaly |
| **Private Memory Retention** | Session only |

**Responsibilities:**
- Monitor Runtime State Machine transitions
- Detect lifecycle leaks (unmanaged resources)
- Alert on execution anomalies
- Analyze execution timing patterns
- Validate state transition correctness

**Input Context:** Current Runtime State, recent TraceEvents, active ExecutionGraph, P3 Memory records.

**Output Alert Format:**
```yaml
RuntimeAlert:
  severity: Enum                # WARNING | CRITICAL
  anomaly_type: Enum            # STATE_INCONSISTENCY | LIFECYCLE_LEAK | TIMING_ANOMALY
  affected_component: string
  description: string
  recommendation: string
```

---

### Agent 3: Security Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | Event-triggered (Tier 2) |
| **Domain** | Safety laws (SL-01 to SL-05), threats, permissions |
| **Authority** | Alert, Block-suggest (to P4) |
| **Trigger** | Security Law violation, Unsafe execution intent, Permission check |
| **Private Memory Retention** | Session only |

**Responsibilities:**
- Monitor violations of SL-01 to SL-05
- Alert on unsafe execution patterns
- Validate permission requests
- Suggest sandboxing when needed
- Check compliance with fail-closed principle

**Input Context:** Current governance verdicts, incident types, execution plan, P4 drift records.

**Output Alert Format:**
```yaml
SecurityAlert:
  law_violated: string          # SL-01 to SL-05
  severity: Enum                # MEDIUM | HIGH | CRITICAL
  threat_description: string
  recommended_action: Enum      # BLOCK | SANDBOX | REQUIRE_APPROVAL
```

---

### Agent 4: Debug Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | Event-triggered (Tier 2) |
| **Domain** | Failure analysis, root cause, error patterns |
| **Authority** | Analyze, Propose |
| **Trigger** | EXECUTION_ERROR, POSTCONDITION_FAILED, RECOVERY_FAILED, Any failure |
| **Private Memory Retention** | Extended (kept for 1h for pattern analysis) |

**Responsibilities:**
- Analyze execution failures
- Determine root cause (symptom vs cause)
- Propose fix alternatives
- Identify recurring failure patterns
- Suggest improvements to P4 recovery strategies

**Input Context:** Full incident details, execution trace, error logs, P3 Memory failure records, P5 lineage for related past failures.

**Output Proposal Format:**
```yaml
DebugProposal:
  incident_id: string
  root_cause: string
  symptom: string
  failure_type: Enum
  fix_alternatives: [{
    description: string,
    risk: float,
    effort: string,
    estimated_success: float
  }]
  recurrence_pattern: string|null
```

---

### Agent 5: Optimization Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | Event-triggered (Tier 2) |
| **Domain** | Performance, memory, budget, execution time |
| **Authority** | Analyze, Recommend |
| **Trigger** | Memory > 70%, CPU > 80%, Execution timeout, Budget saturation |
| **Private Memory Retention** | Session only |

**Responsibilities:**
- Analyze resource usage patterns
- Propose performance optimizations
- Suggest budget allocation adjustments
- Detect memory leaks or pressure
- Recommend execution timing improvements

**Input Context:** P4 Budget System state, P3 Live Observer metrics, Execution timing records, Memory trends.

**Output Recommendation Format:**
```yaml
OptimizationRecommendation:
  target_area: Enum             # MEMORY | CPU | BUDGET | TIMING | RESOURCE
  current_value: float
  threshold: float
  recommendation: string
  estimated_improvement: float
  risk_of_change: float
```

---

### Agent 6: QA Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | On-demand (Tier 3) |
| **Domain** | Testing, validation, contracts, execution verification |
| **Authority** | Verify, Report |
| **Trigger** | Pre-release, Major refactor, User request, Periodic validation |
| **Private Memory Retention** | Extended (until report is delivered) |

**Responsibilities:**
- Validate execution plans before release
- Verify contract compliance (P2 AL-04)
- Run simulation tests on proposed changes
- Report quality metrics
- Suggest test coverage improvements

**Input Context:** ExecutionPlans, P2 Contracts, P3 Memory of past executions, P5 Identity metrics.

**Output Report Format:**
```yaml
QAReport:
  scope: string
  validation_results: [{
    check: string,
    passed: boolean,
    details: string
  }]
  quality_score: float
  risks_found: [string]
  recommendation: Enum          # APPROVED | CONDITIONAL | REJECTED
```

---

### Agent 7: Research Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | On-demand (Tier 3) |
| **Domain** | External knowledge, patterns, best practices |
| **Authority** | Inform, Suggest |
| **Trigger** | User request, New technology, Unknown pattern |
| **Private Memory Retention** | Extended (24h for caching) |

**Responsibilities:**
- Research external patterns and solutions
- Suggest best practices for current context
- Analyze new libraries or technologies
- Provide alternative approaches from industry
- Document research findings in P3 Memory

**Input Context:** User query, current architecture context, affected files, relevant P5 lineage.

**Output Format:**
```yaml
ResearchFinding:
  query: string
  sources: [string]
  findings: [{
    pattern: string,
    applicability: float,
    effort: string,
    risk: string
  }]
  recommendation: string|null
```

---

### Agent 8: Coherence Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | On-demand (Tier 3) |
| **Domain** | P5 Identity interface, identity translation |
| **Authority** | Translate, Monitor |
| **Trigger** | Identity check, Periodic review (24h), User request |
| **Private Memory Retention** | Session only |

**Responsibilities:**
- Read P5 Identity metrics and translate for agents
- Monitor identity impact of agent proposals
- Alert if proposal would cause identity contradiction
- Provide identity context to other agents
- Relay P5 coherence reports to Orchestrator

**Input Context:** P5 IdentityStabilizer reports, P5 Lineage graph, P5 ContradictionRecords.

**Output Format:**
```yaml
CoherenceContext:
  identity_score: float
  identity_trend: string
  contradictions_open: number
  relevant_lineage: [string]    # IDs of relevant decision nodes
  caution: string|null          # If proposal risks identity drift
```

---

### Agent 9: System Integrity Agent

| الخاصية | القيمة |
|---|---|
| **Tier** | Event-triggered (Tier 2) |
| **Domain** | Cross-agent consistency, contradiction detection |
| **Authority** | Validate, Alert |
| **Trigger** | Multiple agent proposals on same topic, Cross-agent contradiction |
| **Private Memory Retention** | Extended (1h for pattern analysis) |

**Responsibilities:**
- Detect contradictions between agent proposals
- Validate cross-agent consistency
- Alert Orchestrator on conflicting recommendations
- Suggest resolution paths
- Track agent reliability patterns

**Input Context:** All agent outputs in Shared Output Memory, P5 ContradictionRecords, active incidents.

**Output Alert Format:**
```yaml
SystemIntegrityAlert:
  conflicting_agents: [string]
  conflict_type: Enum           # CONTRADICTORY_PROPOSALS | OVERLAPPING_SCOPE | 
                                # INCONSISTENT_ASSUMPTIONS | CYCLE_DEPENDENCY
  description: string
  suggested_resolution: string
  severity: Enum
```

---

## Agent Role Comparison

| Agent | Tier | Authority | Trigger Type | Memory |
|---|---|---|---|---|
| Architect | 3 (On-demand) | Propose | Manual | Session |
| Runtime | 2 (Triggered) | Monitor, Alert | State anomaly | Session |
| Security | 2 (Triggered) | Alert, Block-suggest | Law violation | Session |
| Debug | 2 (Triggered) | Analyze, Propose | Execution failure | Extended (1h) |
| Optimization | 2 (Triggered) | Analyze, Recommend | Resource threshold | Session |
| QA | 3 (On-demand) | Verify, Report | Manual | Extended |
| Research | 3 (On-demand) | Inform, Suggest | Manual | Extended (24h) |
| Coherence | 3 (On-demand) | Translate, Monitor | Identity check | Session |
| System Integrity | 2 (Triggered) | Validate, Alert | Agent contradiction | Extended (1h) |

---

*These 9 agent roles form a complete cognitive specialization system. Each agent is a specialist mind, focused on its domain, operating under the governance of P4 and the coordination of the Orchestrator.*

*هذه الأدوار التسعة تشكل نظام تخصص إدراكي كامل. كل Agent هو عقل متخصص، مركز على مجاله، يعمل تحت حوكمة P4 وتنسيق الـ Orchestrator.*
