# Host Capability Model — نموذج قدرات المضيف

HAL يجب أن يعرف ما الذي يمكن أن يقدمه المضيف فعليًا قبل طلب تنفيذ أي إجراء.

Capability set (suggested):

- `file_edit` — تعديل الملفات والكتابة إلى القرص
- `terminal_access` — فتح وتشغيل أوامر في طرفية
- `diagnostics_stream` — بث رسائل تشخيص (lint, errors)
- `workspace_snapshot` — إنشاء لقطات شاملة للمشروع
- `process_control` — بدء/إيقاف عمليات محلية
- `live_selection_tracking` — تتبع تبدلات التحديد والحركات الحية
- `multi_cursor` — دعم تحرير متعدد المؤشرات
- `headless_mode` — دعم العمل بدون واجهة عرض

Representation example:

```
HostCapabilities:
  host_id: string
  timestamp: iso8601
  capabilities: { file_edit: true, terminal_access: false, ... }
  declared_limits: { max_files_snapshot: 1000 }
```

Adapters يجب أن تعلن قدرات المضيف أثناء الاتصال أو عند تغيير الحالة.
