from cognitive_runtime.adapters.opencode.editor_event import (
    EditorEvent,
    EditorEventType,
)


class TestEditorEventType:
    def test_enum_values(self):
        assert EditorEventType.REPOSITORY_OPENED == "repository_opened"
        assert EditorEventType.FILE_OPENED == "file_opened"
        assert EditorEventType.FILE_CLOSED == "file_closed"
        assert EditorEventType.FILE_SAVED == "file_saved"
        assert EditorEventType.SELECTION_CHANGED == "selection_changed"
        assert EditorEventType.BRANCH_SWITCHED == "branch_switched"

    def test_no_cursor_moved_event(self):
        assert not hasattr(EditorEventType, "CURSOR_MOVED")


class TestEditorEvent:
    def test_default_construction(self):
        e = EditorEvent()
        assert e.event_type == ""
        assert e.file_path == ""
        assert e.metadata == {}

    def test_frozen_immutable(self):
        import dataclasses
        e = EditorEvent()
        assert dataclasses.is_dataclass(e)
        assert e.__dataclass_params__.frozen

    def test_to_submit_dto_repository_opened(self):
        event = EditorEvent(
            event_type=EditorEventType.REPOSITORY_OPENED,
            file_path="/repo",
        )
        dto = event.to_submit_event_dto(session_id="test")
        assert dto.session_id == "test"
        assert dto.source == "opencode_adapter"
        assert dto.payload["action"] == "analyze"
        assert dto.payload["target"] == "/repo"
        assert (
            dto.payload["editor_event_type"]
            == "repository_opened"
        )

    def test_to_submit_dto_file_opened(self):
        event = EditorEvent(
            event_type=EditorEventType.FILE_OPENED,
            file_path="/repo/main.py",
        )
        dto = event.to_submit_event_dto()
        assert dto.payload["action"] == "analyze"
        assert dto.payload["target"] == "/repo/main.py"

    def test_to_submit_dto_file_saved(self):
        event = EditorEvent(
            event_type=EditorEventType.FILE_SAVED,
            file_path="/repo/main.py",
        )
        dto = event.to_submit_event_dto()
        assert dto.payload["action"] == "analyze"

    def test_to_submit_dto_selection_changed(self):
        event = EditorEvent(
            event_type=EditorEventType.SELECTION_CHANGED,
            file_path="/repo/main.py",
        )
        dto = event.to_submit_event_dto()
        assert dto.payload["action"] == "search"

    def test_to_submit_dto_file_closed(self):
        event = EditorEvent(
            event_type=EditorEventType.FILE_CLOSED,
            file_path="/repo/main.py",
        )
        dto = event.to_submit_event_dto()
        assert dto.payload["action"] == "analyze"

    def test_to_submit_dto_branch_switched(self):
        event = EditorEvent(
            event_type=EditorEventType.BRANCH_SWITCHED,
            file_path="/repo",
        )
        dto = event.to_submit_event_dto()
        assert dto.payload["action"] == "analyze"

    def test_submit_dto_contains_metadata(self):
        event = EditorEvent(
            event_type=EditorEventType.FILE_OPENED,
            file_path="/repo/main.py",
            metadata={"language": "python"},
        )
        dto = event.to_submit_event_dto()
        assert dto.payload["language"] == "python"

    def test_string_event_type_resolves(self):
        event = EditorEvent(
            event_type="file_opened",
            file_path="/repo/main.py",
        )
        dto = event.to_submit_event_dto()
        assert dto.payload["action"] == "analyze"
