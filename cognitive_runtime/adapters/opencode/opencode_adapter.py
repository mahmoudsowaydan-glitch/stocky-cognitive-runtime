import time
from typing import Optional

from ...runtime.gateway.local_runtime_gateway import LocalRuntimeGateway
from ...contracts.public.dtos import ReceiptDTO, PublicTraceDTO, EventStatusDTO
from .workspace_snapshot import WorkspaceSnapshot
from .editor_event import EditorEvent, EditorEventType


class OpenCodeAdapter:
    def __init__(
        self,
        gateway: LocalRuntimeGateway,
        session_id: str = "opencode",
    ):
        self._gateway = gateway
        self._session_id = session_id

    def capture_workspace(
        self,
        root_path: str,
        open_files: tuple = (),
        selected_file: str = "",
        cursor_line: int = 0,
        cursor_column: int = 0,
    ) -> WorkspaceSnapshot:
        return WorkspaceSnapshot.capture(
            root_path=root_path,
            open_files=open_files,
            selected_file=selected_file,
            cursor_line=cursor_line,
            cursor_column=cursor_column,
        )

    def submit_editor_event(self, event: EditorEvent) -> ReceiptDTO:
        dto = event.to_submit_event_dto(self._session_id)
        return self._gateway.submit_event(dto)

    def submit_analyze(self, target_path: str) -> ReceiptDTO:
        event = EditorEvent(
            event_type=EditorEventType.REPOSITORY_OPENED,
            file_path=target_path,
        )
        return self.submit_editor_event(event)

    def submit_search(
        self, target_path: str, pattern: str = "*"
    ) -> ReceiptDTO:
        event = EditorEvent(
            event_type=EditorEventType.SELECTION_CHANGED,
            file_path=target_path,
            metadata={"pattern": pattern},
        )
        return self.submit_editor_event(event)

    def get_result(self, receipt_id: str) -> Optional[PublicTraceDTO]:
        return self._gateway.get_result(receipt_id)

    def get_status(self, receipt_id: str) -> Optional[EventStatusDTO]:
        return self._gateway.get_status(receipt_id)

    def poll_result(
        self,
        receipt_id: str,
        max_attempts: int = 50,
    ) -> Optional[PublicTraceDTO]:
        for _ in range(max_attempts):
            result = self._gateway.get_result(receipt_id)
            if result is not None and result.event_id:
                return result
            time.sleep(0.1)
        return None
