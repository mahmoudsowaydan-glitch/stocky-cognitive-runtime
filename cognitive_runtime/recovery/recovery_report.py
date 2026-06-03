"""
recovery_report.py — Canonical recovery report dataclass.

Frozen contract. Schema matches FROZEN_SCHEMA_VERSION.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION_STR


@dataclass
class RecoveryReport:
    success: bool
    recovery_mode: str  # "clean_start" | "crash_recovery" | "checkpoint_restore"

    # Cycles
    total_cycles_requested: int = 0
    restored_cycles: int = 0
    skipped_cycles: int = 0

    # Replay
    replay_valid: bool = True
    replay_divergence_count: int = 0
    replay_divergences: List[Dict[str, Any]] = field(default_factory=list)

    # Corruption
    corruption_detected: bool = False
    corruption_details: List[str] = field(default_factory=list)

    # Orphans
    orphan_events_found: int = 0
    orphan_events_recovered: int = 0
    orphan_events: List[str] = field(default_factory=list)

    # Checkpoints
    checkpoint_restored: Optional[str] = None
    checkpoint_count: int = 0
    latest_checkpoint_cycle: int = 0

    # Timing
    recovery_started_at: float = 0.0
    recovery_completed_at: float = 0.0
    recovery_duration_ms: float = 0.0

    # State
    final_state_status: str = "stopped"
    final_health_status: str = "healthy"
    final_trace_count: int = 0

    # Schema
    schema_version: str = FROZEN_SCHEMA_VERSION_STR
    contract_violations_during_recovery: int = 0

    def snapshot(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "recovery_mode": self.recovery_mode,
            "restored_cycles": self.restored_cycles,
            "replay_valid": self.replay_valid,
            "corruption_detected": self.corruption_detected,
            "orphan_events_found": self.orphan_events_found,
            "checkpoint_restored": self.checkpoint_restored,
            "recovery_duration_ms": round(self.recovery_duration_ms, 2),
            "final_health_status": self.final_health_status,
            "final_trace_count": self.final_trace_count,
            "schema_version": self.schema_version,
        }
