# HAL Session State — حالة جلسة HAL

HAL يحتفظ بحالة جلسة مؤقتة تمثل التفاعل المتطور بين المضيف والمستخدم. هذه الحالة تفسيرية، عابرة، وليست ذاكرة دائمة للنظام.

Suggested fields:

- `session_id: string`
- `host_id: string`
- `open_documents: list[{path, cursor_positions, dirty}]`
- `focus_history: list[{editor, timestamp}]`
- `command_chain: list[{command, args, timestamp}]`
- `selection_history: list[{range, timestamp}]`
- `partial_edits_buffer: dict[filepath -> content_snippet]`
- `last_intent_hypotheses: list[IntentHypothesis]`
- `capabilities_snapshot: HostCapabilities`
- `created_at`, `updated_at`

Lifecycle

- create_session(host_id)
- update_on_host_event(host_event)
- expire_session(timeout)
- snapshot_for_runtime()  # produce minimal context for an invocation

HAL Session State يجب أن يبقى محليًا في الـ HAL ولا يكتب مباشرة إلى الـ P3 memory إلا كمؤشرات غير قابلة للتغيير عند الحاجة (مثلاً HALT records).
