# Stocky Engineering OS — System Vocabulary v0.1

---

> هذا القاموس هو **اللغة الرسمية** للنظام. جميع المصطلحات التالية هي Canonical — لا تُترجم ولا يُستبدل أي منها في الـ code أو الـ prompts أو الـ reasoning pipelines.
>
> This dictionary is the **official language** of the system. All terms below are canonical — never translated or substituted in code, prompts, or reasoning pipelines.

---

## 🟦 Core Terms — المصطلحات الأساسية

### EngineeringEvent
**Definition:** An observable engineering signal emitted by any system layer before risk interpretation.

**شرح:** الـ Event يمثل إشارة خام صادرة من النظام قبل التصنيف أو الحكم الهندسي عليها. قد يكون طبيعيًا (file modified) أو خطرًا كامنًا.

**Examples:** `file_modified`, `runtime_spike`, `dependency_added`, `build_failure`

---

### EngineeringIncident
**Definition:** An Event that has passed through Classification + Risk Interpretation and is flagged as a potential threat to system integrity.

**شرح:** الـ Incident هو Event بعد تحليله هندسيًا — يُعتبر خطرًا محتملًا يستدعي استجابة من النظام.

**Examples:** `architectural_drift`, `state_corruption`, `sync_integrity_failure`

---

### Drift
**Definition:** An unintended architectural deviation from the established Engineering Laws.

**شرح:** Drift هو انحراف معماري غير مقصود عن القوانين الهندسية الموضوعة — قد يكون تدريجيًا (gradual drift) أو مفاجئًا (sudden drift).

---

### Leakage
**Definition:** Unintended propagation of state, data, or side effects across architectural boundaries.

**شرح:** Leakage هو تسرب غير مقصود للحالة أو البيانات أو الآثار الجانبية عبر الحدود المعمارية.

**Examples:** `state_leakage_across_modules`, `memory_leakage`, `event_leakage`

---

### Violation
**Definition:** A clear and direct break of one or more Engineering Laws.

**شرح:** Violation هو كسر واضح ومباشر لواحد أو أكثر من القوانين الهندسية. يختلف عن Drift في أنه متعمد أو واضح وليس تدريجيًا.

---

### Intent
**Definition:** The expected engineering objective behind an Event, Incident, or execution action.

**شرح:** Intent يوضح **الغرض الهندسي المتوقع** — هل التغيير مقصود أم عرضي؟ تجريبي أم تخريبي؟

**Fields:**
- `actor`: USER | AGENT | SYSTEM
- `objective`: string
- `expected_outcome`: string
- `confidence`: float

---

### Cognition
**Definition:** The multi-stage reasoning process through which the system interprets, classifies, evaluates, and decides on engineering signals.

**شرح:** Cognition هو عملية الاستدلال والتحليل والتقييم الهندسي التي يمر بها النظام من لحظة استقبال Event إلى لحظة اتخاذ قرار التنفيذ أو المنع.

---

### Governance
**Definition:** The authority layer that controls execution — able to allow, block, sandbox, or require approval for any operation.

**شرح:** Governance هو طبقة سلطة التحكم في التنفيذ — يمكنها السماح أو المنع أو العزل (sandbox) أو طلب الموافقة على أي عملية.

---

### Confidence
**Definition:** The degree of certainty the system has in its own classification, reasoning, or risk assessment.

**شرح:** Confidence يعبر عن **مدى ثقة النظام** في تصنيفه أو استدلاله. كلما زادت البيانات المتاحة، زادت الثقة.

---

### Risk
**Definition:** A quantified measure of potential harm to system integrity, runtime stability, architectural soundness, or state consistency.

**شرح:** Risk هو مقياس كمّي للضرر المحتمل على النظام — منخفض، متوسط، مرتفع، أو كارثي. يُحتسب بعد الـ Reasoning Engine.

---

## 🟩 Event Types — أنواع الأحداث

| Event | الوصف |
|---|---|
| `compile_failure` | Syntax error, type mismatch, import failure |
| `runtime_anomaly` | Lifecycle issue, state leak, memory pressure |
| `architecture_violation` | Boundary or contract break |
| `dependency_drift` | Unauthorized or unintended dependency |
| `state_corruption` | Invalid or inconsistent state transitions |
| `sync_integrity_risk` | Queue, persistence, or sync failure |
| `memory_pressure` | High memory usage, potential leak |
| `lifecycle_leak` | Unmanaged lifecycle, dangling references |
| `unsafe_execution_intent` | Potentially destructive operation |
| `telemetry_blind_spot` | Missing observability, untracked path |
| `contract_violation` | Broken interface or protocol contract |

---

## 🟨 Propagation Scope — نطاق الانتشار

| Scope | المعنى |
|---|---|
| `local` | Confined to single module/file |
| `cross_module` | Affects multiple modules |
| `runtime_wide` | Affects entire runtime |
| `sync_impact` | Affects sync/data persistence layer |

---

## 🟥 Severity Levels — مستويات الخطورة

### Phase A: Initial Severity (قبل التحليل)
| Level | المعنى |
|---|---|
| `LOW` | Aesthetic, tooling, non-functional |
| `MEDIUM` | Behavioral but isolated |
| `HIGH` | Architectural drift or runtime risk |
| `CRITICAL` | State corruption or sync integrity |

### Phase B: Computed Severity (بعد الـ Reasoning)
يُحتسب بناءً على:
- Architectural impact
- Runtime implications
- Propagation risk
- Recovery complexity

---

## 🟪 Intent Types — أنواع الغرض الهندسي

| Intent | الوصف |
|---|---|
| `INTENTIONAL_ARCHITECTURAL` | تغيير معماري مقصود |
| `INTENTIONAL_FEATURE` | إضافة feature مقصودة |
| `ACCIDENTAL_RUNTIME` | مشكلة runtime عرضية |
| `ACCIDENTAL_DRIFT` | انحراف معماري غير مقصود |
| `EXPERIMENTAL` | تجربة أو اختبار |
| `UNSAFE_EXECUTION` | تنفيذ خطر (قد يكون تخريبيًا) |

---

## 🧠 Cognitive Pipeline Layers — طبقات التفكير

| Layer | الوظيفة |
|---|---|
| **Signal Intake** | استقبال Event وتصنيف المصدر |
| **Classification** | تحديد نوع المشكلة هندسيًا |
| **Context Resolution** | جمع السياق: الملفات، dependencies، runtime |
| **Engineering Reasoning** | تحليل root cause، مقارنة البدائل، حساب المخاطر |
| **Governance & Safety** | مراجعة معماریة قبل التنفيذ |
| **Execution Planning** | بناء execution graph + rollback |
| **Controlled Execution** | تنفيذ تدريجي مع checkpoints |

---

*This vocabulary is living and will evolve as the system grows. Any addition or modification must be approved at the Governance layer.*

*هذا القاموس حي وسيتطور مع نمو النظام. أي إضافة أو تعديل يجب أن تمر عبر طبقة Governance.*
