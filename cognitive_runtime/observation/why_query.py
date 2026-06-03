from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph, CausalNode, CausalGraphBuilder
from ..contracts.execution_trace import ExecutionTraceStore
from ..substrate.observation_tap import ObservationTap


@dataclass
class WhyBlockedResult:
    event_id: str
    correlation_id: str
    root_cause: str
    blocking_stage: str
    reason: str
    chain: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WhyFailureResult:
    event_id: str
    correlation_id: str
    root_cause: str
    error: Optional[str]
    chain: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FullTraceResult:
    event_id: str
    correlation_id: str
    path: List[Dict[str, Any]]
    total_time_ms: float
    outcome: str


class WhyQuery:
    """
    Pure read-only explainability layer.
    Answers "Why did the system reach this state?" using CausalGraph + ExecutionTraceStore.

    No side effects. No state mutation. No access to policy_engine, sandbox, or preflight.
    """

    def __init__(self, tap: ObservationTap,
                 trace_store: Optional[ExecutionTraceStore] = None):
        self._tap = tap
        self._trace_store = trace_store
        self._builder = CausalGraphBuilder()

    # ─────────────────────────────────────────────────
    #  Core: Build graph on demand from current state
    # ─────────────────────────────────────────────────

    def _build_graph(self) -> CausalGraph:
        if not self._trace_store:
            return CausalGraph({}, [])
        return self._builder.build(list(self._trace_store.all))

    # ─────────────────────────────────────────────────
    #  Query 1: Why was this event blocked?
    # ─────────────────────────────────────────────────

    def blocked(self, event_id: str) -> Optional[WhyBlockedResult]:
        enriched = self._tap.get_enriched(event_id)
        if not enriched or enriched.status != "blocked":
            return None

        p4 = enriched.p4_decision
        reason = p4.reason if p4 else "No P4 decision recorded"
        verdict = p4.verdict if p4 else "BLOCKED"

        chain: List[Dict[str, Any]] = [
            {"stage": "host_event", "result": "received"},
        ]

        if enriched.p3_proposal:
            chain.append({
                "stage": "proposal",
                "result": "built",
                "action": enriched.p3_proposal.action,
                "risk_score": enriched.p3_proposal.risk_score,
            })

        chain.append({
            "stage": "p4_authority",
            "result": verdict,
            "reason": reason,
            "rule_triggered": p4.rule_triggered if p4 else None,
        })

        return WhyBlockedResult(
            event_id=event_id,
            correlation_id=enriched.correlation_id,
            root_cause=f"P4_{verdict}",
            blocking_stage="p4_authority",
            reason=reason,
            chain=chain,
        )

    # ─────────────────────────────────────────────────
    #  Query 2: Why did execution fail?
    # ─────────────────────────────────────────────────

    def failed(self, event_id: str) -> Optional[WhyFailureResult]:
        enriched = self._tap.get_enriched(event_id)
        if not enriched:
            return None

        exec_ = enriched.execution_result
        if not exec_ or exec_.status != "FAILED":
            return None

        chain: List[Dict[str, Any]] = [
            {"stage": "host_event", "result": "received"},
        ]

        if enriched.p3_proposal:
            chain.append({
                "stage": "proposal",
                "result": "built",
                "action": enriched.p3_proposal.action,
            })

        p4 = enriched.p4_decision
        if p4:
            chain.append({
                "stage": "p4_authority",
                "result": p4.verdict,
                "reason": p4.reason,
            })

        chain.append({
            "stage": "sandbox_execution",
            "result": "FAILED",
            "error": exec_.error,
            "duration_ms": (exec_.finished_at - exec_.started_at) * 1000,
        })

        return WhyFailureResult(
            event_id=event_id,
            correlation_id=enriched.correlation_id,
            root_cause="SANDBOX_FAILED",
            error=exec_.error,
            chain=chain,
        )

    # ─────────────────────────────────────────────────
    #  Query 3: What happened between time X and Y?
    # ─────────────────────────────────────────────────

    def time_range(self, start: float, end: float) -> CausalGraph:
        if not self._trace_store:
            return CausalGraph({}, [])
        enriched_list = self._tap.get_by_status("completed") \
            + self._tap.get_by_status("failed") \
            + self._tap.get_by_status("blocked")
        filtered_eids = {
            e.event_id for e in enriched_list
            if start <= e.host_event.timestamp <= end
        }
        filtered_traces = [
            t for t in self._trace_store.all
            if t.event_id in filtered_eids
        ]
        return self._builder.build(filtered_traces)

    # ─────────────────────────────────────────────────
    #  Query 4: Full causal trace of an event
    # ─────────────────────────────────────────────────

    def full_trace(self, event_id: str) -> Optional[FullTraceResult]:
        enriched = self._tap.get_enriched(event_id)
        if not enriched:
            return None

        graph = self._build_graph()
        root_nodes = [n for n in graph.nodes.values() if n.event_id == event_id and n.node_type == "host_event"]

        if not root_nodes:
            return None

        path = graph.path_to_outcome(root_nodes[0].node_id)

        exec_ = enriched.execution_result
        total_ms = 0.0
        if exec_:
            total_ms = (exec_.finished_at - exec_.started_at) * 1000

        outcome = "UNKNOWN"
        if enriched.status == "blocked":
            outcome = "BLOCKED"
        elif exec_:
            outcome = exec_.status

        return FullTraceResult(
            event_id=event_id,
            correlation_id=enriched.correlation_id,
            path=[
                {
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "data": n.data,
                }
                for n in path
            ],
            total_time_ms=round(total_ms, 2),
            outcome=outcome,
        )

    # ─────────────────────────────────────────────────
    #  Utility: list all available traces
    # ─────────────────────────────────────────────────

    def trace_store_summary(self) -> List[Dict[str, Any]]:
        if not self._trace_store:
            return []
        return [
            {
                "event_id": t.event_id,
                "correlation_id": t.correlation_id,
                "final_status": t.final_status,
                "p4_verdict": t.p4_verdict,
                "execution_status": t.execution_status,
            }
            for t in self._trace_store.recent(100)
        ]
