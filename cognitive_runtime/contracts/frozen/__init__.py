"""
frozen — Runtime Contract Freezing Layer (Phase 7.5).

Freezes canonical interfaces for:
  - CausalGraph / CausalNode / CausalEdge
  - ExecutionTrace
  - Bridge protocols (feedback_bridge, observation_tap)
  - Runtime lifecycle (state, orchestration, periodic tasks)

Prevents schema drift, bridge mismatch, and cross-layer coupling failures.
"""

from .schema_version import SchemaVersion, FROZEN_SCHEMA_VERSION
from .graph_contract import GraphContract
from .trace_contract import TraceContract
from .bridge_contract import BridgeContract
from .runtime_contract import RuntimeContract
from .compatibility_guard import CompatibilityGuard
