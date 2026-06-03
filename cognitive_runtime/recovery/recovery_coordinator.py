"""
recovery_coordinator.py — Orchestrates full crash recovery pipeline.

Steps:
   1. Detect crash (CrashDetector)
   2. Find last valid checkpoint (CheckpointManager)
   3. Validate snapshot compatibility (PersistenceGuard)
   4. Load snapshot into runtime (RuntimeSnapshot restore)
   5. Rebuild queue from remaining WAL events
   6. Validate replay determinism (ReplayValidator)
   7. Report recovery results (RecoveryReport)

Invariants (INV-REC-001):
  - Recovery MUST replace state, never re-execute side effects
  - _apply_snapshot only restores in-memory state (_traces, _state, score histories)
  - Event processing is blocked during recovery by runtime_loop._process_event guard
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.execution_trace import ExecutionTrace
from ..contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION
from ..contracts.frozen.compatibility_guard import CompatibilityGuard
from .recovery_report import RecoveryReport
from .runtime_snapshot import RuntimeSnapshot
from .crash_detector import CrashDetector, CrashIndicator
from .checkpoint_manager import CheckpointManager, CheckpointMetadata
from .persistence_guard import PersistenceGuard, PersistenceValidation
from .replay_validator import ReplayValidator, ReplayValidation


class RecoveryCoordinator:
    def __init__(self,
                 checkpoint_manager: CheckpointManager,
                 crash_detector: Optional[CrashDetector] = None,
                 persistence_guard: Optional[PersistenceGuard] = None,
                 replay_validator: Optional[ReplayValidator] = None,
                 compatibility_guard: Optional[CompatibilityGuard] = None,
                 schema_evolution_guard: Optional[Any] = None,
                 hal_observer: Optional[Any] = None):
        self._checkpoints = checkpoint_manager
        self._crash = crash_detector or CrashDetector()
        if persistence_guard is not None:
            self._persistence = persistence_guard
        else:
            self._persistence = PersistenceGuard(compatibility_guard, schema_evolution_guard)
        self._replay = replay_validator or ReplayValidator()
        self._guard = compatibility_guard or CompatibilityGuard()
        self._hal = hal_observer
        self._last_report: Optional[RecoveryReport] = None
        self._recovery_in_progress = False

    @property
    def last_report(self) -> Optional[RecoveryReport]:
        return self._last_report

    @property
    def recovery_in_progress(self) -> bool:
        return self._recovery_in_progress

    def recover(self, runtime_loop: Any) -> RecoveryReport:
        started_at = time.time()
        self._recovery_in_progress = True
        report = RecoveryReport(
            success=False,
            recovery_mode="clean_start",
            recovery_started_at=started_at,
            schema_version=str(FROZEN_SCHEMA_VERSION),
        )

        try:
            # Step 1: Detect crash
            indicator = self._crash.detect(runtime_loop)
            report.orphan_events_found = indicator.orphan_traces
            report.corruption_detected = indicator.unclean_shutdown
            report.corruption_details = [indicator.details] if indicator.unclean_shutdown else []

            if indicator.unclean_shutdown:
                report.recovery_mode = "crash_recovery"

            # Step 2: Find last checkpoint
            last_cp = self._checkpoints.latest
            if last_cp:
                report.checkpoint_restored = last_cp.checkpoint_id
                report.checkpoint_count = self._checkpoints.checkpoint_count
                report.latest_checkpoint_cycle = last_cp.cycle_count

            # Step 3: Validate snapshot compatibility
            snapshot = None
            if last_cp:
                snapshot = self._checkpoints.load_latest()
                if snapshot:
                    validation = self._persistence.validate_snapshot(snapshot)
                    if not validation.valid:
                        report.corruption_detected = True
                        report.corruption_details.extend(validation.contract_violations)
                        report.contract_violations_during_recovery += len(validation.contract_violations)
                        if self._hal:
                            self._hal({
                                "type": "recovery.snapshot_invalid",
                                "details": validation.details,
                                "schema_snapshot": validation.schema_snapshot,
                                "schema_current": validation.schema_current,
                            })

            # Step 4: Restore snapshot into runtime
            restored_count = 0
            if snapshot and hasattr(runtime_loop, "_traces") and hasattr(runtime_loop, "_state"):
                self._apply_snapshot(runtime_loop, snapshot)
                restored_count = snapshot.trace_count

            report.restored_cycles = restored_count
            report.skipped_cycles = max(0,
                (indicator.expected_trace_count - restored_count))

            # Step 5: Validate replay
            if hasattr(runtime_loop, "_traces") and runtime_loop._traces:
                replay_val = self._replay.validate(
                    snapshot or RuntimeSnapshot.capture(runtime_loop),
                    list(runtime_loop._traces),
                )
                report.replay_valid = replay_val.valid
                report.replay_divergence_count = replay_val.divergence_count
                report.replay_divergences = replay_val.divergences

            # Step 6: Contract verification post-recovery
            if hasattr(runtime_loop, "_contract_guard"):
                cr = runtime_loop._contract_guard.run_all(runtime_loop)
                if not cr["passed"]:
                    report.corruption_detected = True
                    for v in runtime_loop._contract_guard.violations:
                        report.corruption_details.append(
                            f"post-recovery: {v['component']}: {v['message']}"
                        )

        except Exception as e:
            report.corruption_detected = True
            report.corruption_details.append(f"recovery_error: {str(e)}")

        finally:
            report.recovery_completed_at = time.time()
            report.recovery_duration_ms = (time.time() - started_at) * 1000

            if hasattr(runtime_loop, "_state"):
                report.final_state_status = getattr(runtime_loop._state, "status", "stopped")
                report.final_health_status = getattr(runtime_loop._state, "health_status", "healthy")

            if hasattr(runtime_loop, "_traces"):
                report.final_trace_count = len(runtime_loop._traces)

            report.success = (not report.corruption_detected
                              and report.replay_valid
                              and report.contract_violations_during_recovery == 0)

            self._last_report = report
            self._recovery_in_progress = False

            if self._hal:
                self._hal({
                    "type": "recovery.report",
                    "data": report.snapshot(),
                })

        return report

    def _apply_snapshot(self, runtime_loop: Any, snapshot: RuntimeSnapshot) -> None:
        if hasattr(runtime_loop, "_state") and snapshot.runtime_state_snapshot:
            state = runtime_loop._state
            s = snapshot.runtime_state_snapshot
            for key, val in s.items():
                if hasattr(state, key):
                    setattr(state, key, val)

        if hasattr(runtime_loop, "_traces") and snapshot.traces:
            runtime_loop._traces.clear()
            for td in snapshot.traces:
                runtime_loop._traces.append(self._dict_to_trace(td))

        if hasattr(runtime_loop, "_governance") and snapshot.governance_score_history:
            if hasattr(runtime_loop._governance, "_score_history"):
                runtime_loop._governance._score_history = list(snapshot.governance_score_history)

        if hasattr(runtime_loop, "_confidence"):
            c = runtime_loop._confidence
            if snapshot.confidence_score_history and hasattr(c, "_score_history"):
                c._score_history = list(snapshot.confidence_score_history)
            if hasattr(c, "_guard") and hasattr(c._guard, "_current_gradient"):
                from ..confidence.confidence_index import ExecutionConfidenceGradient
                try:
                    c._guard._current_gradient = ExecutionConfidenceGradient(snapshot.confidence_gradient)
                except Exception:
                    pass

        if hasattr(runtime_loop, "_stability") and snapshot.stability_score_history:
            if hasattr(runtime_loop._stability, "_score_history"):
                runtime_loop._stability._score_history = list(snapshot.stability_score_history)

    def _dict_to_trace(self, d: Any) -> ExecutionTrace:
        if isinstance(d, ExecutionTrace):
            return d
        if isinstance(d, dict):
            return ExecutionTrace(
                event_id=d.get("event_id", ""),
                session_id=d.get("session_id", ""),
                sequence_no=d.get("sequence_no", 0),
                correlation_id=d.get("correlation_id", ""),
                preflight_valid=d.get("preflight_valid", False),
                preflight_reason=d.get("preflight_reason"),
                preflight_rules_triggered=d.get("preflight_rules_triggered", []),
                risk_score=d.get("risk_score", 0.0),
                p4_verdict=d.get("p4_verdict", "UNKNOWN"),
                p4_reason=d.get("p4_reason"),
                p4_risk_level=d.get("p4_risk_level"),
                p4_rule_triggered=d.get("p4_rule_triggered"),
                execution_status=d.get("execution_status", "UNKNOWN"),
                execution_error=d.get("execution_error"),
                capabilities_checked=d.get("capabilities_checked", []),
                resource_usage=d.get("resource_usage", {}),
                preflight_time=d.get("preflight_time", 0.0),
                p4_time=d.get("p4_time", 0.0),
                execution_time=d.get("execution_time", 0.0),
                total_time=d.get("total_time", 0.0),
                final_status=d.get("final_status", "UNKNOWN"),
            )
        return ExecutionTrace()
