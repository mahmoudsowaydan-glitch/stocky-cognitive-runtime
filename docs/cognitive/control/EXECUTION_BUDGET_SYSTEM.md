# Stocky Engineering OS — Execution Budget System v0.1

---

> هذا الملف يحدد **نظام الميزانية التنفيذية** — Adaptive Budget مع Elasticity Mode و Guardrails ثابتة.
>
> This file defines the **Execution Budget System** — Adaptive Budget with Elasticity Mode and fixed Guardrails.

---

## Core Formula — الصيغة الأساسية

```
ExecutionBudget = f(RiskScore, Confidence, ContextDepth, StabilityScore)

حيث:
  RiskScore      = من Reasoning Engine (P2 Layer 4)
  Confidence     = من Classification (P2 Layer 2)
  ContextDepth   = عدد الملفات + الـ dependencies المرتبطة
  StabilityScore = من Stability Monitor (P4)
```

---

## 4-Tier Budget Model

| Tier | Risk Score | Max Steps | Reasoning Depth | Context Limit | Timeout |
|---|---|---|---|---|---|
| **Low** | < 0.3 | 3 | Shallow (L1-L3) | ≤ 5 files | 5s |
| **Medium** | 0.3 — 0.6 | 7 | Moderate (L1-L5) | ≤ 15 files | 15s |
| **High** | 0.6 — 0.85 | 12 | Full (L1-L7) | ≤ 50 files | 30s |
| **Critical** | > 0.85 | 0 | — | — | immediate BLOCK |

### Tier Determination
```
إذا كان Confidence < 0.3:
    ارفع Tier بمستوى واحد (لأن الثقة منخفضة → caution)
إذا كان ContextDepth > 20:
    ارفع Tier بمستوى واحد (تحليل أوسع يحتاج وقتًا أطول)
إذا كان StabilityScore < 0.5:
    اخفض Tier بمستوى واحد (system غير مستقر → تحفظ)
إذا كان RiskScore في الحدود بين Tier:
    استخدم الأعلى (أسلم)
```

---

## Execution Elasticity Mode — وضع المرونة التنفيذية

### Principle
```
في الظروف المستقرة → نسمح بـ Burst
في الظروف غير المستقرة → نضغط النظام
```

### Elasticity States

| Mode | الشرط | التأثير على الـ Budget |
|---|---|---|
| **BURST** | Risk < 0.2 AND Stability > 0.8 AND Confidence > 0.8 | Steps × 1.5 (ceiling 15), Timeout × 1.5, Context × 2 |
| **NORMAL** | Default | Standard allocation |
| **COMPRESS** | Risk > 0.6 OR Stability < 0.4 | Steps × 0.5 (floor 1), Timeout × 0.5, Force checkpoints |
| **FREEZE** | Risk > 0.85 OR Drift = HARD | Steps = 0, Immediate halt |

### Burst Mode Rules
```
1. Burst mode متاح فقط إذا كان النظام في IDLE أو COMPLETED لمدة > 1min
2. Burst mode يتطلب checkpoint إضافي واحد على الأقل
3. Burst mode لا يرفع الـ ceiling عن 15 step
4. بعد Burst → العودة إلى NORMAL لمدة cycle واحد على الأقل
```

### Compress Mode Rules
```
1. كل step يتطلب checkpoint
2. الـ rollback strategy تكون full_rollback دائمًا
3. Context محدود بـ essential files فقط
4. أي anomaly أثناء COMPRESS → automatic HALT
```

---

## Guardrails — القيود الثابتة

| Guardrail | Value | Violation |
|---|---|---|
| **Hard ceiling** | 15 steps max | CLIP to 15 |
| **Hard floor** | 1 step min | RAISE to 1 |
| **Absolute timeout** | 60s per cycle | HALT |
| **Burst cool-down** | 1 normal cycle | WAIT |
| **Max consecutive Burst** | 2 | FORCE to NORMAL |
| **Context hard limit** | 100 files | CLIP to 100 |
| **Checkpoint minimum** | 1 per 5 steps | AUTO-INSERT |

---

## Budget Allocation Flow — تدفق تخصيص الميزانية

```
Input: ExecutionPlan (from P2 Layer 6)
Output: BudgetedExecutionPlan (with allocated resources)

1. احسب RiskScore من Reasoning Output
2. احسب ContextDepth من Context Resolution
3. احصل على StabilityScore من Stability Monitor
4. حدد Tier الأساسي
5. طبق Elasticity Mode:
   - هل النظام مستقر؟ ← BURST
   - هل النظام غير مستقر؟ ← COMPRESS
   - كارثة؟ ← FREEZE
6. طبق Guardrails
7. إذا result = FREEZE → return HALT
8. إذا result = steps ≤ 0 → return BLOCK
9. return BudgetAllocation { tier, steps, timeout, depth, mode }
```

---

## Budget Data Structure

```yaml
BudgetAllocation:
  tier: Enum                    # LOW | MEDIUM | HIGH | CRITICAL
  elasticity_mode: Enum         # BURST | NORMAL | COMPRESS | FREEZE
  max_steps: number             # Allocated step count
  max_timeout_ms: number        # Total execution timeout
  max_context_files: number     # Max files in context
  reasoning_depth: Enum         # SHALLOW | MODERATE | FULL
  force_checkpoints: boolean    # Override checkpoint frequency
  checkpoint_interval: number   # Steps between checkpoints
  auto_sandbox: boolean         # Force sandbox execution
  governance_override: boolean  # Requires Governance approval
```

---

## Budget Verification — التحقق من الميزانية

```
قبل بدء التنفيذ، Budget Verification يتحقق:
  1. هل allocated steps ≤ plan steps؟ 
     إذا steps الطلب > allocated → CLIP + WARNING
  2. هل total timeout كافي لجميع الخطوات؟
     إذا لا → زيادة timeout أو تقليل steps
  3. هل checkpoint_interval متوافق مع allocation؟
     إذا لا → إعادة توزيع checkpoints
  4. هل sandbox مطلوب؟ 
     إذا auto_sandbox = true → إجبار Sandbox
```

---

*The Execution Budget System ensures that the system reasons and executes within safe cognitive limits — neither starved nor flooded.*

*نظام الميزانية التنفيذية يضمن أن النظام يفكر وينفذ ضمن حدود إدراكية آمنة — لا مجاعة ولا فيضان.*
