"""
bridge_contract.py — Canonical interfaces for runtime bridges (feedback, observation_tap, etc).

Frozen contract. Do not modify without updating schema_version.
"""

from typing import Any, Dict, List, Optional

from .schema_version import fingerprint_class, register_fingerprint


class BridgeContract:
    """
    Defines the canonical interface that every bridge must satisfy.
    Bridges connect runtime layers to HAL observation and cross-layer analysis.
    """

    # ── ObservationTap contract ──
    TAP_EXPECTED_METHODS = [
        "tap_event_received",
        "tap_p3_proposal",
        "tap_p4_decision",
        "tap_execution_result",
        "tap_blocked",
        "get_enriched",
        "get_by_session",
        "get_by_status",
        "subscribe",
    ]

    TAP_EXPECTED_PROPERTIES = [
        "total_traced",
        "completed_cycles",
    ]

    # ── FeedbackBridge contract ──
    FEEDBACK_EXPECTED_METHODS = [
        "analyze",
    ]

    FEEDBACK_EXPECTED_PROPERTIES = [
        "history",
    ]

    # ── FeedbackReport contract ──
    FEEDBACK_REPORT_FIELDS = [
        "insights",
        "failure_clusters",
        "dominant_layer_trends",
    ]

    # ── FeedbackInsight contract ──
    FEEDBACK_INSIGHT_FIELDS = [
        "insight_type",
        "description",
        "severity",
        "data",
    ]

    # ── EnrichedEvent contract ──
    ENRICHED_EVENT_FIELDS = [
        "event_id",
        "session_id",
        "sequence_no",
        "correlation_id",
        "host_event",
        "p3_proposal",
        "p4_decision",
        "execution_result",
        "hal_trace",
        "status",
    ]

    ENRICHED_EVENT_METHODS = [
        "add_trace",
    ]

    ENRICHED_EVENT_PROPERTIES = [
        "has_full_cycle",
        "final_verdict",
        "final_status",
    ]

    @classmethod
    def check_observation_tap(cls, tap: Any) -> List[str]:
        violations = []
        for method in cls.TAP_EXPECTED_METHODS:
            if not hasattr(tap, method):
                violations.append(f"ObservationTap missing method: {method}")
            elif not callable(getattr(tap, method)):
                violations.append(f"ObservationTap.{method} is not callable")
        for prop in cls.TAP_EXPECTED_PROPERTIES:
            if not hasattr(tap, prop):
                violations.append(f"ObservationTap missing property: {prop}")
            elif callable(getattr(tap, prop)):
                violations.append(f"ObservationTap.{prop} is callable, expected property")
        return violations

    @classmethod
    def check_feedback_bridge(cls, bridge: Any) -> List[str]:
        violations = []
        for method in cls.FEEDBACK_EXPECTED_METHODS:
            if not hasattr(bridge, method):
                violations.append(f"FeedbackBridge missing method: {method}")
            elif not callable(getattr(bridge, method)):
                violations.append(f"FeedbackBridge.{method} is not callable")
        for prop in cls.FEEDBACK_EXPECTED_PROPERTIES:
            if not hasattr(bridge, prop):
                violations.append(f"FeedbackBridge missing property: {prop}")
        return violations

    @classmethod
    def check_feedback_report(cls, report: Any) -> List[str]:
        violations = []
        for field in cls.FEEDBACK_REPORT_FIELDS:
            if not hasattr(report, field):
                violations.append(f"FeedbackReport missing field: {field}")
        return violations

    @classmethod
    def check_feedback_insight(cls, insight: Any) -> List[str]:
        violations = []
        for field in cls.FEEDBACK_INSIGHT_FIELDS:
            if not hasattr(insight, field):
                violations.append(f"FeedbackInsight missing field: {field}")
        return violations

    @classmethod
    def check_enriched_event(cls, event: Any) -> List[str]:
        violations = []
        for field in cls.ENRICHED_EVENT_FIELDS:
            if not hasattr(event, field):
                violations.append(f"EnrichedEvent missing field: {field}")
        for method in cls.ENRICHED_EVENT_METHODS:
            if not hasattr(event, method):
                violations.append(f"EnrichedEvent missing method: {method}")
            elif not callable(getattr(event, method)):
                violations.append(f"EnrichedEvent.{method} is not callable")
        for prop in cls.ENRICHED_EVENT_PROPERTIES:
            if not hasattr(event, prop):
                violations.append(f"EnrichedEvent missing property: {prop}")
        return violations


register_fingerprint("BridgeContract", str(sorted(
    BridgeContract.TAP_EXPECTED_METHODS
    + BridgeContract.TAP_EXPECTED_PROPERTIES
    + BridgeContract.FEEDBACK_EXPECTED_METHODS
    + BridgeContract.FEEDBACK_EXPECTED_PROPERTIES
    + BridgeContract.FEEDBACK_REPORT_FIELDS
    + BridgeContract.FEEDBACK_INSIGHT_FIELDS
    + BridgeContract.ENRICHED_EVENT_FIELDS
    + BridgeContract.ENRICHED_EVENT_METHODS
    + BridgeContract.ENRICHED_EVENT_PROPERTIES
)))
