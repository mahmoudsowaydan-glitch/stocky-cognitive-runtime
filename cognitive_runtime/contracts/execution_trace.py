from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =========================================================
# PREVENT CIRCULAR IMPORTS — TYPE CHECK ONLY
# =========================================================

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .enriched_event import EnrichedEvent


# =========================================================
# BLOCK 1 — EXECUTION TRACE (CANONICAL SCHEMA)
# =========================================================


@dataclass
class ExecutionTrace:
    # Identity
    event_id: str = ""
    session_id: str = ""
    sequence_no: int = 0
    correlation_id: str = ""

    # Preflight layer
    preflight_valid: bool = False
    preflight_reason: Optional[str] = None
    preflight_rules_triggered: List[str] = field(default_factory=list)
    risk_score: float = 0.0

    # P4 layer
    p4_verdict: str = "UNKNOWN"
    p4_reason: Optional[str] = None
    p4_risk_level: Optional[str] = None
    p4_rule_triggered: Optional[str] = None

    # Sandbox layer
    execution_status: str = "UNKNOWN"
    execution_error: Optional[str] = None
    capabilities_checked: List[str] = field(default_factory=list)
    resource_usage: Dict[str, Any] = field(default_factory=dict)

    # Timing
    preflight_time: float = 0.0
    p4_time: float = 0.0
    execution_time: float = 0.0
    total_time: float = 0.0

    # Final outcome
    final_status: str = "UNKNOWN"


# =========================================================
# BLOCK 2 — EXECUTION TRACE NORMALIZER
# =========================================================


class ExecutionTraceNormalizer:
    """
    Deterministic transformation layer:
    Raw multi-layer execution data -> Canonical ExecutionTrace.

    No decision logic. No business rules.
    Pure structural normalization only.
    """

    def normalize(self, raw: Dict[str, Any]) -> ExecutionTrace:
        return ExecutionTrace(
            event_id=raw.get("event_id", ""),
            session_id=raw.get("session_id", ""),
            sequence_no=raw.get("sequence_no", 0),
            correlation_id=raw.get("correlation_id", ""),

            # Preflight
            preflight_valid=raw.get("preflight", {}).get("valid", False),
            preflight_reason=raw.get("preflight", {}).get("reason"),
            preflight_rules_triggered=raw.get("preflight", {}).get("rules", []),
            risk_score=raw.get("risk_score", 0.0),

            # P4
            p4_verdict=raw.get("p4", {}).get("verdict", "UNKNOWN"),
            p4_reason=raw.get("p4", {}).get("reason"),
            p4_risk_level=raw.get("p4", {}).get("risk_level"),
            p4_rule_triggered=raw.get("p4", {}).get("rule_triggered"),

            # Sandbox
            execution_status=raw.get("sandbox", {}).get("status", "UNKNOWN"),
            execution_error=raw.get("sandbox", {}).get("error"),
            capabilities_checked=raw.get("sandbox", {}).get("capabilities", []),
            resource_usage=raw.get("sandbox", {}).get("resource_usage", {}),

            # Timing
            preflight_time=raw.get("timing", {}).get("preflight", 0.0),
            p4_time=raw.get("timing", {}).get("p4", 0.0),
            execution_time=raw.get("timing", {}).get("execution", 0.0),
            total_time=raw.get("timing", {}).get("total", 0.0),

            # Final
            final_status=self._derive_final_status(raw),
        )

    # =========================================================
    # BLOCK 3 — INTERNAL HELPERS
    # =========================================================

    def _derive_final_status(self, raw: Dict[str, Any]) -> str:
        """
        Deterministic outcome derivation (no external dependencies).
        Priority:
        1. Sandbox failure
        2. P4 decision
        3. Preflight rejection
        """
        sandbox = raw.get("sandbox", {})
        if sandbox.get("status") == "FAILED":
            return "SANDBOX_FAILED"

        p4 = raw.get("p4", {})
        if p4.get("verdict"):
            return f"P4_{p4.get('verdict')}"

        preflight = raw.get("preflight", {})
        if preflight.get("valid") is False:
            return "BLOCKED_BY_PREFLIGHT"

        return "UNKNOWN"


# =========================================================
# BLOCK 4 — EXECUTION TRACE STORE
# =========================================================


class ExecutionTraceStore:
    """
    Ordered, read-friendly store for canonical ExecutionTrace objects.
    Auto-populated by ObservationTap when events complete their cycle.
    """

    def __init__(self, max_size: int = 1000):
        self._traces: list[ExecutionTrace] = []
        self._max_size = max_size

    def add(self, trace: ExecutionTrace) -> None:
        self._traces.append(trace)
        if len(self._traces) > self._max_size:
            self._traces.pop(0)

    def by_correlation_id(self, cid: str) -> Optional[ExecutionTrace]:
        for t in self._traces:
            if t.correlation_id == cid:
                return t
        return None

    def by_event_id(self, eid: str) -> Optional[ExecutionTrace]:
        for t in self._traces:
            if t.event_id == eid:
                return t
        return None

    def by_final_status(self, status: str) -> list[ExecutionTrace]:
        return [t for t in self._traces if t.final_status == status]

    def recent(self, n: int) -> list[ExecutionTrace]:
        return self._traces[-n:]

    def clear(self) -> None:
        self._traces.clear()

    @property
    def all(self) -> list[ExecutionTrace]:
        return list(self._traces)

    def __len__(self) -> int:
        return len(self._traces)


# =========================================================
# BLOCK 5 — ENRICHED EVENT → EXECUTION TRACE HELPER
# =========================================================


def enriched_to_trace_dict(enriched: "EnrichedEvent") -> Dict[str, Any]:
    """
    Build a canonical dict from an EnrichedEvent suitable for
    ExecutionTraceNormalizer.normalize().
    """
    p3 = enriched.p3_proposal
    p4 = enriched.p4_decision
    exec_ = enriched.execution_result

    preflight = {
        "valid": p3 is not None,
        "reason": "proposal_built",
        "rules": [],
    }
    risk_score = p3.risk_score if p3 else 0.0

    p4_block = {
        "verdict": p4.verdict if p4 else
                   "BLOCKED_BY_PREFLIGHT" if enriched.status == "blocked" else
                   enriched.final_verdict or "UNKNOWN",
        "reason": p4.reason if p4 else "",
        "risk_level": p4.risk_level if p4 else "",
        "rule_triggered": p4.rule_triggered if p4 else None,
    }

    sandbox_block = {
        "status": exec_.status if exec_ else "SKIPPED",
        "error": exec_.error if exec_ else None,
        "capabilities": [c.value for c in p3.required_capabilities] if p3 else [],
        "resource_usage": {},
    }

    timing = {
        "preflight": 0.0,
        "p4": 0.0,
        "execution": (exec_.finished_at - exec_.started_at) if exec_ else 0.0,
        "total": 0.0,
    }
    if exec_:
        timing["total"] = exec_.finished_at - exec_.started_at

    return {
        "event_id": enriched.event_id,
        "session_id": enriched.session_id,
        "sequence_no": enriched.sequence_no,
        "correlation_id": enriched.correlation_id,
        "preflight": preflight,
        "risk_score": risk_score,
        "p4": p4_block,
        "sandbox": sandbox_block,
        "timing": timing,
    }
