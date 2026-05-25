# Host Event Model — نموذج حدث المضيف

هذا الملف يحدد بنية `HostEvent` ونماذج الأحداث العامة التي تُنتجها Adapters قبل دخول HAL.

Core HostEvent fields:

- `id: string` (UUID)
- `source: Enum[IDE|CLI|HEADLESS|REMOTE|PLUGIN]`
- `type: string` (e.g. `file_opened`, `file_changed`, `command_invoked`)
- `payload: dict` (مفتاح/قيمة عامة)
- `timestamp: iso8601`
- `session_id: string` (مرجع لحالة الجلسة في HAL)
- `capabilities_snapshot: dict` (نسخة من قدرات المضيف عند توليد الحدث)

Event categories (non-exhaustive):
- `document` (open, close, save, change)
- `selection` (cursor_move, selection_changed)
- `command` (command_invoked, command_chain_start, command_chain_continue)
- `focus` (focus_in, focus_out)
- `system` (connectivity, host_capability_update)

Adapters مسؤولون عن إنتاج `HostEvent` موحَّد، وليس عن ترجمة مباشرة إلى أحداث معرفية نهائية.
