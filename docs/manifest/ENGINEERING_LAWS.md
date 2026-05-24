# Stocky Engineering OS — Engineering Laws v0.1

---

> هذه هي **القوانين الهندسية الرسمية** للنظام. لا يمكن كسر أي من هذه القوانين دون المرور على Governance Layer وتوثيق القرار في ADR.
>
> These are the **official engineering laws** of the system. No law may be broken without passing through the Governance Layer and documenting the decision in an ADR.

---

## Preamble — الديباجة

### لماذا القوانين؟
النظام يهدف إلى الحفاظ على **الانضباط الهندسي** عبر الزمن. الـ Laws تمنع:
- Architectural drift
- Dependency chaos
- Runtime corruption
- Cognitive inconsistency
- Safety violations

### كيف تطبق؟
- تلقائيًا عبر **Drift Detection Agent**
- يدويًا عند **Code Review** و **Architecture Review**
- قبليًا عبر **Governance Layer** قبل أي تنفيذ

### من يخضع للقوانين؟
- جميع الـ Agents
- جميع الـ Layers
- جميع التعديلات المقترحة (User أو Agent أو System)

---

## 🏛 Category 1: Architecture Laws (قوانين معمارية)

### AL-01: Layer Independence
```
Domain layer cannot depend on runtime layer.
```
**شرح:** الطبقة المنطقية (Domain) يجب ألا تعتمد على أي تفاصيل Runtime (HTTP, Queue, DB, File System).

**Violation Risk:** CRITICAL — يؤدي إلى coupling غير قابل للفصل.

**Detection:** تحليل الـ imports والتوجيهات — أي Domain module يستورد من Runtime layer.

---

### AL-02: Deterministic State Transitions
```
State transitions must be deterministic.
```
**شرح:** كل انتقال حالة يجب أن يكون محددًا — نفس input يعطي نفس output بغض النظر عن وقت أو سياق التنفيذ.

**Violation Risk:** HIGH — يؤدي إلى unpredictable behavior.

**Detection:** تحليل functions اللي بتغير state — وجود external state أو I/O داخل transition logic.

---

### AL-03: Architecture Validation Precedes Execution
```
Architecture validation must complete before any execution begins.
```
**شرح:** لا تنفيذ قبل التحقق المعماري — الـ Governance Layer تفحص أي Intent قبل السماح بالتنفيذ.

**Violation Risk:** CRITICAL — يمكن أن يؤدي إلى تدمير الـ architecture.

**Enforcement:** Governance Layer تمنع أي Execution Plan لم يجتز الـ validation.

---

### AL-04: Defined Contracts at Every Boundary
```
Every architectural boundary must have a defined and versioned contract.
```
**شرح:** أي حدود بين طبقتين أو Moduleين لازم يكون ليها Contract واضح (Interface, Protocol, Schema).

**Violation Risk:** MEDIUM → HIGH — يؤدي إلى fragile integration.

---

### AL-05: No Cross-Layer Shortcuts
```
No layer may bypass an intermediate layer to access a deeper layer directly.
```
**شرح:** Presentation → Domain مباشر مسموح. Presentation → Data مباشر ممنوع.

**Violation Risk:** HIGH — يكسر encapsulation ويزيد coupling.

---

## 🔗 Category 2: Dependency Laws (قوانين تبعيات)

### DL-01: Inward Dependency Direction
```
Dependencies must point inward toward domain layers.
```
**شرح:** الـ outer layers (Presentation, Infrastructure) تعتمد على inner layers (Domain). العكس ممنوع.

**Violation Risk:** CRITICAL — يؤدي إلى circular dependency.

---

### DL-02: No Circular Dependencies
```
Circular dependencies between modules or layers are strictly forbidden.
```
**شرح:** A → B → A ممنوع تمامًا.

**Violation Risk:** CRITICAL — يمنع التطوير المستقل ويسبب runtime deadlocks.

**Detection:** تحليل dependency graph دوريًا عبر Drift Detection Agent.

---

### DL-03: Contract-Mediated Communication
```
Cross-module communication must be mediated by contracts, not direct implementation references.
```
**شرح:** Module A لا يستدعي implementation في Module B مباشرة. Uses interfaces / ports.

**Violation Risk:** HIGH — يؤدي إلى tight coupling.

---

### DL-04: Explicit Dependency Declaration
```
All dependencies must be explicitly declared. No ambient or implicit dependencies.
```
**شرح:** أي dependency لازم تكون مصرح بها. لا يمكن استخدام global state أو service locator كـ hidden dependency.

**Violation Risk:** MEDIUM → HIGH — يؤدي إلى invisible coupling.

---

## ⚡ Category 3: Runtime Laws (قوانين تشغيلية)

### RL-01: Passive Telemetry
```
Telemetry must be passive — it must not alter system behavior, state, or performance profile.
```
**شرح:** المراقبة (logging, metrics, tracing) لازم تكون **بدون side effects**. لا تؤثر على business logic أو state.

**Violation Risk:** HIGH — يؤدي إلى Heisenberg effect (المراقبة تغير السلوك).

---

### RL-02: Sync Runtime Cannot Mutate Domain Directly
```
The sync/persistence layer cannot mutate domain state directly — only through domain commands.
```
**شرح:** الـ sync layer (queues, DB, cache) لا يعدّل domain objects مباشرة. يستخدم commands / events.

**Violation Risk:** CRITICAL — يؤدي إلى state corruption.

---

### RL-03: Explicit Async Boundary Declaration
```
Every async boundary (thread, task, event bus, message queue) must be explicitly declared and documented.
```
**شرح:** لا يمكن أن يحدث async communication بدون تعريف رسمي للـ boundary.

**Violation Risk:** HIGH — يؤدي إلى implicit concurrency وrace conditions.

---

### RL-04: Lifecycle Ownership
```
Every resource (memory, connection, file handle) must have a clear, single owner responsible for its lifecycle.
```
**شرح:** أي resource لازم يكون ليه owner واحد واضح مسؤول عن إنشائه وتدميره.

**Violation Risk:** MEDIUM → HIGH — يؤدي إلى leaks وdangling references.

---

### RL-05: Deterministic Async Handling
```
Async operations must have deterministic timeout and error handling defined at the call site.
```
**شرح:** أي async call لازم يكون عنده timeout و error handling واضحين — ممنوع fire-and-forget بدون handling.

**Violation Risk:** MEDIUM — يؤدي إلى silent failures وzombie operations.

---

## 🧠 Category 4: Cognitive Laws (قوانين إدراكية)

### CL-01: Rationale Recording
```
Every engineering decision must have a recorded rationale — why this choice over alternatives.
```
**شرح:** أي قرار هندسي لازم يُوثق معه الـ rationale (لماذا تم الاختيار والبدائل).

**Violation Risk:** MEDIUM — يؤدي إلى فقدان الذاكرة الهندسية.

---

### CL-02: Context Compression
```
Context must be compressed before long-term memory storage to prevent memory bloat.
```
**شرح:** عند تخزين أي Context في الذاكرة طويلة المدى، يتم ضغطه (إزالة التفاصيل غير المهمة، الاحتفاظ بالجوهر).

**Violation Risk:** MEDIUM → HIGH يؤدي إلى cognitive overload.

---

### CL-03: Confidence Transparency
```
Every classification and reasoning output must report its confidence score.
```
**شرح:** أي تصنيف أو استدلال لازم يبلغ عن درجة الثقة (0.0 - 1.0) — لا يمكن تقديم result بدون confidence.

**Violation Risk:** LOW → MEDIUM — يؤدي إلى false sense of certainty.

---

### CL-04: Separation of Observation from Judgment
```
The system must clearly separate raw observation (Event) from interpreted judgment (Incident).
```
**شرح:** لا يمكن خلط raw signal مع interpreted risk — Event مختلف عن Incident.

**Violation Risk:** HIGH — يؤدي إلى biased cognition.

---

## 🛡 Category 5: Safety Laws (قوانين أمان)

### SL-01: Rollback Requirement
```
Every execution must have a defined rollback strategy before execution begins.
```
**شرح:** أي عملية تنفيذ لازم يكون ليها استراتيجية تراجع محددة — ممنوع التنفيذ بدون rollback plan.

**Violation Risk:** CRITICAL — يمكن أن يترك النظام في حالة غير قابلة للاسترداد.

---

### SL-02: Critical Operations Require Human Approval
```
Operations classified as CRITICAL severity must require explicit human approval before execution.
```
**شرح:** أي عملية severity = CRITICAL لا تنفذ إلا بموافقة المستخدم الصريحة.

**Violation Risk:** CRITICAL — يؤدي إلى تغيير غير مراقب.

**Enforcement:** Governance Layer تمنع التنفيذ حتى approval.

---

### SL-03: Sandboxed Execution Isolation
```
Sandboxed execution must have zero side effects on the actual system state.
```
**شرح:** الـ Sandbox يمثل بيئة معزولة — لا يمكنه التأثير على النظام الحقيقي.

**Violation Risk:** CRITICAL — يؤدي إلى state corruption خارج الـ sandbox.

---

### SL-04: Fail-Closed Security Model
```
In case of uncertainty or error in governance checks, the system must default to BLOCK rather than ALLOW.
```
**شرح:** إذا كان النظام غير قادر على تحديد هل عملية آمنة أم لا، يتم منعها (BLOCK).

**Violation Risk:** HIGH — يؤدي إلى vulnerabilities.

---

### SL-05: Least Privilege Execution
```
Every Agent and Layer must operate with the minimum authority necessary for its function.
```
**شرح:** أي Agent ليست له صلاحيات زائدة عن حاجته — لا يمكن لأي Agent تنفيذ عمليات خارج نطاقه.

---

## 📊 Violation Classification — تصنيف الخروقات

| Level | المعنى | Consequence |
|---|---|---|
| **Minor** | Violation لا يؤثر على runtime أو architecture | Warning + تسجيل |
| **Major** | Violation قد يسبب instability أو drift | Block + تقرير إلى Governance |
| **Critical** | Violation يكسر foundational law | Block فوري + إشعار المستخدم + تسجيل ADR |

### Violation → Incident Mapping
```
Minor Violation → EngineeringIncident.severity = LOW
Major Violation → EngineeringIncident.severity = HIGH
Critical Violation → EngineeringIncident.severity = CRITICAL
```

---

## 🔧 Enforcement Mechanism — آلية التطبيق

| الآلية | المسؤول | Coverage |
|---|---|---|
| **Automated Static Analysis** | Drift Detection Agent | AL-01, AL-05, DL-01, DL-02, DL-04, RL-03 |
| **Runtime Monitoring** | Runtime Observer | RL-01, RL-02, RL-04, RL-05 |
| **Pre-Execution Governance** | Governance Layer | AL-03, SL-01, SL-02, SL-03, SL-04, SL-05 |
| **Audit & Review** | Cognitive Observer | CL-01, CL-02, CL-03, CL-04 |

---

## 📝 Law Change Process — عملية تعديل القوانين

```
1. Propose change in an ADR (Architecture Decision Record)
2. Submit to Governance Layer for review
3. Impact analysis on all existing modules
4. Majority approval from active Agents
5. Update ENGINEERING_LAWS.md
6. Record rationale in Project Brain
```

---

## 🧾 Summary Table — جدول ملخص القوانين

| ID | Law | Risk | Enforcement |
|---|---|---|---|
| AL-01 | Domain independence from runtime | CRITICAL | Static Analysis |
| AL-02 | Deterministic state transitions | HIGH | Static Analysis |
| AL-03 | Architecture validation before execution | CRITICAL | Governance |
| AL-04 | Defined contracts at boundaries | MEDIUM→HIGH | Review |
| AL-05 | No cross-layer shortcuts | HIGH | Static Analysis |
| DL-01 | Inward dependency direction | CRITICAL | Static Analysis |
| DL-02 | No circular dependencies | CRITICAL | Static Analysis |
| DL-03 | Contract-mediated communication | HIGH | Static Analysis |
| DL-04 | Explicit dependency declaration | MEDIUM→HIGH | Static Analysis |
| RL-01 | Passive telemetry | HIGH | Runtime Monitor |
| RL-02 | Sync layer domain mutation | CRITICAL | Runtime Monitor |
| RL-03 | Explicit async boundaries | HIGH | Static Analysis |
| RL-04 | Lifecycle ownership | MEDIUM→HIGH | Runtime Monitor |
| RL-05 | Deterministic async handling | MEDIUM | Runtime Monitor |
| CL-01 | Rationale recording | MEDIUM | Audit |
| CL-02 | Context compression | MEDIUM→HIGH | Audit |
| CL-03 | Confidence transparency | LOW→MEDIUM | Audit |
| CL-04 | Observation vs judgment separation | HIGH | Review |
| SL-01 | Rollback requirement | CRITICAL | Governance |
| SL-02 | Critical ops require approval | CRITICAL | Governance |
| SL-03 | Sandboxed execution isolation | CRITICAL | Governance |
| SL-04 | Fail-closed security | HIGH | Governance |
| SL-05 | Least privilege execution | HIGH | Governance |

---

*These laws are the constitutional foundation of Stocky Engineering OS. Any violation, modification, or exception must be formally documented and approved.*

*هذه القوانين هي الأساس الدستوري للنظام. أي خرق أو تعديل أو استثناء يجب أن يُوثق رسميًا ويُعتمد.*
