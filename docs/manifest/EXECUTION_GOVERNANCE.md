# Stocky Engineering OS — Execution Governance Model v0.1

---

> هذا الملف يحدد **قواعد الحوكمة والتنفيذ** — كيف يتم التحكم في التنفيذ، منع الانهيار، وإدارة الصلاحيات.
>
> This file defines the **governance and execution rules** — how execution is controlled, collapse is prevented, and permissions are managed.

---

## Governance Philosophy — فلسفة الحوكمة

النظام يعمل على مبدأ **Fail-Closed**:
- في حالة الشك، المنع (BLOCK) هو الخيار الافتراضي
- أي تنفيذ يحتاج إلى validation معماري قبل البدء
- أي Agent يعمل ضمن حدود صلاحياته فقط

---

## 🏛 Governance Layers

### Layer G1: Permission Model — نموذج الصلاحيات

كل Agent وكل Layer له **Trust Level** يحدد صلاحياته:

| Trust Level | الصلاحيات | أمثلة |
|---|---|---|
| **SYSTEM** | الوصول الكامل لجميع الـ Layers | Kernel, Governance |
| **TRUSTED** | تنفيذ في layers محددة مع موافقة مسبقة | Runtime Observer, Architect Agent |
| **SANDBOXED** | تنفيذ في بيئة معزولة فقط | Experimental Agents, Refactor Agent |
| **OBSERVER** | قراءة فقط — لا تنفيذ | Cognitive Observer, Telemetry |
| **EXTERNAL** | فقط API محدد — لا وصول مباشر | CI/CD integrations |

### Permission Inheritance
```
إذا كان Agent A لديه Trust Level = TRUSTED:
    - يمكنه القراءة من جميع الـ Layers
    - يمكنه الكتابة فقط في الـ Layers المصرح بها في تكوينه
    - لا يمكنه تعديل Governance Layer أو Laws
```

---

## 🛡 Execution Modes — أوضاع التنفيذ

| Mode | الوصف | متى يُستخدم |
|---|---|---|
| **AUTO** | تنفيذ تلقائي بدون تدخل | Verdict = ALLOW + Low Risk |
| **SEMI-AUTO** | تنفيذ مع عرض ملخص للمستخدم | Verdict = ALLOW + Medium Risk |
| **CONFIRM** | يتطلب موافقة المستخدم | Verdict = REQUIRE_APPROVAL |
| **MANUAL** | المستخدم ينفذ يدويًا | Verdict = BLOCK + لا يوجد بديل آلي |
| **SANDBOX** | تنفيذ في بيئة معزولة | Verdict = SANDBOX |

---

## 🧪 Sandbox Rules — قواعد البيئة المعزولة

```
1. Sandbox لها نسخة منفصلة تمامًا من:
   - File system (snapshot)
   - Runtime state (clone)
   - Memory (isolated)

2. Sandbox لا يمكنها:
   - تعديل النظام الحقيقي
   - الوصول إلى production data
   - إرسال external requests حقيقية

3. Sandbox تدمج فقط إذا:
   - اجتازت جميع validation checks
   - وافق المستخدم صراحة
   - Governance أعطت ALLOW بعد المراجعة

4. أي side effect غير متوقع داخل الـ Sandbox → تدميرها فورًا
```

---

## ⛔ BLOCK Conditions — شروط المنع

يتم **BLOCK** تلقائيًا إذا تحقق أي من الشروط التالية:

| # | الشرط | السبب |
|---|---|---|
| 1 | Violation من نوع CRITICAL | كسر قانون أساسي |
| 2 | risk_score > 0.85 | خطر كارثي |
| 3 | confidence < 0.3 و risk > 0.5 | غير متأكد لكن خطير |
| 4 | محاولة تعديل ENGINEERING_LAWS بدون ADR | تغيير غير موثق |
| 5 | محاولة تخطي Governance Layer | خرق أمني |
| 6 | Agent يحاول تنفيذ خارج صلاحياته | تجاوز صلاحيات |
| 7 | runtime_wide propagation بدون approval | تأثير واسع غير مرخص |

---

## ✅ ALLOW Conditions — شروط السماح

يتم **ALLOW** فقط إذا تحققت جميع الشروط التالية:

| # | الشرط |
|---|---|
| 1 | لا يوجد أي CRITICAL Violation |
| 2 | risk_score < 0.6 (أو موافقة صريحة من المستخدم) |
| 3 | جميع الـ pre-validation checks اجتازت |
| 4 | rollback strategy محددة (لأي عملية غير read-only) |
| 5 | Agent لديه الصلاحية الكافية |

---

## 🔐 Approval Flow — تدفق الموافقة

```
Verdict = REQUIRE_APPROVAL
    │
    ▼
يُعرض على المستخدم:
    ├── وصف التعديل
    ├── التحليل الهندسي (root cause + impact)
    ├── المخاطر (risk_score + confidence)
    ├── البدائل الممكنة
    └── التوصية
    │
    ▼
المستخدم يختار:
    ├── ALLOW — تنفيذ
    ├── BLOCK — رفض
    ├── SANDBOX — تنفيذ في بيئة معزولة
    └── MODIFY — تعديل الخطة وإعادة التقييم
    │
    ▼
إذا ALLOW أو SANDBOX → يمر على Layer 6 (Execution Planning)
إذا BLOCK → يُسجل في Memory + إشعار
إذا MODIFY → يعاد إلى Layer 4 (Reasoning) مع التعديلات
```

---

## 🧠 Trust Zones — مناطق الثقة

```
┌─────────────────────────────────────────────────────────┐
│                    TRUST ZONE 0                          │
│              Governance Layer (SYSTEM trust)             │
│         يمكنه تعديل القوانين — لكن مع ADR                │
├─────────────────────────────────────────────────────────┤
│                    TRUST ZONE 1                          │
│           Kernel + Runtime (TRUSTED trust)               │
│         يمكنه تنفيذ أي عملية ضمن نطاقه                   │
├─────────────────────────────────────────────────────────┤
│                    TRUST ZONE 2                          │
│        Cognitive + Execution (SANDBOXED trust)           │
│         معظم الـ Agents تعمل هنا                         │
├─────────────────────────────────────────────────────────┤
│                    TRUST ZONE 3                          │
│        Memory + Observability (OBSERVER trust)          │
│         قراءة فقط — تسجيل ومراقبة                        │
├─────────────────────────────────────────────────────────┤
│                    TRUST ZONE 4                          │
│            External Integrations (EXTERNAL trust)        │
│         API محدود — لا وصول مباشر                        │
└─────────────────────────────────────────────────────────┘
```

### Zone Crossing Rules
- أي محاولة للانتقال من Zone أقل ثقة إلى Zone أعلى → **تتطلب موافقة Governance**
- أي Agent في Zone 2 لا يمكنه القراءة من Zone 1 دون تصريح
- أي Agent في Zone 3 لا يمكنه الكتابة في أي Zone (Observer)

---

## 📝 Audit Trail — سجل المراجعة

كل قرار Governance يُسجل في **Audit Trail**:
```yaml
audit_entry:
  timestamp: datetime
  incident_id: string
  agent: string
  action: string
  verdict: Enum
  rationale: string
  approved_by: USER | SYSTEM | AGENT
  zone_crossing: boolean
  sandbox_used: boolean
  rollback_executed: boolean
```

### Audit Retention
- **Online (قابل للاستعلام):** آخر 30 يومًا
- **Archive (مضغوط):** إلى الأبد (جزء من Project Brain)

---

## 🚨 Incident Response — الاستجابة للحوادث

| Severity | الاستجابة |
|---|---|
| **LOW** | تسجيل + إشعار (اختياري) |
| **MEDIUM** | تسجيل + إشعار للمستخدم |
| **HIGH** | Block + إشعار فوري + تقرير مفصل |
| **CRITICAL** | Block فوري + إشعار + إنشاء ADR + مراجعة إجبارية |

### Post-Incident Review (PIR)
أي Incident مستوى HIGH أو CRITICAL يستوجب:
```
1. تحليل post-mortem
2. تحديث ENGINEERING_LAWS إذا لزم الأمر
3. تحديث Drift Detection patterns
4. تسجيل الدرس المستفاد في Project Brain
```

---

## 🧾 Governance Summary — ملخص الحوكمة

| المكون | المسؤولية | Trust Level |
|---|---|---|
| Governance Layer | منح أو منع التنفيذ | SYSTEM |
| Drift Detection Agent | مراقبة الانحراف المعماري | TRUSTED |
| Runtime Observer | مراقبة الـ Runtime | OBSERVER |
| Cognitive Observer | مراقبة جودة التفكير | OBSERVER |
| Architect Agent | اقتراح تعديلات معمارية | SANDBOXED |
| Refactor Agent | إعادة هيكلة الكود | SANDBOXED |
| Security Agent | فحص أمني | TRUSTED |
| QA Agent | اختبار وتحقق | SANDBOXED |

---

*Execution Governance is the safety backbone of Stocky Engineering OS. Any modification to governance rules must be approved by the Governance Layer and recorded in an ADR.*

*حوكمة التنفيذ هي العمود الفقري للأمان في النظام. أي تعديل في قواعد الحوكمة يجب أن يُعتمد من طبقة Governance ويُسجل في ADR.*
