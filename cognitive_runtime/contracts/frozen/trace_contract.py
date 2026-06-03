"""
trace_contract.py — Canonical interface definition for ExecutionTrace and ExecutionTraceNormalizer.

Frozen contract. Do not modify without updating schema_version.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .schema_version import fingerprint_class, register_fingerprint


@dataclass(frozen=True)
class ExecutionTraceContract:
    identity: Dict[str, str]
    preflight: Dict[str, Any]
    p4: Dict[str, Any]
    sandbox: Dict[str, Any]
    timing: Dict[str, float]
    final_status: str

    @classmethod
    def from_instance(cls, trace: Any) -> "ExecutionTraceContract":
        return cls(
            identity={
                "event_id": trace.event_id,
                "session_id": trace.session_id,
                "sequence_no": trace.sequence_no,
                "correlation_id": trace.correlation_id,
            },
            preflight={
                "valid": trace.preflight_valid,
                "reason": trace.preflight_reason,
                "rules_triggered": list(trace.preflight_rules_triggered),
                "risk_score": trace.risk_score,
            },
            p4={
                "verdict": trace.p4_verdict,
                "reason": trace.p4_reason,
                "risk_level": trace.p4_risk_level,
                "rule_triggered": trace.p4_rule_triggered,
            },
            sandbox={
                "status": trace.execution_status,
                "error": trace.execution_error,
                "capabilities": list(trace.capabilities_checked),
                "resource_usage": dict(trace.resource_usage),
            },
            timing={
                "preflight_time": trace.preflight_time,
                "p4_time": trace.p4_time,
                "execution_time": trace.execution_time,
                "total_time": trace.total_time,
            },
            final_status=trace.final_status,
        )

    def validate(self) -> List[str]:
        violations = []
        if not self.identity.get("event_id"):
            violations.append("event_id must be non-empty")
        valid_verdicts = ("ALLOW", "BLOCK", "DEFER", "REVIEW", "UNKNOWN",
                          "BLOCKED_BY_PREFLIGHT")
        if self.p4.get("verdict") not in valid_verdicts:
            violations.append(f"invalid verdict: {self.p4.get('verdict')}")
        valid_statuses = ("SUCCESS", "FAILED", "UNKNOWN", "SKIPPED", "QUEUED")
        if self.sandbox.get("status") not in valid_statuses:
            violations.append(f"invalid execution status: {self.sandbox.get('status')}")
        return violations


class TraceContract:
    EXPECTED_FIELDS = [
        "event_id", "session_id", "sequence_no", "correlation_id",
        "preflight_valid", "preflight_reason", "preflight_rules_triggered", "risk_score",
        "p4_verdict", "p4_reason", "p4_risk_level", "p4_rule_triggered",
        "execution_status", "execution_error", "capabilities_checked", "resource_usage",
        "preflight_time", "p4_time", "execution_time", "total_time",
        "final_status",
    ]

    EXPECTED_NORMALIZER_METHODS = [
        "normalize",
    ]

    @classmethod
    def check_trace(cls, trace: Any) -> List[str]:
        violations = []
        for field in cls.EXPECTED_FIELDS:
            if not hasattr(trace, field):
                violations.append(f"ExecutionTrace missing field: {field}")
        return violations

    @classmethod
    def check_normalizer(cls, normalizer: Any) -> List[str]:
        violations = []
        for method in cls.EXPECTED_NORMALIZER_METHODS:
            if not hasattr(normalizer, method):
                violations.append(f"Normalizer missing method: {method}")
            elif not callable(getattr(normalizer, method)):
                violations.append(f"Normalizer.{method} is not callable")
        return violations


register_fingerprint("ExecutionTrace", str(sorted(TraceContract.EXPECTED_FIELDS)))
