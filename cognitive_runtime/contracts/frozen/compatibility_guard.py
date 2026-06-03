"""
compatibility_guard.py — Runtime compatibility assertions for frozen contracts.

Detects:
  - missing fields / methods on contract implementations
  - bridge interface incompatibility
  - graph schema mismatch
  - trace schema drift
  - runtime lifecycle violations
"""

from typing import Any, Dict, List, Optional, Tuple

from .schema_version import FROZEN_SCHEMA_VERSION, SchemaVersion
from .graph_contract import GraphContract
from .trace_contract import TraceContract
from .bridge_contract import BridgeContract
from .runtime_contract import RuntimeContract


class CompatibilityGuard:
    """
    Runs all contract checks against actual runtime instances.
    Returns structured violation reports.
    Logs all violations through an optional observer.
    """

    def __init__(self, schema_version: Optional[SchemaVersion] = None,
                 hal_observer: Optional[Any] = None):
        self._schema_version = schema_version or FROZEN_SCHEMA_VERSION
        self._hal = hal_observer
        self._violations: List[Dict[str, Any]] = []

    @property
    def schema_version(self) -> SchemaVersion:
        return self._schema_version

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def violations(self) -> List[Dict[str, Any]]:
        return list(self._violations)

    def clear(self) -> None:
        self._violations.clear()

    def _record(self, component: str, severity: str, message: str) -> None:
        entry = {
            "component": component,
            "severity": severity,
            "message": message,
            "schema_version": str(self._schema_version),
        }
        self._violations.append(entry)
        if self._hal:
            self._hal({"type": "contract.violation", "data": entry})

    # ── Graph checks ──

    def check_graph(self, name: str, graph: Any) -> bool:
        component = f"CausalGraph({name})"
        violations = GraphContract.check_graph(graph)
        for v in violations:
            self._record(component, "error", v)
        if not violations:
            if hasattr(graph, "nodes") and graph.nodes:
                sample = next(iter(graph.nodes.values()))
                node_violations = GraphContract.check_node_instance(sample)
                for v in node_violations:
                    self._record(f"{component}.node", "error", v)
            if hasattr(graph, "edges") and graph.edges:
                sample = graph.edges[0]
                edge_violations = GraphContract.check_edge_instance(sample)
                for v in edge_violations:
                    self._record(f"{component}.edge", "error", v)
        return len(violations) == 0

    def check_graph_contract(self, name: str, graph: Any) -> Tuple[bool, int]:
        ok = self.check_graph(name, graph)
        return ok, len([v for v in self._violations if v["component"].startswith(f"CausalGraph({name})")])

    # ── Trace checks ──

    def check_trace(self, trace: Any) -> bool:
        violations = TraceContract.check_trace(trace)
        for v in violations:
            self._record("ExecutionTrace", "error", v)
        return len(violations) == 0

    def check_traces(self, traces: List[Any]) -> Tuple[int, int]:
        failed = 0
        for t in traces:
            if not self.check_trace(t):
                failed += 1
        return len(traces) - failed, failed

    def check_normalizer(self, normalizer: Any) -> bool:
        violations = TraceContract.check_normalizer(normalizer)
        for v in violations:
            self._record("ExecutionTraceNormalizer", "error", v)
        return len(violations) == 0

    # ── Bridge checks ──

    def check_observation_tap(self, tap: Any) -> bool:
        violations = BridgeContract.check_observation_tap(tap)
        for v in violations:
            self._record("ObservationTap", "error", v)
        return len(violations) == 0

    def check_feedback_bridge(self, bridge: Any) -> bool:
        violations = BridgeContract.check_feedback_bridge(bridge)
        for v in violations:
            self._record("FeedbackBridge", "error", v)
        return len(violations) == 0

    def check_enriched_event(self, event: Any) -> bool:
        violations = BridgeContract.check_enriched_event(event)
        for v in violations:
            self._record("EnrichedEvent", "error", v)
        return len(violations) == 0

    # ── Runtime checks ──

    def check_runtime_state(self, state: Any) -> bool:
        violations = RuntimeContract.check_runtime_state(state)
        for v in violations:
            self._record("RuntimeState", "error", v)
        return len(violations) == 0

    def check_orchestrator(self, orchestrator: Any) -> bool:
        violations = RuntimeContract.check_orchestrator(orchestrator)
        for v in violations:
            self._record("RuntimeOrchestrator", "error", v)
        return len(violations) == 0

    # ── Full system check ──

    def run_all(self, runtime_loop: Any) -> Dict[str, Any]:
        pre_count = len(self._violations)

        if hasattr(runtime_loop, "_causal_graph"):
            self.check_graph("runtime", runtime_loop._causal_graph)
        if hasattr(runtime_loop, "_trace_normalizer"):
            self.check_normalizer(runtime_loop._trace_normalizer)
        if hasattr(runtime_loop, "_tap"):
            self.check_observation_tap(runtime_loop._tap)
        if hasattr(runtime_loop, "_feedback"):
            self.check_feedback_bridge(runtime_loop._feedback)
        if hasattr(runtime_loop, "_state"):
            self.check_runtime_state(runtime_loop._state)
        if hasattr(runtime_loop, "_orchestrator"):
            self.check_orchestrator(runtime_loop._orchestrator)
        if hasattr(runtime_loop, "_traces"):
            passed, failed = self.check_traces(runtime_loop._traces)
            if failed > 0:
                self._record("ExecutionTrace[]", "warning",
                             f"{failed}/{passed + failed} traces failed contract check")

        new_violations = len(self._violations) - pre_count
        return {
            "schema_version": str(self._schema_version),
            "violations_found": new_violations,
            "total_violations": len(self._violations),
            "passed": new_violations == 0,
        }
