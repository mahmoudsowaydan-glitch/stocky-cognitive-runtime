# Intent Reconstruction — إعادة بناء النية (Probabilistic)

HAL لا تنتج نية واحدة قطعية. بدلاً من ذلك تُنتج قائمة `IntentHypothesis[]` مرتبة حسب الثقة.

IntentHypothesis structure:

- `id: string`
- `intent_type: Enum[edit|review|refactor|analyze|compare|debug|other]`
- `confidence: float`  # 0.0 - 1.0
- `supporting_signals: list[HostEvent references]`
- `competing_hypotheses: list[id]`
- `created_at`, `updated_at`

Pipeline notes:

1. Collect supporting signals from `HAL Session State` and recent `HostEvent`s.
2. Run probabilistic inference (weights, heuristics, ML model optionally) to produce hypotheses.
3. Emit `IntentHypothesis[]` to `Cognitive Runtime` with confidence for P2/P4 to evaluate.

Integration:

- P2 reasoning may request further probes (e.g., ask user clarifying question) to disambiguate high-impact intents.
- P4 uses confidence + trust boundary to decide whether to allow actions.
