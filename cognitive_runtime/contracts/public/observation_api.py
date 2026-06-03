from typing import Optional, Protocol

from .dtos import HealthDTO, PaginatedTracesDTO, PublicTraceDTO


class ObservationAPI(Protocol):
    def get_trace_by_id(self, event_id: str) -> Optional[PublicTraceDTO]:
        ...

    def list_traces(self, session_id: str, limit: int = 50, cursor: Optional[str] = None) -> PaginatedTracesDTO:
        ...

    def get_health(self) -> HealthDTO:
        ...
