# Stocky Engineering OS — Risk Dampening System v0.1

---

> هذا الملف يحدد **نظام تهدئة المخاطر** — المسؤول عن تنعيم إشارات المخاطر الخام، الحفاظ على Baseline ثابت، وتغذية باقي نظام التحكم ببيانات مخاطر مستقرة.
>
> This file defines the **Risk Dampening System** — responsible for smoothing raw risk signals, maintaining a stable baseline, and feeding the rest of the control system with stable risk data.

---

## Core Principle — المبدأ الأساسي

```
Raw risk signals are noisy.
Stable systems require smoothed risk data.

إشارات المخاطر الخام مليئة بالضوضاء.
الأنظمة المستقرة تحتاج بيانات مخاطر مُنعّمة.
```

The Risk Dampening System is the only **Inform-only** module in P4-A — it has no authority to block or halt. It exists purely to provide stable input to the other controllers.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   RISK DAMPENING SYSTEM                    │
│                                                            │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │              │   │              │   │              │  │
│  │ Raw Risk     │──▶│ Smoothing    │──▶│ Baseline     │  │
│  │ Intake       │   │ Engine       │   │ Manager      │  │
│  │              │   │              │   │              │  │
│  └──────────────┘   └──────────────┘   └──────┬───────┘  │
│                                                │          │
│                                                ▼          │
│  ┌──────────────────────────────────────────────────┐    │
│  │              Output Distribution                   │    │
│  │  → Budget System (smoothed_risk)                  │    │
│  │  → Stability Monitor (risk_baseline)              │    │
│  │  → Rate Limiter (risk_trend)                      │    │
│  │  → Drift Suppression (risk_context)               │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

---

## Raw Risk Intake — استقبال المخاطر الخام

### Sources
| Source | Signal Type | Frequency |
|---|---|---|
| Reasoning Engine (P2-L4) | risk_score per incident | Per event |
| Classification Engine (P2-L2) | initial_severity | Per event |
| Live Observer (P3) | anomaly signals | Variable |
| Drift Suppression (P4) | drift severity | On drift detection |
| Stability Monitor (P4) | stability_score | Every 60s |

### Raw Risk Data Structure
```yaml
RawRiskSignal:
  id: string
  timestamp: datetime
  source: Enum                  # REASONING | CLASSIFICATION | OBSERVER | DRIFT | STABILITY
  value: float                  # 0.0 - 1.0
  confidence: float             # 0.0 - 1.0
  context: string               # Brief description of what generated this signal
  incident_id: string|null      # Related incident (if any)
```

---

## Smoothing Engine — محرك التنعيم

### Algorithm: Exponential Moving Average (EMA)

```
smoothed_risk = α × raw_risk + (1 - α) × previous_smoothed_risk

حيث:
  α = smoothing_factor (0.1 - 0.5) يحدد بناءً على:
    - ثبات النظام (StabilityScore)
    - source الثقة (confidence)
    - معدل التغيير (rate of change)
```

### Adaptive Alpha Selection
| Condition | α | التأثير |
|---|---|---|
| StabilityScore > 0.8 (STABLE) | 0.1 | Smoothing عالي — يتجاهل الشذوذ الفردي |
| StabilityScore 0.5 - 0.8 | 0.2 | Smoothing معتدل |
| StabilityScore < 0.5 (UNSTABLE) | 0.3 | Smoothing منخفض — يستجيب بسرعة |
| Confidence > 0.8 (high certainty) | 0.3 | يثق في الـ raw signal |
| Confidence < 0.3 (low certainty) | 0.1 | يتجاهل الإشارات غير الموثوقة |
| Drift = HARD | 0.4 | استجابة سريعة للانحراف الحاد |
| Anomaly storm detected | 0.5 | استجابة فورية |

### Example
```
Raw signals: [0.3, 0.8, 0.2, 0.9, 0.3]
(طفرة مفاجئة ثم عودة — noise)

مع α = 0.1 (STABLE):
  Smoothed: [0.30, 0.33, 0.31, 0.35, 0.34]
  
مع α = 0.4 (UNSTABLE):
  Smoothed: [0.30, 0.50, 0.38, 0.59, 0.47]
```

---

## Baseline Manager — مدير خط الأساس

### Purpose
الحفاظ على **خط أساس ديناميكي** للمخاطر — الطبيعي للنظام في الظروف العادية.

### Baseline Calculation
```
baseline = percentile_50(smoothed_risk over last 24h)
         = المتوسط الطبيعي للمخاطر في التشغيل اليومي

baseline يَتحدّث كل ساعة
baseline يُخزّن في Memory (مع compress)
```

### Baseline States
| State | الوصف |
|---|---|
| **NORMAL** | smoothed_risk قريب من baseline (ضمن ±0.1) |
| **ELEVATED** | smoothed_risk > baseline + 0.2 |
| **SPIKING** | smoothed_risk > baseline + 0.4 |
| **CRITICAL** | smoothed_risk > 0.8 بغض النظر عن baseline |

### Deviation Detection
```
deviation = smoothed_risk - baseline

إذا deviation > 0.2:
    → إبلاغ Budget System (رفع Tier)
إذا deviation > 0.4:
    → إبلاغ Stability Monitor (CRITICAL)
إذا deviation ترتفع 3 مرات متتالية:
    → إبلاغ Drift Suppression (trend analysis)
```

---

## Output Distribution — توزيع المخرجات

| Recipient | What is sent | Format |
|---|---|---|
| **Budget System** | smoothed_risk + baseline + trend | `{ smoothed: float, baseline: float, trend: string }` |
| **Stability Monitor** | risk_baseline + deviation_level | `{ baseline: float, deviation: float, level: Enum }` |
| **Rate Limiter** | risk_trend (increasing/stable/decreasing) | `{ trend: string, magnitude: float }` |
| **Drift Suppression** | risk_context + anomaly_pattern | `{ recent_peaks: [float], pattern: string }` |

### Update Frequency
| Output | Frequency |
|---|---|
| smoothed_risk | بعد كل ريsk signal (real-time) |
| baseline | كل ساعة |
| trend | كل 5 دقائق |
| anomaly_pattern | عند اكتشاف peak |

---

## Risk Dampening Data Structure

```yaml
RiskDampeningState:
  current: {
    raw: float,                   # آخر raw signal
    smoothed: float,              # آخر smoothed value
    baseline: float,              # Current baseline
    deviation: float,             # Current deviation from baseline
    trend: Enum                   # STABLE | INCREASING | DECREASING | SPIKING
  }
  history: {
    signals_last_100: [float],    # Last 100 raw signals (circular buffer)
    smoothed_last_100: [float],   # Last 100 smoothed values
    hourly_baselines: [float]     # Last 24 baselines
  }
  parameters: {
    alpha: float,                 # Current smoothing factor
    baseline_period_hours: 24,    # Baseline calculation window
    deviation_threshold: 0.2      # Threshold for alert
  }
```

---

*The Risk Dampening System is the sensory stabilizer of Stocky Engineering OS. It ensures that the control system receives calm, stable data — not noisy, reactive signals.*

*نظام تهدئة المخاطر هو مثبت الحواس للنظام. يضمن أن نظام التحكم يستقبل بيانات هادئة ومستقرة — وليس إشارات مزعجة متفاعلة.*
