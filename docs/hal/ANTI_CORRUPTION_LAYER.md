# Anti-Corruption Layer — حاجز مناعة ضد فساد المصطلحات

الهدف: منع تسرب مصطلحات وسلوكيات المضيف الخاصة إلى Cognitive Runtime.

مستويات التحويل:

1. Host Concepts (مفردات المضيف الخاصة)
2. Normalized Host Concepts (نموذج HID — Host Independent Definitions)
3. Cognitive Concepts (نماذج النظام المعرفي)

الخطوات:

- Adapter يحول إشارات محلية إلى Host Concepts.
- HAL Runtime يُطبّع Host Concepts إلى Normalized Host Concepts عبر قواعد ترجمة ورزم تحويل.
- Normalized Concepts تُستخدم لإنتاج `IntentHypothesis[]` و`HostEvent` المعرفة.

Principles:

- Explicit mapping tables, not ad-hoc code.
- Versioned translators to support host evolution.
- Tests for semantic equivalence across adapters.
