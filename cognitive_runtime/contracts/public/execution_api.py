from typing import List, Optional, Protocol

from .dtos import (
    EventStatusDTO,
    PublicTraceDTO,
    ReceiptDTO,
    SubmitEventDTO,
)


class ExecutionAPI(Protocol):
    def submit_event(self, dto: SubmitEventDTO) -> ReceiptDTO:
        ...

    def get_status(self, receipt_id: str) -> Optional[EventStatusDTO]:
        ...

    def get_result(self, receipt_id: str) -> Optional[PublicTraceDTO]:
        ...

    def await_result(self, receipt_id: str, timeout: Optional[float] = None) -> Optional[PublicTraceDTO]:
        ...

    def get_capabilities(self) -> List[str]:
        ...
