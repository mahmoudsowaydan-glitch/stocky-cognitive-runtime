"""schema_sync_protocol.py — Communication contract between distributed nodes.

Defines handshake and response dataclasses for schema negotiation.
No runtime state, no HAL dependency.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class SchemaHandshake:
    node_id: str
    schema_version: str
    supported_versions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SchemaSyncResponse:
    status: str  # ACCEPT | MIGRATE | REJECT
    target_version: Optional[str] = None
    migration_required: bool = False
    reason: str = ""
