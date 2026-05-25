# Runtime Binding Rules — قواعد ربط HAL بالـ Cognitive Runtime

قواعد أساسية للحفاظ على الاستقلالية وعدم الانغماس بالـ Host:

1. Runtime يجب أن يتلقى فقط Normalized Cognitive Events وIntentHypotheses.
2. لا يسمح بمرور أي Host-specific payload إلى Runtime دون التحقق والتحويل.
3. أي طلب تنفيذ من Runtime إلى المضيف يجب أن يمر عبر HAL ويفحص بالـ `HostCapabilities` و`TrustLevel`.
4. HAL لا ينفذ سياسات P2/P4؛ هي تزود المعلومات اللازمة لاتخاذ القرار.
5. يجب أن تكون واجهات الاتصال versioned ومُعلن عنها في `ADAPTER_CONTRACT.md`.

Example binding flow:

```
1. Adapter -> HostEvent -> HAL
2. HAL updates Session State, produces IntentHypothesis[]
3. HAL emits CognitiveEvent -> Runtime
4. Runtime requests action -> HAL (check capabilities + trust) -> Adapter.perform_action
```
