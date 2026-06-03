"""
recovery — Runtime Persistence & Recovery Layer (Phase 8).

Provides crash-survivable runtime with:
  - Periodic checkpoints (RuntimeState + traces + sub-system state)
  - Crash detection (unclean shutdown, orphan traces, partial execution)
  - Deterministic replay validation (causal integrity, trace equivalence)
  - Recovery orchestration (snapshot restore → queue rebuild → replay validate)
  - Persistence guard (schema version, frozen contract compatibility)

Invariants:
  1. Recovery ≠ Re-execution — no side-effect replay without causal verification
  2. Replay is deterministic — same traces produce same causal truth
  3. No authority mutation — recovery never changes P4 decisions or contracts
  4. WAL is source of truth — SQLite WAL + traces are the final reference
"""

from .recovery_report import RecoveryReport
from .runtime_snapshot import RuntimeSnapshot
from .crash_detector import CrashDetector, CrashIndicator
from .checkpoint_manager import CheckpointManager, CheckpointMetadata
from .delta_checkpoint import DeltaCheckpointManager, DeltaSegment, CheckpointBaseMeta
from .persistence_guard import PersistenceGuard, PersistenceValidation
from .replay_validator import ReplayValidator, ReplayValidation
from .recovery_coordinator import RecoveryCoordinator
