# Stocky Engineering OS — Controlled Agents Layer Overview v0.1

---

> هذا الملف هو **الخريطة الرئيسية لـ P5-A Controlled Agents Layer** — طبقة تحليل الذكاء إلى أدوار متخصصة تحت حوكمة واحدة.
>
> This file is the **master map of P5-A Controlled Agents Layer** — the decomposition of intelligence into specialized roles under single governance.

---

## Core Philosophy — الفلسفة الأساسية

```
Agents do NOT decide.
Agents do NOT communicate freely.
Agents only propose.
P4 decides. P2 constrains. P5 validates identity.

الـ Agents لا يقررون.
الـ Agents لا يتواصلون بحرية.
الـ Agents فقط يقترحون.
P4 يقرر. P2 يحدد. P5 يتحقق من الهوية.
```

---

## Architecture Map — خريطة البنية

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       CONTROLLED AGENTS LAYER (P5-A)                     │
│                                                                           │
│  ┌────────────── ALWAYS-ON SENSORS ──────────────┐                      │
│  │  Runtime Monitor · Drift Hook · Budget Watch  │                      │
│  │  (embedded in P3/P4 loop — lightweight)       │                      │
│  └──────────────────────┬────────────────────────┘                      │
│                          │                                                │
│  ┌──────────────────────▼────────────────────────┐                      │
│  │          CENTRAL COGNITIVE ORCHESTRATOR        │                      │
│  │  · Routes events to appropriate agents         │                      │
│  │  · Enforces P4 constraints                     │                      │
│  │  · Validates outputs against P2 laws           │                      │
│  │  · Logs everything into P3 memory              │                      │
│  │  · No direct agent-to-agent communication      │                      │
│  └──────┬─────────────────────────────────┬───────┘                      │
│          │                                 │                                │
│  ┌───────▼────────┐            ┌──────────▼────────┐                     │
│  │  EVENT-TRIGGERED│            │   ON-DEMAND       │                     │
│  │  AGENTS        │            │   AGENTS          │                     │
│  │                 │            │                    │                     │
│  │  Debug Agent    │            │  Architect Agent  │                     │
│  │  Security Agent │            │  Research Agent   │                     │
│  │  Runtime Agent  │            │  QA Deep Agent    │                     │
│  │  Optimization   │            │  Coherence Agent  │                     │
│  │  SystemIntegrity│            │                    │                     │
│  └─────────────────┘            └────────────────────┘                     │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                    AGENT MEMORY MODEL                             │    │
│  │  · Private Working Memory  (isolated per agent)                   │    │
│  │  · Shared Output Memory    (P3 append-only)                       │    │
│  │  · Global Lineage          (P5 read-only)                         │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                │                        │
                ▼                        ▼
    ┌───────────────────┐    ┌──────────────────────┐
    │  CONSTRAINED BY   │    │  VALIDATED BY        │
    │  P2 (Doctrine)    │    │  P5 (Identity)       │
    │  P4 (Control)     │    │  P3 (Memory Records) │
    └───────────────────┘    └──────────────────────┘
```

---

## 3-Tier Activation Model — نموذج التنشيط ثلاثي المستويات

### Tier 1: Always-on Sensors (في P3/P4 loop)
| Sensor | المسؤولية | Activation |
|---|---|---|
| Runtime Monitor | يراقب الـ State Machine والـ execution | دائم |
| Drift Hook | يلتقط إشارات Drift Suppression | دائم |
| Budget Watch | يراقب استهلاك الـ Budget | دائم |
| Observer Relay | يمرر الـ Trace Events إلى Orchestrator | دائم |

### Tier 2: Event-Triggered Agents (عند thresholds)
| Agent | Trigger | الـ Threshold |
|---|---|---|
| Debug Agent | Failure أو Anomaly | أي EXECUTION_ERROR أو POSTCONDITION_FAILED |
| Security Agent | Violation من Laws SL-01 إلى SL-05 | أي Security Law Violation |
| Runtime Agent | State غير متوقع | State inconsistency أو Lifecycle leak |
| Optimization Agent | Resource استخدام مرتفع | Memory > 70% أو CPU > 80% |
| System Integrity Agent | Contradiction بين Agents | أي CROSS_AGENT_CONTRADICTION |

### Tier 3: On-Demand Deep Agents (عند الطلب)
| Agent | الـ Trigger | Activation |
|---|---|---|
| Architect Agent | User request أو Major architectural event | Manual أو Governance request |
| Research Agent | New technology أو Unknown pattern | Manual |
| QA Deep Agent | Pre-release أو Major refactor | Manual |
| Coherence Agent | Identity check أو Periodic review | Manual أو كل 24h |

---

## Communication Model — نموذج التواصل

### Golden Rule
```
❌ No agent-to-agent direct communication
✅ All communication goes through Central Orchestrator
```

### Communication Flow
```
Agent A → proposal → Orchestrator → validates → P4 approves → routes to Agent B
                                                                       │
                                                                       ▼
                                                               Agent B reads from
                                                               Shared Output Memory
```

---

## Conflict Resolution — حل النزاعات

### Agents Propose, P4 Decides
```
Agent A says:  "Extract interface (architectural purity)"
Agent B says:  "Keep monolithic (security simplicity)"
    │
    ▼
Orchestrator sends both proposals to P4 Control Plane
    │
    ▼
P4 evaluates against:
  - P2 Laws (which proposal is more compliant?)
  - Risk Score (which has lower risk?)
  - Stability Impact (which destabilizes less?)
    │
    ▼
P4 decides → result logged in Shared Output Memory
```

### Authority Stack
```
Priority 1: P4 Control Plane (decides)
Priority 2: P2 Doctrine (constrains)
Priority 3: P5 Identity (validates)
Priority 4: P5-A Agents (propose)
Priority 5: P3 Runtime (executes)
```

---

## Agent Memory Model Summary

| Memory Type | الوصول | Storage | visibility |
|---|---|---|---|
| **Private Working Memory** | Agent only | Isolated per agent | Hidden |
| **Shared Output Memory** | All agents + P3 | P3 append-only | Public |
| **Global Lineage** | Read-only for all | P5 Decision Graph | Public |

---

## The 9 Agents (Summary)

| Agent | Tier | Domain | Authority |
|---|---|---|---|
| Architect | On-demand | Structure, layers, dependencies | Propose |
| Runtime | Event-triggered | Lifecycle, state, memory | Monitor, Alert |
| Security | Event-triggered | Safety laws, threats | Alert, Block-suggest |
| Debug | Event-triggered | Failure analysis, root cause | Analyze, Propose |
| Optimization | Event-triggered | Performance, memory | Analyze, Recommend |
| QA | On-demand | Testing, validation | Verify, Report |
| Research | On-demand | External knowledge, patterns | Inform, Suggest |
| Coherence | On-demand | Identity interface with P5 | Translate, Monitor |
| System Integrity | Event-triggered | Cross-agent consistency | Validate, Alert |

---

*The Controlled Agents Layer transforms Stocky Engineering OS from a single cognitive mind into a governed society of specialized intelligences — all operating under a single authority kernel.*

*طبقة الـ Agents المتحكم فيهم تحول النظام من عقل إدراكي واحد إلى مجتمع محكوم من الذكاءات المتخصصة — كلها تعمل تحت نواة سلطة واحدة.*
