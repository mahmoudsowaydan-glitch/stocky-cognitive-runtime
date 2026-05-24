# Stocky Engineering OS — Reasoning Pipeline v0.1

---

> هذا الملف يحدد **كيف يفكر النظام** رسميًا. الـ 7 Layers التالية تمثل العقل الهندسي للنظام — من استقبال Event إلى تنفيذ متحكم فيه.
>
> This file defines **how the system thinks** officially. The following 7 Layers represent the engineering brain of the system — from Event intake to controlled execution.

---

## Cognitive Pipeline Overview — نظرة عامة

```
┌─────────────────────────────────────────────────────────────┐
│                     SIGNAL INTAKE (Layer 1)                   │
│  User / Runtime / Agent / Drift Detector / Telemetry         │
└────────────────────────┬────────────────────────────────────┘
                         │ EngineeringEvent (raw)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  CLASSIFICATION ENGINE (Layer 2)              │
│  Type identification · Confidence calculation                │
└────────────────────────┬────────────────────────────────────┘
                         │ Classified Event
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                CONTEXT RESOLUTION ENGINE (Layer 3)            │
│  Files · Dependencies · Runtime state · Memory lookup        │
└────────────────────────┬────────────────────────────────────┘
                         │ Enriched Incident
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              ENGINEERING REASONING ENGINE (Layer 4)           │
│  Root cause · Alternatives · Risk · Confidence               │
└────────────────────────┬────────────────────────────────────┘
                         │ Analyzed Incident
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               GOVERNANCE & SAFETY LAYER (Layer 5)             │
│  Law matching · Verdict: ALLOW/BLOCK/SANDBOX/APPROVAL         │
└────────────────────────┬────────────────────────────────────┘
                         │ Approved Incident + Verdict
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               EXECUTION PLANNING LAYER (Layer 6)              │
│  Steps · Rollback · Checkpoints · Dependency order           │
└────────────────────────┬────────────────────────────────────┘
                         │ Execution Plan
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CONTROLLED EXECUTION LAYER (Layer 7)             │
│  Execute · Validate · Rollback · Record to Memory            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🟦 Layer 1: Signal Intake Layer

### Mission
استقبال أي إشارة خام من أي مصدر — وتجهيزها كـ EngineeringEvent.

### Inputs
- Raw signal from: USER, SYSTEM_AGENT, RUNTIME_OBSERVER, DRIFT_DETECTOR, TELEMETRY, EXTERNAL_INTEGRATION

### Process
```
1. Identify source
2. Determine initial_severity based on source + type heuristic
3. Create EngineeringEvent with snapshot
4. Assign unique ID + timestamp
```

### Output
```
EngineeringEvent {
  id, source, type (if identifiable),
  initial_severity, timestamp, snapshot
}
```

### Initial Severity Heuristic
| Source | Initial Severity |
|---|---|
| USER (explicit request) | LOW — pending classification |
| USER (error report) | MEDIUM |
| RUNTIME_OBSERVER | HIGH |
| DRIFT_DETECTOR | CRITICAL |
| TELEMETRY (anomaly) | MEDIUM |
| SYSTEM_AGENT | MEDIUM |
| EXTERNAL_INTEGRATION | MEDIUM |

### Performance Budget
- **Target latency:** < 50ms
- **Must not block** — يعمل بشكل متزامن أو غير متزامن حسب الحاجة

---

## 🟩 Layer 2: Classification Engine

### Mission
تصنيف الحدث هندسيًا — تحديد نوع المشكلة ودرجة الثقة في التصنيف.

### Input
EngineeringEvent (from Layer 1)

### Process
```
1. Pattern match event against known types
2. Calculate confidence score based on:
   - Completeness of evidence
   - Clarity of signal
   - Historical accuracy of similar classifications
3. Emit classified EngineeringEvent
```

### Classification Rules
| Signal Pattern | Type |
|---|---|
| Syntax error / type mismatch | COMPILE_FAILURE |
| Memory usage spike | RUNTIME_ANOMALY / MEMORY_PRESSURE |
| Circular dependency detected | DEPENDENCY_DRIFT |
| State mutation without command | STATE_CORRUPTION |
| Async operation with no timeout | SYNC_INTEGRITY_RISK |
| Unmanaged subscription | LIFECYCLE_LEAK |
| Crossing architecture boundary | ARCHITECTURE_VIOLATION |
| Direct domain mutation from sync | CONTRACT_VIOLATION |
| Operation with no rollback | UNSAFE_EXECUTION_INTENT |
| Missing telemetry in critical path | TELEMETRY_BLIND_SPOT |

### Output
```
EngineeringEvent {
  ... (from Layer 1)
  classification: {
    category: string,
    confidence: float (0.0 - 1.0)
  }
}
```

### Performance Budget
- **Target latency:** < 100ms
- **Parallelizable** — يمكن تشغيل classification لعدة Events بالتوازي

---

## 🟨 Layer 3: Context Resolution Engine

### Mission
جمع كل السياق اللازم لتحليل الحادث — الملفات، التبعيات، حالة الـ Runtime، والذاكرة السابقة.

### Input
Classified EngineeringEvent (from Layer 2)

### Process
```
1. Identify files_involved from the event snapshot
2. Traverse dependency graph for affected modules
3. Query runtime observer for current state
4. Search Project Brain for similar past incidents
5. Load relevant ARCHITECTURE_LAWS
6. Create EngineeringIncident with enriched context
```

### Context Types Collected
| Context | المصدر | Purpose |
|---|---|---|
| Files involved | Snapshot + File graph | تحديد نطاق التغيير |
| Dependency chain | Dependency graph | تحليل الـ propagation |
| Runtime state | Runtime Observer | فهم حالة التشغيل الحالية |
| Past incidents | Project Brain (Memory Layer) | استدعاء القرارات السابقة |
| Active laws | ENGINEERING_LAWS | التحقق المعماري |
| Recent modifications | Git history + Memory | فهم السياق الزمني |

### Output
```
EngineeringIncident {
  id,
  event_ids: [event.id],
  classification: { category, confidence, severity },
  intent: { actor, objective, expected_outcome, confidence },
  propagation_scope: { local, cross_module, runtime_wide, sync_impact },
  snapshot: { ... },
  context: { files, dependencies, runtime_state, past_incidents }
}
```

### Performance Budget
- **Target latency:** 200ms - 500ms
- **Heaviest layer** — يعتمد على حجم الـ dependency graph
- **Caching:** Context results are cached for repeated queries

---

## 🟧 Layer 4: Engineering Reasoning Engine

### Mission
تحليل root cause، مقارنة البدائل، حساب المخاطر — هذه أخطر طبقة في النظام.

### Input
EngineeringIncident with enriched context (from Layer 3)

### Process
```
1. ROOT CAUSE ANALYSIS
   - Trace event back to origin
   - Distinguish symptom from root cause
   - Identify architecture weakness vs implementation error

2. IMPACT ANALYSIS
   - Determine affected modules and layers
   - Estimate propagation path
   - Identify state corruption risk

3. ALTERNATIVE GENERATION
   - Propose fix options
   - Evaluate each against ENGINEERING_LAWS
   - Rank by risk + effort + architectural alignment

4. RISK CALCULATION
   - Calculate risk_score based on:
     - Propagation scope weight
     - Affected layer criticality
     - Recovery complexity
     - Historical incident patterns
   - Calculate confidence_score based on:
     - Completeness of context
     - Clarity of root cause
     - Historical accuracy

5. DECISION RECOMMENDATION
   - Recommend best alternative
   - Provide rationale
```

### Root Cause vs Symptom — التفريق الحاسم
| Symptom (عرض) | Root Cause (سبب جذري) |
|---|---|
| Compile error in import | Architectural dependency violation |
| Runtime memory spike | Lifecycle leak — no disposal |
| State inconsistency | Missing transaction boundary |
| Async timeout | Implicit async boundary — no declared timeout |

### Risk Score Formula (v0.1)
```
risk_score = (propagation_weight * 0.3)
           + (layer_criticality * 0.3)
           + (recovery_complexity * 0.2)
           + (historical_pattern * 0.2)

حيث:
  propagation_weight: local=0.2, cross_module=0.5, runtime_wide=0.8, sync_impact=1.0
  layer_criticality: KERNEL=1.0, RUNTIME=0.8, COGNITIVE=0.6, EXECUTION=0.6, AGENT=0.4
  recovery_complexity: simple=0.2, moderate=0.5, complex=0.8, impossible=1.0
  historical_pattern: based on frequency of similar incidents
```

### Output
```
EngineeringIncident {
  ... (from Layer 3)
  reasoning_output: {
    root_cause: string,
    impact_analysis: string,
    alternatives: [string],
    risk_score: float (0.0 - 1.0),
    confidence_score: float (0.0 - 1.0)
  }
}
```

### Performance Budget
- **Target latency:** 500ms - 2s
- **Most critical layer** — قد يتطلب multiple LLM calls
- **Cannot be cached** — كل حادث فريد

---

## 🟥 Layer 5: Governance & Safety Layer

### Mission
المراجعة المعمارية النهائية قبل السماح بالتنفيذ — مقارنة التحليل بالقوانين.

### Input
Analyzed EngineeringIncident (from Layer 4)

### Process
```
1. LAW MATCHING
   - Compare incident against all ENGINEERING_LAWS
   - Identify which laws are at risk
   - Flag direct violations

2. SEVERITY VERIFICATION
   - Confirm computed_severity
   - Check if initial_severity was accurate
   - Escalate if discrepancy found

3. PROPAGATION ANALYSIS
   - Confirm propagation_scope
   - Identify downstream risk

4. VERDICT DETERMINATION
   - Use Decision Matrix (Risk × Confidence)
   - Apply law violation override rules
   - Determine final verdict
```

### Decision Matrix (Risk × Confidence)
| Risk ↓ \ Confidence → | Low (< 0.4) | Medium (0.4-0.7) | High (> 0.7) |
|---|---|---|---|
| **Low** (< 0.3) | ALLOW | ALLOW | ALLOW |
| **Medium** (0.3-0.6) | SANDBOX | SANDBOX | REQUIRE_APPROVAL |
| **High** (0.6-0.85) | BLOCK | BLOCK | REQUIRE_APPROVAL |
| **Critical** (> 0.85) | BLOCK | BLOCK | BLOCK |

### Law Violation Override Rules
- أي Violation من نوع CRITICAL → يرفع verdict إلى BLOCK (بغض النظر عن Decision Matrix)
- أي Violation من نوع MAJOR مع propagation = runtime_wide → يرفع إلى BLOCK
- Violations متعددة في نفس الـ Incident → يرفع الـ risk score +0.2 لكل violation إضافية
- إذا كان confidence_score < 0.3 و risk_score > 0.5 → REQUIRES_APPROVAL (لأن النظام غير متأكد لكن الخطر مرتفع)

### Verdict Types
| Verdict | المعنى | الإجراء |
|---|---|---|
| ALLOW | آمن للتنفيذ | تنفيذ فوري |
| BLOCK | ممنوع تمامًا | إيقاف + إشعار المستخدم + تسجيل |
| SANDBOX | تنفيذ في بيئة معزولة | تنفيذ بدون side effects على النظام الحقيقي |
| REQUIRE_APPROVAL | يحتاج موافقة المستخدم | عرض التقرير وانتظار القرار |

### Output
```
EngineeringIncident {
  ... (from Layer 4)
  governance_verdict: ALLOW | BLOCK | SANDBOX | REQUIRE_APPROVAL
}
```

### Performance Budget
- **Target latency:** < 100ms
- **Synchronous** — لا يمكن تخطي هذه الطبقة
- **Deterministic** — نفس input يعطي نفس verdict

---

## 🟪 Layer 6: Execution Planning Layer

### Mission
بناء خطة تنفيذ مفصلة مع استراتيجية تراجع عند الفشل.

### Input
Approved EngineeringIncident with verdict (from Layer 5)

### Process
```
1. DECOMPOSE
   - Divide operation into atomic steps
   - Order steps by dependency

2. VALIDATION DESIGN
   - Define validation criteria for each step
   - Identify checkpoints

3. ROLLBACK DESIGN
   - Define rollback strategy for each step
   - Ensure rollback is reversible

4. RESOURCE ALLOCATION
   - Identify required permissions
   - Allocate sandbox if verdict = SANDBOX
```

### Execution Plan Structure
```yaml
execution_plan:
  steps:
    - id: "step-001"
      action: "modify file X"
      validation: "verify file X compiles"
      rollback: "git checkout file X"
      checkpoint: true
    - id: "step-002"
      action: "update import in file Y"
      validation: "verify dependency graph"
      rollback: "revert import change"
      checkpoint: false
    - id: "step-003"
      action: "run tests for module Z"
      validation: "all tests pass"
      rollback: "N/A (validation-only step)"
      checkpoint: true
  rollback_strategy: "sequential-reverse"
  checkpoints: ["step-001", "step-003"]
```

### Rollback Strategies
| Strategy | الوصف | Use Case |
|---|---|---|
| sequential-reverse | التراجع بترتيب عكسي للخطوات | معظم التعديلات |
| atomic-snapshot | snapshot قبل التنفيذ → استعادة كاملة | تغييرات runtime |
| compensatory | تعويض التأثير بدلاً من التراجع | تغييرات state |
| no-rollback | عمليات بدون rollback (قراءة فقط) | تحليل/قراءة |

### Output
```
EngineeringIncident {
  ... (from Layer 5)
  execution_plan: { steps, rollback_strategy, checkpoints }
}
```

### Performance Budget
- **Target latency:** 100ms - 300ms
- **Deterministic** — نفس input يعطي نفس الخطة

---

## ⬛ Layer 7: Controlled Execution Layer

### Mission
تنفيذ الخطة تدريجيًا مع التحقق في كل checkpoint — مع القدرة على التراجع عند الفشل.

### Input
Execution Plan (from Layer 6)

### Process
```
for each step in execution_plan.steps:
    1. PRE-VALIDATION
       - Check preconditions
       - Verify permissions still valid
    
    2. EXECUTE
       - Perform the action
    
    3. POST-VALIDATION
       - Verify validation criteria
       - If failed:
           a. Trigger rollback for this step
           b. Continue rollback chain if checkpoint
    
    4. CHECKPOINT (if step has checkpoint)
       - Save state snapshot
       - Record milestone
    
    5. RECORD
       - Log step result
       - Update Project Brain
    
    if any step fails and rollback triggered:
        execute rollback_strategy
        record failure in memory
        return ExecutionResult { success: false, rollback_executed: true }
    
return ExecutionResult { success: true, summary, memory_record }
```

### Execution Result Structure
```yaml
execution_result:
  success: boolean
  steps_completed: number
  steps_failed: number
  rollback_executed: boolean
  summary: string
  memory_record:
    timestamp: datetime
    incident_id: string
    decision_rationale: string
    outcome: string
    archived: boolean
```

### Safety Guarantees
- **Atomicity:** أي step يفشل → التراجع عن جميع الـ steps السابقة حتى آخر checkpoint
- **Isolation:** إذا verdict = SANDBOX → التنفيذ في بيئة معزولة بالكامل
- **Auditability:** جميع الخطوات مسجلة في Project Brain

### Performance Budget
- **Target latency:** يعتمد على حجم الخطة
- **User-facing** — يرسل تحديثات لكل checkpoint

---

## 🔄 Cross-Cutting Concerns — اهتمامات شاملة

### Error Handling
| الخطأ | الإجراء |
|---|---|
| Layer 1 timeout | إعادة المحاولة مرة واحدة ← إبلاغ المستخدم |
| Layer 2 unknown type | إرسال إلى HUMAN_CLASSIFICATION queue |
| Layer 3 context incomplete | تقليل confidence والتقدم (بعد تسجيل تحذير) |
| Layer 4 inconclusive analysis | يمر إلى Layer 5 مع confidence منخفضة |
| Layer 5 confidence low | يُحول إلى REQUIRE_APPROVAL تلقائيًا |
| Layer 6 planning fails | BLOCK + إشعار المستخدم |
| Layer 7 execution failure | تفعيل rollback + إشعار المستخدم |

### Caching Strategy
| البيانات | مدة التخزين | السبب |
|---|---|---|
| Context results | TTL 5 min | تحسين أداء Layer 3 |
| Law check results | TTL 30 min | قوانين نادرًا ما تتغير |
| Past incident lookups | دائمة (مع ضغط) | الذاكرة طويلة المدى |
| Classification patterns | دائمة (مع تحديث) | تحسين accuracy |

### Parallel Execution
- Layers 1, 2, 5, 6 — **synchronous** (تعتمد على بعضها)
- Layer 3 — **partially parallel** (dependency graph مستقل عن memory lookup)
- Layer 7 — **sequential** (خطوات تعتمد على بعضها)

---

*This Reasoning Pipeline is the cognitive architecture of Stocky Engineering OS. Any modification to the pipeline structure must pass through the Governance Layer and be recorded in an ADR.*

*هذا الـ Reasoning Pipeline هو العقل المعماري للنظام. أي تعديل في هيكل الـ Pipeline يجب أن يمر عبر طبقة Governance ويُسجل في ADR.*
