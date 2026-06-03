from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Callable, Dict, List, Optional
from uuid import uuid4

from ..p4.policy_engine import PolicyEngine
from ..p4.models import PolicyVerdict
from ..p4.decision_ledger import DecisionLedger, DecisionRecord

if TYPE_CHECKING:
    from ..state.cognitive import ExecutionProposal


class ExecutionVerdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"
    REQUIRE_REVIEW = "require_review"


@dataclass
class ArbitrationTicket:
    proposal_id: str
    proposal: ExecutionProposal
    bridge_verdict: str = "PENDING"
    final_verdict: Optional[PolicyVerdict] = None
    p4_rule: Optional[str] = None
    p4_reason: Optional[str] = None
    risk_score: Optional[float] = None
    status: str = "pending"
    created_at: datetime = datetime.utcnow()
    notes: Optional[str] = None


@dataclass
class ArbitrationEvent:
    ticket: ArbitrationTicket
    emitted_at: datetime = datetime.utcnow()


EventListener = Callable[[ArbitrationEvent], None]


class ExecutionArbitrationBridge:
    """Decision gatekeeper bridge between HAL and a future P4 Control Plane.

    - Normalizes `ExecutionProposal` into `ArbitrationTicket`
    - Assigns a preliminary verdict
    - Emits an `ArbitrationEvent` for downstream validation
    - Never executes runtime actions
    """

    def __init__(self, policy_engine: Optional[PolicyEngine] = None, ledger: Optional[DecisionLedger] = None) -> None:
        # Tickets store remains for retrieval, but bridge is observation-only.
        self._tickets: Dict[str, ArbitrationTicket] = {}
        self._listeners: List[EventListener] = []
        # accept injected policy engine and ledger for testability
        self._policy_engine: PolicyEngine = policy_engine or PolicyEngine()
        self._ledger: DecisionLedger = ledger or DecisionLedger()

    def register_listener(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def unregister_listener(self, listener: EventListener) -> None:
        self._listeners = [l for l in self._listeners if l is not listener]

    def submit_proposal(self, proposal: ExecutionProposal) -> ArbitrationTicket:
        ticket = self._normalize_proposal(proposal)

        # Bridge is OBSERVATION ONLY. It must not compute a final decision.
        ticket.bridge_verdict = "OBSERVED"

        # P4 is the single authority
        policy_result = self._policy_engine.evaluate(ticket)

        ticket.final_verdict = policy_result.final_verdict
        ticket.p4_rule = policy_result.rule_triggered
        ticket.p4_reason = policy_result.reason
        ticket.risk_score = policy_result.risk_score
        ticket.status = self._status_from_verdict(policy_result.final_verdict)

        # persist decision to ledger for audit/tracing
        record = DecisionRecord(
            intent=getattr(ticket.proposal, "intent", "unknown"),
            risk=policy_result.risk_score,
            bridge_signal=ticket.bridge_verdict,
            final_verdict=policy_result.final_verdict.value if policy_result.final_verdict is not None else str(policy_result.final_verdict),
            rule_triggered=policy_result.rule_triggered,
            reason=policy_result.reason,
            timestamp=str(datetime.utcnow()),
        )

        try:
            self._ledger.record(record)
        except Exception:
            # ledger failures must not crash the bridge; record failures should be handled upstream
            pass

        self._tickets[ticket.proposal_id] = ticket
        self._emit_event(ticket)
        return ticket

    def _normalize_proposal(self, proposal: ExecutionProposal) -> ArbitrationTicket:
        ticket_id = str(uuid4())
        return ArbitrationTicket(proposal_id=ticket_id, proposal=proposal)

    def _bridge_verdict(self, proposal: ExecutionProposal) -> str:
        # Deprecated: Bridge must not emit a verdict. Keep method for compatibility.
        return "OBSERVED"

    def _status_from_verdict(self, final_verdict: PolicyVerdict) -> str:
        mapping = {
            PolicyVerdict.ALLOW: "approved",
            PolicyVerdict.BLOCK: "denied",
            PolicyVerdict.DEFER: "deferred",
            PolicyVerdict.REVIEW: "requires_review",
        }
        return mapping.get(final_verdict, "pending")

    def _emit_event(self, ticket: ArbitrationTicket) -> None:
        event = ArbitrationEvent(ticket=ticket)
        for listener in list(self._listeners):
            listener(event)

    def _capability_available(self, capability: str) -> bool:
        available = {
            "read.files",
            "write.files",
            "analyze.syntax",
            "format.code",
            "clipboard.write",
            "process.exec",
            "io.write",
            "attach.debugger",
            "read.logs",
            "process.terminate",
        }
        return capability in available

    def get_ticket(self, proposal_id: str) -> Optional[ArbitrationTicket]:
        return self._tickets.get(proposal_id)
