# Stocky Engineering OS — Cognitive Control Layer Overview v0.1

---

> هذا الملف هو **الخريطة الرئيسية لـ P4-A Cognitive Control Layer** — طبقة التحكم التي تحكم الذكاء وتنظم التنفيذ وتمنع الانهيار المعرفي.
>
> This file is the **master map of P4-A Cognitive Control Layer** — the command layer that governs intelligence, regulates execution, and prevents cognitive collapse.

---

## Core Philosophy — الفلسفة الأساسية

```
الذكاء لا يُمنع… لكنه يُنظَّم
Intelligence is not prevented… it is regulated
```

النظام الآن لديه:
- 🧠 عقل يفكر (P2 Reasoning Pipeline)
- ⚡ جهاز عصبي ينفذ (P3 Runtime Engine)
- 🛡️ طبقة تحكم حاكمة (P4 Control Layer — هنا)

---

## Architecture Overview — بنية التحكم الكلية

```
                    ┌────────────────────────────────────────┐
                    │           GOVERNANCE LAYER (P2-L5)      │
                    │    Ultimate authority — overrides all   │
                    └──────────────────┬─────────────────────┘
                                       │ final_verdict
                                       ▼
┌───────────────────────────────────────────────────────────────────────┐
│                       COGNITIVE CONTROL LAYER (P4-A)                  │
│                                                                       │
│  ┌─────────────────┐   ┌──────────────────┐   ┌───────────────────┐  │
│  │  RISK DAMPENING │   │  EXECUTION        │   │  DRIFT            │  │
│  │  SYSTEM         │──▶│  BUDGET SYSTEM    │   │  SUPPRESSION      │  │
│  │  Smooths risk   │   │  Adaptive + Tier  │   │  ENGINE           │  │
│  └─────────────────┘   └────────┬─────────┘   │  Independent      │  │
│                                 │              └────────┬──────────┘  │
│                                 ▼                       │             │
│  ┌─────────────────┐   ┌──────────────────┐            │             │
│  │  COGNITIVE      │   │  STABILITY       │            │             │
│  │  RATE LIMITER   │   │  MONITOR         │            │             │
│  │  Context-aware  │   │  Loop detection  │            │             │
│  └─────────────────┘   └──────────────────┘            │             │
│                                 │                       │             │
│                                 ▼                       ▼             │
│                    ┌────────────────────────────────────────┐         │
│                    │     CONTROL ARBITRATION LOGIC          │         │
│                    │  Resolves conflicts between controllers│         │
│                    │  Produces single authoritative verdict │         │
│                    └────────────────┬───────────────────────┘         │
└─────────────────────────────────────┼─────────────────────────────────┘
                                      │ combined_control_verdict
                                      ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     REASONING + RUNTIME (P2 + P3)                     │
│              ينفذ تحت إشراف Control Layer — مقيد بالـ Budget          │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Control Arbitration Logic — منطق التحكيم بين وحدات التحكم

### Why — لماذا نحتاج Arbitration؟

لدينا 5 أنظمة تحكم قد تصدر قرارات متعارضة:

| Controller | Decision | Authority |
|---|---|---|
| Budget System | EXECUTE with 5 steps | Steps + Depth |
| Drift Suppression | WARN - intervene | Pause + Block |
| Stability Monitor | HALT execution | Full stop |
| Rate Limiter | DELAY - backoff | Throttle |
| Risk Dampening | PASS (smoothed signal) | Inform only |

**المشكلة:** لو Budget قال EXECUTE و Drift قال BLOCK — من نصدق؟

### Arbitration Logic — Deterministic Resolution

```yaml
ArbitrationRules:
  - rule: "HALT from Stability Monitor overrides all other signals"
    priority: 1
    action: IMMEDIATE_HALT
  
  - rule: "Hard Drift BLOCK overrides Budget + Rate Limiter"
    priority: 2
    action: BLOCK + REPORT_TO_GOVERNANCE
  
  - rule: "Medium Drift with Budget HIGH → downgrade to Critical Budget (Tier 3)"
    priority: 3
    action: DOWNGRADE_BUDGET + SANDBOX
  
  - rule: "Rate Limiter DELAY with Budget LOW → respect delay"
    priority: 4
    action: APPLY_BACKOFF
  
  - rule: "Soft Drift WARN + Budget MEDIUM → continue with increased checkpoints"
    priority: 5
    action: CONTINUE_WITH_CHECKPOINTS
  
  - rule: "All pass or Low signals → standard Budget allocation"
    priority: 6
    action: STANDARD_EXECUTION
```

### Arbitration Priority Stack
```
Priority 1: HALT (Stability Monitor)
Priority 2: BLOCK (Drift Suppression - Hard)
Priority 3: DOWNGRADE (Drift + Budget conflict)
Priority 4: THROTTLE (Rate Limiter)
Priority 5: WARN (Drift - Soft/Medium)
Priority 6: PASS (Normal execution)
```

Any controller can **escalate** to Governance Layer at any time.

---

## Module Map — خريطة الوحدات

| Module | الملف | الوظيفة | Authority |
|---|---|---|---|
| **Risk Dampening System** | `RISK_DAMPENING_SYSTEM.md` | Smooths raw risk signals, maintains baseline | Inform only |
| **Execution Budget System** | `EXECUTION_BUDGET_SYSTEM.md` | Allocates steps/depth/time per risk tier | Steps/Depth control |
| **Drift Suppression Engine** | `DRIFT_SUPPRESSION_ENGINE.md` | Detects + classifies + intervenes on drift | WARN / PAUSE / BLOCK |
| **Stability Monitor** | `STABILITY_MONITOR.md` | Loop detection, cognitive health | HALT |
| **Cognitive Rate Limiter** | `COGNITIVE_RATE_LIMITER.md` | Context-aware throttling | DELAY / BACKOFF |
| **Control Arbitration** | *(implicit — in this file)* | Resolves conflicts | Single authoritative verdict |

---

## Control Flow — التدفق الحركي

```
1. Event يصل إلى Reasoning Pipeline (P2)
       │
       ▼
2. Risk Dampening System يحسب smoothed_risk_baseline
       │
       ▼
3. Execution Budget System يحدد Tier (Low/Medium/High/Critical)
       │
       ▼
4. Reasoning + Execution يتم ضمن الـ Budget المخصص
       │
       ▼
5. Live Observer (P3) يرسل trace + state إلى Control Layer
       │
       ▼
6. Drift Suppression Engine + Stability Monitor +
   Cognitive Rate Limiter → كل واحد يقيّم بشكل مستقل
       │
       ▼
7. Control Arbitration Logic يحل conflicts ← verdict موحد
       │
       ▼
8. إذا verdict = ALLOW → يكمل ضمن Budget
   إذا verdict = BLOCK / HALT → يوقف + يبلغ Governance
   إذا verdict = DOWNGRADE → يخفض Budget + يُحكم المراقبة
   إذا verdict = WARN → يكمل مع checkpoints إضافية
```

---

## Design Rules — قواعد التصميم

```
1. P4-A controllers هم read-only على P3 Observer — لا يكتبون إليه
2. P4-A controllers لا يمكنهم تعديل ENGINEERING_LAWS أو Doctrine Files
3. أي HALT أو BLOCK يسجل في Memory Recording كـ immutable record
4. Arbitration Logic هو deterministic — نفس input يعطي نفس output
5. أي controller عنده القدرة على escalation إلى Governance Layer
6. P4-A لا يمكن تخطيه — جميع executions تمر عبر Control Layer
7. أي تعديل في P4-A نفسها يحتاج ADR + موافقة Governance
```

---

## Interaction Matrix — مصفوفة التفاعل

| | Budget | Drift | Stability | Rate Limiter | Risk Dampening |
|---|---|---|---|---|---|
| **Budget** | — | Reads drift severity for tier adjustment | Reads stability score for elasticity | Reads throttle status | Reads smoothed risk |
| **Drift** | Can downgrade budget | — | Can signal stability | Independent | Independent |
| **Stability** | Can trigger HALT | Independent | — | Independent | Reads risk baseline |
| **Rate Limiter** | Reads budget for burst allowance | Independent | Independent | — | Reads system state |
| **Risk Dampening** | Feeds smoothed risk | Feeds smoothed risk baseline | Feeds risk baseline | Feeds system state | — |

---

*The Cognitive Control Layer is the executive command center of Stocky Engineering OS. All intelligence flows through it before reaching execution.*

*طبقة التحكم الإدراكي هي المركز التنفيذي للقيادة في النظام. جميع الذكاء يمر عبرها قبل الوصول إلى التنفيذ.*
