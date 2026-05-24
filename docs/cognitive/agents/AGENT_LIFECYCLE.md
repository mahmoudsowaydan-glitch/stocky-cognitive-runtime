# Stocky Engineering OS — Agent Lifecycle v0.1

---

> هذا الملف يحدد **دورة حياة الـ Agent** — كيف يتم التنشيط، التنفيذ، إلغاء التنشيط، والتعامل مع حالات الفشل.
>
> This file defines the **Agent Lifecycle** — how agents are activated, executed, deactivated, and how failures are handled.

---

## Core Lifecycle — دورة الحياة الأساسية

```
    ┌─────────────────────────────────────────────────────────────┐
    │                     AGENT LIFECYCLE                          │
    │                                                              │
    │  IDLE ──(trigger)──▶ ACTIVATED ──▶ WORKING ──▶ OUTPUT_READY  │
    │   ▲                        │            │         │         │
    │   │                        │            │         │         │
    │   │                        ▼            ▼         ▼         │
    │   │                    ┌────────┐  ┌────────┐  ┌────────┐  │
    │   │                    │TIMEOUT │  │ FAILED │  │VALIDATE│  │
    │   │                    └───┬────┘  └───┬────┘  └───┬────┘  │
    │   │                        │            │         │         │
    │   └────────────────────────┴────────────┴─────────┘         │
    │                                  │                          │
    │                                  ▼                          │
    │                            ┌──────────┐                     │
    │                            │ COMPLETED│                     │
    │                            └────┬─────┘                     │
    │                                 │                            │
    │                                 ▼                            │
    │                           (back to IDLE)                    │
    └─────────────────────────────────────────────────────────────┘
```

---

## Lifecycle States — حالات دورة الحياة

| State | الوصف | مسموح بالعمل؟ |
|---|---|---|
| **IDLE** | الـ Agent في حالة سكون — ينتظر trigger | لا |
| **ACTIVATED** | تم تنشيط الـ Agent — يحمّل السياق | لا (تحضير) |
| **WORKING** | الـ Agent يعمل — تحليل واستدلال | نعم (داخلي) |
| **WAITING** | ينتظر بيانات إضافية من Orchestrator | لا (انتظار) |
| **OUTPUT_READY** | الـ Agent أكمل التحليل — لديه output جاهز | لا |
| **VALIDATING** | Orchestrator يتحقق من صحة الـ output | لا |
| **COMPLETED** | اكتملت المهمة — output في Shared Memory | لا |
| **FAILED** | فشل الـ Agent أثناء العمل | لا |
| **TIMEOUT** | تجاوز الـ Agent الوقت المسموح | لا |

---

## State Transitions — انتقالات الحالة

| From | To | Trigger |
|---|---|---|
| IDLE | ACTIVATED | Trigger event من Orchestrator |
| ACTIVATED | WORKING | Context loaded and ready |
| ACTIVATED | FAILED | Context load failure |
| WORKING | OUTPUT_READY | Agent completes analysis |
| WORKING | WAITING | Agent needs more data from Orchestrator |
| WAITING | WORKING | Data received from Orchestrator |
| WAITING | TIMEOUT | No response within timeout |
| WORKING | FAILED | Internal error |
| WORKING | TIMEOUT | Exceeded max work duration |
| OUTPUT_READY | VALIDATING | Orchestrator starts validation |
| VALIDATING | COMPLETED | Validation passed |
| VALIDATING | FAILED | Validation failed + no retry |
| VALIDATING | WORKING | Validation failed + retry allowed |
| COMPLETED | IDLE | Automatic reset |
| FAILED | IDLE | Manual reset from Orchestrator |
| TIMEOUT | IDLE | Automatic reset after cool-down |

---

## Activation Flow — تدفق التنشيط

```
Trigger arrives at Orchestrator
    │
    ▼
1. Orchestrator checks agent availability (is agent IDLE?)
    │ If BUSY → queue the trigger
    ▼
2. Orchestrator creates activation context:
   - incident_id (if applicable)
   - execution_id (if applicable)
   - files_in_scope
   - current_system_state
   - relevant P5 lineage
    │
    ▼
3. Orchestrator sends ACTIVATE signal to agent
    │
    ▼
4. Agent transitions IDLE → ACTIVATED
    │
    ▼
5. Agent loads Private Working Memory with context
    │
    ▼
6. Agent transitions ACTIVATED → WORKING
```

---

## Timeout Policy — سياسة المهلة

| Agent | Max Work Time | Timeout Action |
|---|---|---|
| Architect | 30s | TIMEOUT + notify user |
| Runtime | 5s | TIMEOUT + alert P4 |
| Security | 10s | TIMEOUT + escalate to P4 |
| Debug | 20s | TIMEOUT + retry 1x |
| Optimization | 15s | TIMEOUT + skip optimization |
| QA | 60s | TIMEOUT + partial report |
| Research | 120s | TIMEOUT + return partial results |
| Coherence | 10s | TIMEOUT + use last known identity |
| System Integrity | 10s | TIMEOUT + skip integrity check |

---

## Retry Policy — سياسة إعادة المحاولة

| Agent | Max Retries | Backoff |
|---|---|---|
| Architect | 1 | 2s |
| Runtime | 0 | N/A (must be fast) |
| Security | 0 | N/A (must be fast) |
| Debug | 2 | 1s, 5s |
| Optimization | 1 | 3s |
| QA | 1 | 5s |
| Research | 0 | N/A (return partial) |
| Coherence | 1 | 2s |
| System Integrity | 2 | 1s, 3s |

---

## Agent Output Readiness

```
عندما Agent يصل إلى OUTPUT_READY:
  1. الـ Agent يجمّع outputه في format محدد
  2. الـ Orchestrator يستلم الـ output
  3. Orchestrator يبدأ VALIDATING:
     a. P2 Law check
     b. P4 Constraint check
     c. P5 Identity notification
  4. إذا ALLOW → يكتب في Shared Output Memory
     → الـ Agent ينتقل إلى COMPLETED
  5. إذا BLOCK → يكتب مع BLOCK status
     → الـ Agent ينتقل إلى FAILED
     → Source agent يُبلّغ
```

---

## Failure Handling — التعامل مع الفشل

| Failure | Action | Recovery |
|---|---|---|
| Agent internal error | تسجيل في Memory + FAILED | Manual reset from Orchestrator |
| Validation BLOCK | تسجيل + إبلاغ Agent + FAILED | Agent يمكنه تقديم بديل |
| Timeout | TIMEOUT + إبلاغ Orchestrator | Automatic reset after cool-down |
| Contradiction detected | تسجيل + إبلاغ P4 | P4 يقرر + إبلاغ Agent |
| Resource exhaustion | FAILED + إبلاغ Optimization Agent | تحسين الموارد + retry |

---

## Agent Health Monitoring

| Metric | Monitored By | Threshold |
|---|---|---|
| Success rate | Orchestrator | < 80% → alert |
| Avg response time | Orchestrator | > 2x baseline → alert |
| Failure frequency | Orchestrator | > 3 failures/h → pause agent |
| Contradiction rate | System Integrity Agent | > 20% → recalibrate |

---

*The Agent Lifecycle ensures that every cognitive agent has a clear start, a bounded execution window, a validated output, and a clean completion or failure path.*

*دورة حياة الـ Agent تضمن أن كل Agent إدراكي له بداية واضحة، نافذة تنفيذ محدودة، output مُتحقق منه، ومسار اكتمال أو فشل نظيف.*
