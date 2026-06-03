"""
runtime_contract.py — Canonical lifecycle, orchestration, and periodic task semantics.

Frozen contract. Do not modify without updating schema_version.
"""

from typing import Any, Dict, List, Optional

from .schema_version import fingerprint_class, register_fingerprint


class RuntimeContract:
    """
    Defines the canonical runtime lifecycle that RuntimeLoop must satisfy.
    All consumers (HAL, external observers, orchestration chain) rely on this contract.
    """

    # ── RuntimeState fields ──
    STATE_FIELDS = [
        "started_at", "uptime_seconds", "status",
        "queue_depth", "total_events_processed",
        "active_sessions", "total_sessions",
        "last_execution_trace_id", "last_execution_status", "last_execution_at",
        "consecutive_failures", "total_failures", "health_status",
        "drift_detected", "drift_count",
        "average_cycle_ms", "last_cycle_ms",
        "last_error", "errors",
    ]

    STATE_METHODS = [
        "record_cycle",
        "record_error",
        "snapshot",
    ]

    # ── RuntimeOrchestrator contract ──
    ORCHESTRATOR_METHODS = [
        "start",
        "stop",
        "pause",
        "resume",
        "tick_heartbeat",
    ]

    ORCHESTRATOR_PROPERTIES = [
        "is_running",
        "state",
    ]

    # ── Heartbeat contract ──
    HEARTBEAT_FIELDS = [
        "timestamp", "status", "uptime", "queue_depth",
        "events_processed", "health_status",
        "average_cycle_ms", "drift_detected",
    ]

    # ── RuntimeLoop periodic schedule ──
    PERIODIC_SCHEDULE = {
        "causal_graph_rebuild": 10,
        "intelligence_compression": 10,
        "feedback_analysis": 20,
        "stability_index": 50,
        "confidence_assessment": 75,
        "governance_entropy": 100,
    }

    LIFECYCLE_INVARIANTS = [
        "P4 is the single authority — no layer overrides P4 decisions",
        "HAL is strictly observational — no influence on execution path",
        "P3 is context builder only — no decision shaping",
        "Sandbox is dumb executor — no interpretation of P4 output",
        "risk_score is observability-only — never enters decision chain",
        "Intelligence layer is read-only compression — no feedback loop",
        "Stability layer is measurement-only — not a controller",
        "Confidence layer is observational — not authority",
        "Governance layer is observational — no coupling with P4/sandbox",
    ]

    CYCLE_GUARANTEES = {
        "ordering": "strict (session_id, sequence_no) via TimeKernel",
        "trace_appended_before_checks": True,
        "drift_detected_before_periodic": True,
        "hal_observer_invoked_each_cycle": True,
        "exception_does_not_lose_trace": True,
    }

    @classmethod
    def check_runtime_state(cls, state: Any) -> List[str]:
        violations = []
        for field in cls.STATE_FIELDS:
            if not hasattr(state, field):
                violations.append(f"RuntimeState missing field: {field}")
        for method in cls.STATE_METHODS:
            if not hasattr(state, method):
                violations.append(f"RuntimeState missing method: {method}")
            elif not callable(getattr(state, method)):
                violations.append(f"RuntimeState.{method} is not callable")
        return violations

    @classmethod
    def check_orchestrator(cls, orchestrator: Any) -> List[str]:
        violations = []
        for method in cls.ORCHESTRATOR_METHODS:
            if not hasattr(orchestrator, method):
                violations.append(f"RuntimeOrchestrator missing method: {method}")
            elif not callable(getattr(orchestrator, method)):
                violations.append(f"RuntimeOrchestrator.{method} is not callable")
        for prop in cls.ORCHESTRATOR_PROPERTIES:
            if not hasattr(orchestrator, prop):
                violations.append(f"RuntimeOrchestrator missing property: {prop}")
        return violations

    @classmethod
    def check_heartbeat(cls, hb: Any) -> List[str]:
        violations = []
        for field in cls.HEARTBEAT_FIELDS:
            if not hasattr(hb, field):
                violations.append(f"Heartbeat missing field: {field}")
        return violations

    @classmethod
    def check_periodic_schedule(cls, loop: Any) -> Dict[str, bool]:
        results = {}
        for task, expected_cycle in cls.PERIODIC_SCHEDULE.items():
            results[task] = False
            if hasattr(loop, "_finalize_cycle"):
                import inspect
                source = inspect.getsource(loop._finalize_cycle)
                if str(expected_cycle) in source:
                    results[task] = True
        return results

    @classmethod
    def verify_lifecycle_invariants(cls, loop: Any) -> List[str]:
        violations = []
        for inv in cls.LIFECYCLE_INVARIANTS:
            violations.append(f"Invariant not verifiable at runtime: {inv}")
        return violations


register_fingerprint("RuntimeContract", str(sorted(
    RuntimeContract.STATE_FIELDS
    + RuntimeContract.STATE_METHODS
    + RuntimeContract.ORCHESTRATOR_METHODS
    + RuntimeContract.ORCHESTRATOR_PROPERTIES
    + RuntimeContract.HEARTBEAT_FIELDS
)))
