"""evolution_node.py — SchemaVersionNode represents one version in the evolution graph.

Each node tracks:
  - version string
  - parent lineage (direct ancestors)
  - frozen status
  - breaking changes introduced
  - compatibility hash
"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class SchemaVersionNode:
    version: str
    parent_versions: Tuple[str, ...] = field(default_factory=tuple)
    is_frozen: bool = True
    breaking_changes: Tuple[str, ...] = field(default_factory=tuple)
    compatibility_hash: str = ""
