from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass
class AuditEvent:
    layer: str
    event_type: str
    entity_id: str
    payload: Dict[str, Any]
    timestamp: datetime
    correlation_id: str
