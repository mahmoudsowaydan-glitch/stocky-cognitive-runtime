from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.execution_trace import ExecutionTrace
from ..contracts.causal_graph import CausalGraph


@dataclass(frozen=True)
class FailureExplanation:
    event_id: str
    root_cause: str
    path: List[str]
    failure_chain: List[Dict[str, Any]]
    total_time_ms: float = 0.0
    replay_impact: bool = False
    governance_denial: bool = False
    sandbox_failure: bool = False
    replay_cascade: bool = False

    @property
    def summary(self) -> str:
        parts = [f"event={self.event_id}", f"root={self.root_cause}"]
        if self.governance_denial:
            parts.append("governance_denial")
        if self.sandbox_failure:
            parts.append("sandbox_failure")
        if self.replay_impact:
            parts.append("replay_impact")
        if self.replay_cascade:
            parts.append("replay_cascade")
        return " | ".join(parts)


class RuntimeFailureExplainer:
    """
    Converts failures into causal explanations.

    Instead of "Execution failed", produces:
    "failure originated from governance denial
     propagated through execution gate
     causing replay interruption at WAL stage"
    """

    DENIAL_STAGES = {"p4_authority", "preflight"}
    EXECUTION_STAGES = {"sandbox_execution", "execution_substrate"}
    REPLAY_STAGES = {"replay", "wal", "recovery"}

    STAGE_LABELS = {
        "host_event": "host event received",
        "proposal": "context proposal built",
        "p4_authority": "governance evaluation",
        "p4_decision": "policy decision",
        "preflight": "preflight check",
        "sandbox_execution": "execution substrate",
        "execution_substrate": "execution sandbox",
        "replay": "replay replay",
        "wal": "WAL persistence",
        "recovery": "recovery stage",
        "event_queue": "event queued",
        "p3_context": "context built",
    }

    def explain(self, trace: ExecutionTrace,
                graph: Optional[CausalGraph] = None) -> FailureExplanation:
        event_id = trace.event_id
        path: List[str] = []
        failure_chain: List[Dict[str, Any]] = []
        root_cause = trace.final_status or "UNKNOWN"

        governance_denial = False
        sandbox_failure = False
        replay_impact = False
        replay_cascade = False

        if trace.p4_verdict in ("BLOCK", "DEFER", "REVIEW"):
            compliance_source = "governance"
            governance_denial = True
            failure_chain.append({
                "stage": "p4_authority",
                "action": "policy_denial",
                "detail": f"verdict={trace.p4_verdict} reason={trace.p4_reason}",
            })
            path.append("governance_denial")
            path.append("propagated through execution gate")
        elif trace.execution_status == "FAILED":
            sandbox_failure = True
            failure_chain.append({
                "stage": "sandbox_execution",
                "action": "execution_failure",
                "detail": f"error={trace.execution_error}",
            })
            path.append("execution_failure")
            path.append("sandbox_error")

        if "BLOCK" in trace.final_status:
            failure_chain.append({
                "stage": "outcome",
                "action": "blocked",
                "detail": f"final_status={trace.final_status}",
            })
            path.append("blocked_propagation")

        if trace.execution_status == "FAILED":
            failure_chain.append({
                "stage": "outcome",
                "action": "failed",
                "detail": trace.execution_error or "no error detail",
            })

        return FailureExplanation(
            event_id=event_id,
            root_cause=root_cause,
            path=path,
            failure_chain=failure_chain,
            total_time_ms=trace.total_time * 1000,
            replay_impact=replay_impact,
            governance_denial=governance_denial,
            sandbox_failure=sandbox_failure,
            replay_cascade=replay_cascade,
        )

    def explain_event_id(self, event_id: str,
                         traces: List[ExecutionTrace],
                         graph: Optional[CausalGraph] = None) -> Optional[FailureExplanation]:
        for t in traces:
            if t.event_id == event_id:
                return self.explain(t, graph)
        return None
