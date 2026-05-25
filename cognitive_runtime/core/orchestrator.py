from typing import Any, Optional

from ..agents_bridge.orchestration_layer import AgentOrchestrationLayer
from ..control_bridge.control_adapter import ControlAdapter, Verdict
from ..doctrine.doctrine_engine import DoctrineEngine
from ..events.event_bus import EventBus
from ..events.event_types import Event, EventCategory, EventPriority
from ..execution.execution_graph import ExecutionGraph
from ..execution.execution_node import ExecutionNode, ActionType, NodeStatus
from ..memory.memory_bridge import MemoryBridge
from ..observation.live_observer import LiveObserver
from ..state.state_context import StateContext
from ..state.runtime_state_machine import RuntimeState


class CentralOrchestrator:
    def __init__(self):
        self.doctrine_engine = DoctrineEngine()
        self.control_bridge = ControlAdapter()
        self.state_context = StateContext()
        self.execution_graph: Optional[ExecutionGraph] = None
        self.agent_layer = AgentOrchestrationLayer()
        self.memory = MemoryBridge()
        self.observer = LiveObserver()
        self.event_bus = EventBus()

    def initialize(self) -> None:
        self.state_context.set_execution_id("sys-init")

    def handle(self, event: Event) -> Optional[dict[str, Any]]:
        self.observer.record(event, phase="received")

        doctrine_result = self.doctrine_engine.validate(event)
        if not doctrine_result.valid:
            self.observer.record_anomaly("doctrine_violation", {
                "event_id": event.id,
                "violations": doctrine_result.violations,
            })
            self._record_memory(event, {"blocked": True, "reason": "doctrine_violation"})
            return {"blocked": True, "reason": "doctrine_violation", "violations": doctrine_result.violations}

        control_decision = self.control_bridge.evaluate(event)
        if control_decision.verdict == Verdict.BLOCK:
            self.observer.record_anomaly("control_block", {
                "event_id": event.id,
                "reason": control_decision.reason,
            })
            self._record_memory(event, {"blocked": True, "reason": control_decision.reason})
            return {"blocked": True, "reason": control_decision.reason}

        if event.category == EventCategory.EXECUTION_PLAN:
            return self._handle_execution_plan(event)
        elif event.category == EventCategory.AGENT_DISPATCH:
            return self._handle_agent_dispatch(event)
        elif event.category == EventCategory.STATE_TRANSITION:
            return self._handle_state_transition(event)
        elif event.category == EventCategory.OBSERVATION:
            return self._handle_observation(event)
        elif event.category == EventCategory.SYSTEM_BOOT:
            return self._handle_system_event(event)

        self._record_memory(event, {"status": "processed"})
        return {"status": "processed"}

    def _handle_execution_plan(self, event: Event) -> dict[str, Any]:
        self.state_context.transition(RuntimeState.PLANNING, trigger="plan_received")
        self.observer.record_state_transition("IDLE", "PLANNING", "plan_received")

        graph = self._build_execution_graph(event)
        if not graph:
            self.state_context.transition(RuntimeState.FAILED, trigger="graph_build_failed")
            return {"error": "failed to build execution graph"}

        self.execution_graph = graph
        self.observer.record(event, phase="graph_built", metadata={
            "node_count": graph.node_count, "graph_id": graph.id,
        })

        self.state_context.transition(RuntimeState.EXECUTING, trigger="graph_ready")
        self.observer.record_state_transition("PLANNING", "EXECUTING", "graph_ready")

        agent_outputs = self.agent_layer.process_graph({"graph_id": graph.id, "node_count": graph.node_count})

        execution_result = self._execute_graph(graph)

        self.state_context.transition(RuntimeState.VERIFYING, trigger="execution_complete")

        if execution_result.get("success"):
            self.state_context.transition(RuntimeState.COMPLETED, trigger="all_passed")
            self.observer.record_state_transition("VERIFYING", "COMPLETED", "all_passed")
        else:
            self.state_context.transition(RuntimeState.RECOVERING, trigger="execution_failed")
            self.observer.record_state_transition("EXECUTING", "RECOVERING", "execution_failed")
            self.state_context.transition(RuntimeState.FAILED, trigger="recovery_failed")

        self._record_memory(event, execution_result)

        return execution_result

    def _handle_agent_dispatch(self, event: Event) -> dict[str, Any]:
        outputs = self.agent_layer.process_event(event)
        self._record_memory(event, {"agent_outputs": outputs})
        return {"agent_outputs": outputs}

    def _handle_state_transition(self, event: Event) -> dict[str, Any]:
        target_str = event.payload.get("target", "")
        target = next((s for s in RuntimeState if s.name == target_str), None)
        if target:
            ok, err = self.state_context.transition(target, trigger=event.payload.get("trigger", ""))
            self.observer.record_state_transition(
                self.state_context.previous.name if self.state_context.previous else "?",
                target.name,
                event.payload.get("trigger", ""),
            )
            return {"success": ok, "error": err}
        return {"success": False, "error": f"unknown state: {target_str}"}

    def _handle_observation(self, event: Event) -> dict[str, Any]:
        self.observer.record(event, phase="observation")
        self._record_memory(event, {"observed": True})
        return {"observed": True}

    def _handle_system_event(self, event: Event) -> dict[str, Any]:
        self.observer.record(event, phase="system")
        return {"system": event.payload.get("status", "unknown")}

    def _build_execution_graph(self, event: Event) -> Optional[ExecutionGraph]:
        try:
            import uuid
            graph = ExecutionGraph(
                id=str(uuid.uuid4()),
                plan_id=event.id,
            )
            steps = event.payload.get("steps", [])
            for step in steps:
                node = ExecutionNode(
                    id=step.get("id", f"step-{len(graph.nodes) + 1}"),
                    action=step.get("action", ""),
                    action_type=ActionType[step.get("action_type", "READ_ANALYSIS").upper()],
                )
                graph.add_node(node)

            deps = event.payload.get("dependencies", [])
            for dep in deps:
                graph.add_edge(dep["from"], dep["to"])

            errors = graph.validate()
            if errors:
                return None
            return graph
        except Exception:
            return None

    def _execute_graph(self, graph: ExecutionGraph) -> dict[str, Any]:
        try:
            sorted_nodes = graph.topological_sort()
        except Exception as e:
            return {"success": False, "error": str(e)}

        results = []
        all_success = True
        for node in sorted_nodes:
            node.status = NodeStatus.RUNNING
            self.observer.record_node_start(node.id, node.action)
            node.status = NodeStatus.SUCCESS
            node.completed_at = node.completed_at
            self.observer.record_node_complete(node.id, {"status": "success"})
            results.append({"node_id": node.id, "status": "success"})

        return {
            "success": all_success,
            "execution_id": graph.id,
            "graph_id": graph.id,
            "state": "COMPLETED" if all_success else "FAILED",
            "nodes": results,
            "checkpoints_passed": 0,
            "checkpoints_total": 0,
            "recovery_triggered": False,
            "rollback_executed": False,
        }

    def _record_memory(self, event: Event, result: dict[str, Any]) -> None:
        self.memory.write(event, result)

    def block(self, event: Event) -> dict[str, Any]:
        return {"blocked": True, "event_id": event.id}
