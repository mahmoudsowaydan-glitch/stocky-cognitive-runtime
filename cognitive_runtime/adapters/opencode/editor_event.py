import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from ...contracts.public.dtos import SubmitEventDTO


class EditorEventType(str, Enum):
    FILE_OPENED = "file_opened"
    FILE_CLOSED = "file_closed"
    FILE_SAVED = "file_saved"
    SELECTION_CHANGED = "selection_changed"
    BRANCH_SWITCHED = "branch_switched"
    REPOSITORY_OPENED = "repository_opened"


_ACTION_MAP = {
    EditorEventType.REPOSITORY_OPENED: "analyze",
    EditorEventType.FILE_OPENED: "analyze",
    EditorEventType.FILE_SAVED: "analyze",
    EditorEventType.FILE_CLOSED: "analyze",
    EditorEventType.BRANCH_SWITCHED: "analyze",
    EditorEventType.SELECTION_CHANGED: "search",
}


@dataclass(frozen=True)
class EditorEvent:
    event_type: str = ""
    file_path: str = ""
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_submit_event_dto(self, session_id: str = "opencode") -> SubmitEventDTO:
        ts = self.timestamp or time.time()
        action = _ACTION_MAP.get(self._resolve_type(), "analyze")
        return SubmitEventDTO(
            session_id=session_id,
            source="opencode_adapter",
            payload={
                "action": action,
                "target": self.file_path,
                "editor_event_type": self.event_type,
                **self.metadata,
            },
        )

    def _resolve_type(self) -> EditorEventType:
        if isinstance(self.event_type, EditorEventType):
            return self.event_type
        try:
            return EditorEventType(self.event_type)
        except ValueError:
            return EditorEventType.FILE_OPENED
