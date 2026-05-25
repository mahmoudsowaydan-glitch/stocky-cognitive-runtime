# Adapter Contract — عقد واجهة الـ Adapter

الـ Adapter هو المكوّن المضيف-خاص الذي يُنتج `HostEvent` و`HostCapabilities` ويستقبل أوامر قياسية محدودة من HAL.

التزامات Adapter:

1. إعلان `HostCapabilities` عند الاتصال وأي تغيير.
2. توليد `HostEvent` موحَّدة لكل حدث مضيف ذي معنى.
3. ربط/فصل آمن للجلسات مع `session_id`.
4. تنفيذ أوامر بسيطة إذا كانت مضمنة ضمن القدرات المصرح بها (مثال: `open_file(path)`, `apply_patch(patch)` ) ويجب أن يرفض أو يعيد خطأ إن كانت غير مدعومة.

محظورات (Forbidden):

- لا ترسل مفردات داخلية خاصة بالمحرر كأحداث إلى HAL (مثلاً: `monaco_internal_event`).
- لا تُدخل منطق قرار معماري أو سياسة داخل Adapter.

API surface (example):

```
Adapter.connect(host_metadata) -> HostCapabilities
Adapter.emit_event(raw_host_signal) -> HostEvent
Adapter.perform_action(action_name, action_payload) -> ActionResult
Adapter.get_session_snapshot(session_id) -> HAL Session Snapshot
Adapter.disconnect()
```
