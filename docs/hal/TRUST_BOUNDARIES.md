# Trust Boundaries — تصنيف حدود الثقة للمضيف

HAL يجب أن يصنف المضيفين بناءً على مستوى الثقة لأن السياسات (P4) تعتمد على ذلك.

Suggested Trust Levels:

- `HIGH` — Local editor (e.g., VSCode desktop with known extensions)
- `MEDIUM` — Remote IDE with authenticated user/session (e.g., Codespaces)
- `LOW` — Cloud agent or ephemeral notebook kernel
- `RESTRICTED` — Unknown host, unverified plugin, or third-party integration

Mapping example:

```
HostTrust:
  host_id: string
  trust_level: HIGH|MEDIUM|LOW|RESTRICTED
  rationale: string
  evaluated_at: iso8601
```

Governance integration:

- P4 Decision = f(intent_confidence, trust_level, capability, risk)
- Example rule: if trust_level <= LOW and intent requests `process_control` then BLOCK unless manual approval.
