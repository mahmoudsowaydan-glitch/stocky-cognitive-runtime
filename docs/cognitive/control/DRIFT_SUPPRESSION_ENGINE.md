# Stocky Engineering OS — Drift Suppression Engine v0.1

---

> هذا الملف يحدد **محرك قمع الانحراف** — طبقة مستقلة تمامًا عن Observer تكتشف الانحراف المعماري والتشغيلي المبكر وتتدخل قبل أن ينتشر.
>
> This file defines the **Drift Suppression Engine** — a fully independent layer that detects architectural and operational drift early and intervenes before propagation.

---

## Core Principle — المبدأ الأساسي

```
Drift Suppression Engine:
  - مستقل تمامًا عن Live Observer (P3)
  - يقرأ من Observer فقط — لا يكتب إليه
  - يقرأ من Dependency Graph + Runtime State مباشرة
  - له سلطة WARNING / PAUSE / BLOCK
```

---

## Module Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DRIFT SUPPRESSION ENGINE               │
│                                                          │
│  ┌─────────────────┐  ┌────────────────┐                │
│  │ Drift Detector   │  │ Drift          │                │
│  │ (reads state)    │──▶ Classifier     │                │
│  └─────────────────┘  └───────┬────────┘                │
│                               │                          │
│                               ▼                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │           Intervention Decision Engine              │  │
│  │  WARN / PAUSE / BLOCK / ESCALATE_TO_GOVERNANCE     │  │
│  └───────────────────────────────────────────────────┘  │
│                               │                          │
│                               ▼                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │           Propagation Isolation Engine              │  │
│  │  عزل scope المتأثر  ·  Stop contamination           │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Drift Types — أنواع الانحراف التي يكتشفها

| Drift Type | المصدر | الوصف |
|---|---|---|
| **Architectural Boundary** | Dependency Graph + Laws | Layer crossing غير مصرح به |
| **Dependency Cycle** | Dependency Graph | Circular dependency جديد |
| **State Inconsistency** | Runtime State | State يختلف عن المتوقع |
| **Contract Violation** | Interface Definitions | Interface تغير بدون تحديث المستهلكين |
| **Lifecycle Leak** | Resource Monitor | Resource غير مُدار (leak) |
| **Async Boundary** | Thread/Task Monitor | Async operation بدون declared boundary |
| **Memory Trend** | Memory Monitor | زيادة غير طبيعية في الذاكرة |
| **Execution Pattern** | Trace Stream | نمط تنفيذ غير طبيعي (مثلاً تنفيذ same step 3 times) |

---

## Drift Classification — تصنيف الانحراف

### 3-Level Severity Model

| Level | Severity | الانتشار | الإجراء |
|---|---|---|---|
| **Soft Drift** | محلي، سهل الإصلاح | confined to single module | WARNING + تسجيل |
| **Medium Drift** | عبر Module واحد، يحتاج تدخل | cross_module | PAUSE + إعادة توجيه + عزل module |
| **Hard Drift** | عبر Layers متعددة، خطر | runtime_wide أو sync_impact | BLOCK + Governance |

### Classification Logic
```
إذا كان drift scope = local:
    إذا كان violation = AL-04 (contract) أو DL-04 (dependency):
        Soft Drift
    وإلا:
        Medium Drift

إذا كان drift scope = cross_module:
    Medium Drift

إذا كان drift scope = runtime_wide أو sync_impact:
    Hard Drift

إذا كان drift يكسر أي CRITICAL Law (AL-01, AL-03, DL-01, DL-02, RL-02, SL-01):
    Hard Drift (تصعيد تلقائي)

إذا كان نفس الـ drift type يتكرر 3+ مرات في آخر 10 دقائق:
    ارفع مستوى واحد (Soft → Medium, Medium → Hard)
```

---

## Intervention Actions — إجراءات التدخل

### WARNING
```
1. تسجيل drift في Memory
2. إرسال إشعار إلى Governance Layer
3. Allow execution to continue (مع إضافة checkpoint)
4. عدم تغيير Budget
```

### PAUSE
```
1. إيقاف Execution Engine مؤقتًا
2. عزل الـ module المتأثر (Propagation Isolation)
3. تسجيل drift في Memory
4. إبلاغ Stability Monitor
5. طلب إعادة تقييم من Reasoning Pipeline
6. السماح بعد إعادة التقييم أو escalate إلى BLOCK
```

### BLOCK
```
1. إيقاف Execution Engine فورًا
2. عزل جميع الـ modules المتأثرة
3. تسجيل Hard Drift في Memory (immutable)
4. إبلاغ Governance Layer
5. طلب ADR (Architecture Decision Record) للحل
6. لا يمكن رفع BLOCK إلا عن طريق Governance
```

### ESCALATE_TO_GOVERNANCE
```
1. إرسال تقرير كامل إلى Governance Layer
2. يتضمن: drift type, severity, scope, root cause, recommendation
3. Governance تقرر: ALLOW (مع شروط) | BLOCK (نهائي) | MODIFY (تعديل القوانين)
```

---

## Propagation Isolation Engine — محرك عزل الانتشار

### Purpose
منع انتشار الـ drift من scope المصاب إلى باقي النظام.

### Isolation Strategy Selection
| Scope | Strategy |
|---|---|
| Local (single module) | Mark module as ISOLATED — تعليق التنفيذ فيه فقط |
| Cross-module | Mark all affected modules as QUARANTINED — قطع connections بينهم |
| Runtime-wide | HALT جميع الـ executions + freeze runtime |

### Isolation Flow
```
1. تحديد scope المصاب بالـ drift
2. تحديد جميع الـ modules المتصلة به (dependency graph)
3. قطع connections بين module المصاب والباقي
4. Mark module المصاب كـ ISOLATED في Runtime State
5. تسجيل العزل في Memory
6. السماح باستمرار التنفيذ في الـ modules غير المصابة (إذا أمكن)
```

### Isolation Recovery
```
1. إصلاح root cause
2. اختبار الـ module المعزول في Sandbox
3. إذا اجتاز الاختبار → إعادة الدمج (UNISOLATE)
4. إذا فشل → بقاء ISOLATED + إبلاغ Governance
```

---

## Drift Record Structure

```yaml
DriftRecord:
  id: string
  timestamp: datetime
  drift_type: Enum              # Type from Drift Types table
  severity: Enum                # SOFT | MEDIUM | HARD
  scope: Enum                   # LOCAL | CROSS_MODULE | RUNTIME_WIDE | SYNC_IMPACT
  source_module: string
  affected_modules: [string]
  law_violated: string|null     # Reference to ENGINEERING_LAWS.md
  detection_method: string      # How it was detected
  intervention: Enum            # WARN | PAUSE | BLOCK | ESCALATED
  intervention_result: string   # What happened after intervention
  isolated: boolean
  resolved: boolean
  resolution_timestamp: datetime|null
  root_cause: string
  memory_id: string             # Reference in Memory Recording
```

---

## Independence Guarantees — ضمانات الاستقلالية

| Guarantee | Enforcement |
|---|---|
| يقرأ من Observer فقط — لا يكتب | Read-only connection |
| يقرأ من Dependency Graph مباشر | Direct connection |
| لا يعتمد على Reasoning Pipeline | Independent execution path |
| لديه cache خاص به | No shared cache with P3 |
| تدخله يسجل في Memory منفصل | Separate entry type |

---

*The Drift Suppression Engine is the internal police of Stocky Engineering OS. It watches independently and acts decisively to prevent architectural decay.*

*محرك قمع الانحراف هو الشرطي الداخلي للنظام. يراقب باستقلالية ويتدخل بحسم لمنع الانهيار المعماري.*
