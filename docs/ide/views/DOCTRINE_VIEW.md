# Stocky Engineering OS — Doctrine View v0.1

---

> هذا الملف يحدد **Doctrine View** — view P2 في طائرة الإدراك: عرض الـ Manifest، القوانين، الأحداث، والمفردات الرسمية.
>
> This file defines the **Doctrine View** — the P2 view in the Cognition Plane: displaying the Manifest, Laws, Events, and Vocabulary.

---

## Core Content — المحتوى الأساسي

| العنصر | المصدر |
|---|---|
| Manifest (full text) | STOCKY_MANIFEST.md |
| Engineering Laws (all) | ENGINEERING_LAWS.md |
| Engineering Events (types) | ENGINEERING_EVENTS.md |
| System Vocabulary | SYSTEM_VOCABULARY.md |
| Law enforcement stats | P3 Memory (incidents per law) |

---

## Doctrine Overview

### Web Dashboard
```
┌──────────────────────────────────────────────────────────────────────────┐
│  📜 ENGINEERING DOCTRINE                                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────── System Identity ─────────────────────────────────────┐    │
│  │  Stocky Engineering OS — v1.0 Kernel                             │    │
│  │  "An AI-native engineering operating system"                     │    │
│  │  Status: ● ACTIVE  │  Commits: 5  │  Files: 22                  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌─── 23 Engineering Laws ──────────────────────────────────────────┐    │
│  │  ┌──────────┬────────┬───────────┬──────────┐                    │    │
│  │  │ Category │ Count  │ Compliant │ Violated │                    │    │
│  │  ├──────────┼────────┼───────────┼──────────┤                    │    │
│  │  │ 🏛 Arch  │ 5      │ 98%       │ 2 this h │ ← click for       │    │
│  │  │ 🔗 Dep   │ 4      │ 97%       │ 1 this h │   incidents       │    │
│  │  │ ⚡ Runtime│ 5      │ 100%      │ 0        │                    │    │
│  │  │ 🧠 Cog   │ 4      │ 100%      │ 0        │                    │    │
│  │  │ 🛡 Safety│ 5      │ 100%      │ 0        │                    │    │
│  │  └──────────┴────────┴───────────┴──────────┘                    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌─── 11 Event Types ───────────────────────────────────────────────┐    │
│  │  COMPILE_FAILURE │ RUNTIME_ANOMALY │ ARCHITECTURE_VIOLATION     │    │
│  │  DEPENDENCY_DRIFT│ STATE_CORRUPTION│ SYNC_INTEGRITY_RISK        │    │
│  │  MEMORY_PRESSURE │ LIFECYCLE_LEAK  │ UNSAFE_EXECUTION_INTENT    │    │
│  │  TELEMETRY_BLIND │ CONTRACT_VIOLATION                            │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Law Detail View

### Web Dashboard (click a Law)
```
┌──────────────────────────────────────────────────────────────────────────┐
│  🏛 AL-01: Domain Independence from Runtime                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Rule:                                                                   │
│  Domain layer cannot depend on runtime layer.                            │
│                                                                           │
│  Risk: CRITICAL  │  Enforcement: Static Analysis                         │
│                                                                           │
│  ┌── Compliance Stats (24h) ────────────────────────────────────────┐   │
│  │  Checked: 200 behaviors  │  Compliant: 196  │  98%               │   │
│  │  Violations: 4                                                     │   │
│  │  ┌──────────┬──────────┬────────┬──────────┐                    │   │
│  │  │ Incident │ Module   │ Time   │ Status   │                    │   │
│  │  ├──────────┼──────────┼────────┼──────────┤                    │   │
│  │  │ inc-a3f1 │ auth     │ 14:30  │ ● ACTIVE │ ← click for full   │   │
│  │  │ inc-a3e9 │ payment  │ 13:15  │ ✓ RES    │   reasoning view   │   │
│  │  │ inc-a3e2 │ auth     │ 11:00  │ ✓ RES    │                    │   │
│  │  └──────────┴──────────┴────────┴──────────┘                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  Related Laws: DL-01 (Inward dependency), AL-04 (Contracts)              │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Event Type Detail View

### Web Dashboard (click an Event Type)
```
┌──────────────────────────────────────────────────────────────────────────┐
│  ⚡ ARCHITECTURE_VIOLATION                                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Definition: A boundary or contract break between layers                 │
│                                                                           │
│  Initial Severity: HIGH  │  Source: DRIFT_DETECTOR (typical)             │
│                                                                           │
│  ┌── Last 24h ──────────────────────────────────────────────────────┐   │
│  │  Incidents: 3  │  Resolved: 2  │  Active: 1                      │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │ Time     │ Incident │ Module   │ Severity │ Outcome     │    │   │
│  │  ├─────────┼──────────┼─────────┼──────────┼─────────────┤    │   │
│  │  │ 14:30   │ inc-a3f1 │ auth    │ CRITICAL │ ● Active    │    │   │
│  │  │ 13:15   │ inc-a3e9 │ payment │ HIGH     │ ✓ RolledBack│    │   │
│  │  │ 11:00   │ inc-a3e2 │ auth    │ MEDIUM   │ ✓ Resolved  │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  Related Laws: AL-01, AL-05, DL-01                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Vocabulary View

### CLI Display
```
┌──────────────────────────────────────────────────────────┐
│  📖 SYSTEM VOCABULARY  (10 canonical terms)              │
├──────────────────────────────────────────────────────────┤
│  Event       │  Raw observable signal                    │
│  Incident    │  Classified dangerous condition            │
│  Drift       │  Architectural deviation                   │
│  Leakage     │  Unintended state propagation              │
│  Violation   │  Broken engineering law                    │
│  Intent      │  Expected engineering objective            │
│  Cognition   │  Reasoning process                         │
│  Governance  │  Execution authority control               │
│  Confidence  │  Degree of classification certainty        │
│  Risk        │  Potential harm to system integrity        │
└──────────────────────────────────────────────────────────┘
```

### Web Vocabulary View
```
┌──────────────────────────────────────────────────────────────────────────┐
│  📖 SYSTEM VOCABULARY                                         [Search]  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Term:  Event                                                      │  │
│  │  Type:  Core Term                                                   │  │
│  │  Def:   Raw observable signal emitted by any system layer           │  │
│  │  Used:  Source, initial_severity, type, snapshot                    │  │
│  │  Related: Incident, Signal Intake (Layer 1)                         │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Term:  Incident                                                    │  │
│  │  Type:  Core Term                                                   │  │
│  │  Def:   Event that has passed through Classification + Risk         │  │
│  │  Used:  classification, reasoning_output, governance_verdict       │  │
│  │  Related: Event, Classification Engine (Layer 2)                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

| View Element | يقرأ من |
|---|---|
| Laws | ENGINEERING_LAWS.md (static) |
| Events | ENGINEERING_EVENTS.md (static) |
| Vocabulary | SYSTEM_VOCABULARY.md (static) |
| Law compliance | P3 Memory (incidents by law) |
| Event stats | P3 Memory (incidents by type) |

---

*The Doctrine View is the constitution display of Stocky Engineering OS. It shows the foundational rules that govern the system and their real-time enforcement status.*

*عرض المبادئ هو عرض الدستور للنظام. يُظهر القواعد التأسيسية التي تحكم النظام وحالة تطبيقها في الوقت الفعلي.*
