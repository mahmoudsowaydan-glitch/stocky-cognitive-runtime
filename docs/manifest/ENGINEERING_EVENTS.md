# Stocky Engineering OS — Engineering Events & Incidents Model v0.1

---

> هذا الملف يحدد **النموذج الرسمي للحدث الهندسي** في النظام. الـ EngineeringEvent و EngineeringIncident هما الـ primitives الأساسية التي يبني عليها الـ Cognition Pipeline بالكامل.
>
> This file defines the **official engineering event model** of the system. EngineeringEvent and EngineeringIncident are the foundational primitives upon which the entire Cognition Pipeline is built.

---

## Core Distinction — الفصل الجوهري

| EngineeringEvent | EngineeringIncident |
|---|---|
| Raw observable signal | Event after classification + risk interpretation |
| لم يُصنّف بعد | تم تحليله هندسيًا |
| May be benign or dangerous | Considered a potential threat |
| مثال: `file_modified`, `runtime_spike` | مثال: `architectural_drift`, `state_corruption` |

**السبب من الفصل:**
- فصل observation عن judgment
- منع overreaction على إشارات عابرة
- السماح بـ multiple events → single incident
- تمييز clear بين raw data و interpreted intelligence

---

## 🟦 EngineeringEvent Model

```yaml
EngineeringEvent:
  id: string                        # Unique identifier (UUID)
  
  source: Enum                      # مصدر الحدث
    - USER                          # طلب أو فعل مباشر من المستخدم
    - SYSTEM_AGENT                  # Agent تابع للنظام (Refactor, QA, ...)
    - RUNTIME_OBSERVER              # مراقب runtime مباشر
    - DRIFT_DETECTOR                # كاشف الانحراف المعماري
    - TELEMETRY                     # بيانات مراقبة وقياس
    - EXTERNAL_INTEGRATION          # مصدر خارجي (CI/CD, hook, ...)
  
  type: Enum                        # نوع الحدث الهندسي
    - COMPILE_FAILURE               # Syntax error, type mismatch, import failure
    - RUNTIME_ANOMALY               # Lifecycle issue, state leak, memory pressure
    - ARCHITECTURE_VIOLATION        # Boundary or contract break
    - DEPENDENCY_DRIFT              # Unauthorized or unintended dependency
    - STATE_CORRUPTION              # Invalid or inconsistent state transitions
    - SYNC_INTEGRITY_RISK           # Queue, persistence, or sync failure
    - MEMORY_PRESSURE               # High memory usage, potential leak
    - LIFECYCLE_LEAK                # Unmanaged lifecycle, dangling references
    - UNSAFE_EXECUTION_INTENT       # Potentially destructive operation
    - TELEMETRY_BLIND_SPOT          # Missing observability, untracked path
    - CONTRACT_VIOLATION            # Broken interface or protocol contract
  
  initial_severity: Enum            # Severity قبل التحليل (Phase A)
    - LOW                           # تجميلي، tooling
    - MEDIUM                        # سلوكي لكن معزول
    - HIGH                          # خطورة معمارية أو runtime
    - CRITICAL                      # فساد حالة أو sync integrity
  
  timestamp: datetime               # وقت الحدث
  
  snapshot:                         # لقطة للسياق عند لحظة الحدث
    layer_affected: Enum            # الطبقة المتأثرة
      - KERNEL
      - RUNTIME
      - COGNITIVE
      - AGENT
      - EXECUTION
      - MEMORY
      - OBSERVABILITY
    files_involved: [string]        # الملفات المرتبطة
    runtime_state: object|null      # حالة runtime عند الحدث
    dependency_chain: [string]|null  # سلسلة التبعيات المرتبطة
  
  metadata:                         # بيانات إضافية
    raw_message: string             # الرسالة الخام (إن وجدت)
    stack_trace: string|null        # Stack trace (إن وجد)
    environment: object|null        # بيئة التنفيذ
```

---

## 🟥 EngineeringIncident Model

```yaml
EngineeringIncident:
  id: string                        # Unique identifier (UUID)
  event_ids: [string]               # واحد أو أكثر من Events سببوا الـ Incident
  
  classification:                   # مخرجات Layer 2 — Classification Engine
    category: string                # تصنيف دقيق
    confidence: float               # 0.0 - 1.0 (ثقة التصنيف)
    severity: Enum                  # Computed Severity — Phase B
      - LOW
      - MEDIUM
      - HIGH
      - CRITICAL
  
  intent:                           # الغرض الهندسي
    actor: Enum                     # USER | AGENT | SYSTEM
    objective: string               # الهدف المعلن
    expected_outcome: string        # النتيجة المتوقعة
    confidence: float               # 0.0 - 1.0 (ثقة تحديد الـ intent)
  
  propagation_scope:                # نطاق انتشار التأثير
    local: boolean                  # confined to single module
    cross_module: boolean           # affects multiple modules
    runtime_wide: boolean           # affects entire runtime
    sync_impact: boolean            # affects persistence layer
  
  reasoning_output:                 # مخرجات Layer 4 — Engineering Reasoning Engine
    root_cause: string              # السبب الجذري
    impact_analysis: string         # تحليل التأثير
    alternatives: [string]          # البدائل الممكنة
    risk_score: float               # 0.0 - 1.0 (درجة الخطر)
    confidence_score: float         # 0.0 - 1.0 (ثقة التحليل — منفصلة عن risk)
  
  governance_verdict: Enum          # مخرجات Layer 5 — Governance & Safety
    - ALLOW                         # تنفيذ مسموح
    - BLOCK                         # تنفيذ ممنوع
    - SANDBOX                       # تنفيذ في بيئة معزولة
    - REQUIRE_APPROVAL              # يحتاج موافقة المستخدم
  
  execution_plan: object|null       # مخرجات Layer 6 — Execution Planning Layer
    steps: [                        # خطوات التنفيذ
      {
        id: string
        action: string
        validation: string
        rollback: string
      }
    ]
    rollback_strategy: string       # استراتيجية التراجع
    checkpoints: [string]           # نقاط التوقف للتحقق
  
  memory_record:                    # للتخزين في Project Brain
    timestamp: datetime
    decision_rationale: string      # لماذا اتخذ هذا القرار
    outcome: string                 # النتيجة النهائية
    archived: boolean               # أُرشفت في الذاكرة طويلة المدى؟
```

---

## 🧠 Two-Phase Severity Model — نموذج الخطورة ثنائي المرحلة

### Phase A: Initial Severity
يُحتسب فور استقبال الـ Event بناءً على:
- Source المصدر
- Type النوع
- Layer الطبقة المتأثرة
- Operation type نوع العملية

**القاعدة:** Initial Severity **لا يمكن أن تقل عن** Medium لأي Event مصدره `DRIFT_DETECTOR` أو `RUNTIME_OBSERVER`.

### Phase B: Computed Severity
يُحتسب بعد المرور على الـ Reasoning Engine بناءً على:
- Architectural impact — هل يكسر boundaries أو contracts؟
- Runtime implications — هل يسبب lifecycle leak أو state corruption؟
- Propagation risk — هل سينتشر التأثير عبر modules؟
- Recovery complexity — هل التراجع سهل أم معقد؟
- Intent confidence — هل الفعل مقصود أم عرضي؟

### Mapping Rule
```
إذا كان computed_severity < initial_severity:
    استخدم computed_severity (ما لم يكن initial_severity == CRITICAL)
إذا كان computed_severity > initial_severity:
    استخدم computed_severity
إذا كان initial_severity == CRITICAL:
    يمر حتمًا على Governance Layer
```

---

## 🔗 Event → Incident Flow

```
Raw Signal (User, Runtime, Agent...)
    │
    ▼
[Layer 1] Signal Intake
    │  يصنف المصدر + initial_severity
    ▼
[Layer 2] Classification Engine
    │  يحدد النوع + confidence
    ▼
┌─────────────────────────────┐
│  EngineeringIncident Created │
│  (event_ids + classification)│
└─────────────────────────────┘
    │
    ▼
[Layer 3] Context Resolution
    │  يجمع السياق والمخلفات
    ▼
[Layer 4] Engineering Reasoning
    │  root cause + risk_score + alternatives
    ▼
[Layer 5] Governance & Safety
    │  verdict: ALLOW | BLOCK | SANDBOX | REQUIRE_APPROVAL
    ▼
[Layer 6] Execution Planning
    │  build execution plan + rollback
    ▼
[Layer 7] Controlled Execution
    │  execute + validate + record
```

---

## 📊 Risk Score vs Confidence Score — الفصل الحاسم

| Risk Score | Confidence Score |
|---|---|
| يقيس **الخطر** على النظام | يقيس **ثقة النظام** في تحليله |
| 0.0 = no risk | 0.0 = uncertain |
| 1.0 = catastrophic | 1.0 = certain |
| **مثال:** risk=0.9, confidence=0.3 → قلق جدًا لكن غير متأكد → أحتاج موافقة المستخدم | **مثال:** risk=0.2, confidence=0.95 → مطمئن وواثق → تنفيذ تلقائي |

### Decision Matrix
| Risk ↓ \ Confidence → | Low | Medium | High |
|---|---|---|---|
| **Low** | ALLOW | ALLOW | ALLOW |
| **Medium** | SANDBOX | SANDBOX | REQUIRE_APPROVAL |
| **High** | BLOCK | BLOCK | REQUIRE_APPROVAL |
| **Critical** | BLOCK | BLOCK | BLOCK |

---

## 🧪 Example Scenarios — سيناريوهات توضيحية

### Example 1: Compile Failure
```yaml
Event:
  source: USER
  type: COMPILE_FAILURE
  initial_severity: MEDIUM

Incident:
  classification:
    severity: LOW (بعد التحليل — import خطأ في ملف واحد فقط)
  intent:
    actor: USER
    objective: "إضافة import جديد"
  propagation_scope:
    local: true
  governance_verdict: ALLOW
```

### Example 2: Runtime State Leakage
```yaml
Event:
  source: RUNTIME_OBSERVER
  type: RUNTIME_ANOMALY
  initial_severity: HIGH

Incident:
  classification:
    severity: HIGH (بعد التحليل — state leak across modules)
  intent:
    actor: SYSTEM
    objective: "تحديث غير مقصود لحالة مشتركة"
    confidence: 0.4
  propagation_scope:
    cross_module: true
    runtime_wide: false
  reasoning_output:
    risk_score: 0.7
    confidence_score: 0.6
  governance_verdict: SANDBOX
```

### Example 3: Architecture Violation
```yaml
Event:
  source: DRIFT_DETECTOR
  type: ARCHITECTURE_VIOLATION
  initial_severity: CRITICAL

Incident:
  classification:
    severity: CRITICAL
  intent:
    actor: AGENT
    objective: "إضافة dependency مباشرة على domain layer"
    confidence: 0.9
  propagation_scope:
    cross_module: true
    runtime_wide: true
    sync_impact: true
  reasoning_output:
    risk_score: 0.95
    confidence_score: 0.85
  governance_verdict: BLOCK
```

---

*This model will evolve with the system. Any change to the Event/Incident structure must pass through the Governance Layer.*

*هذا النموذج سيتطور مع النظام. أي تغيير في بنية الـ Event/Incident يجب أن يمر عبر طبقة Governance.*
