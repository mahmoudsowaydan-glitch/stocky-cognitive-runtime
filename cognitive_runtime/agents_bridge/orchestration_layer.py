from collections import defaultdict
from typing import Any, Optional

from ..events.event_types import Event, EventCategory, EventPriority
from .agent_executor import AgentExecutor, AgentTask
from .agent_runtime_adapter import AgentRuntimeAdapter
from .agent_router import AgentRouter


class AgentOrchestrationLayer:
    def __init__(self):
        self._adapter = AgentRuntimeAdapter()
        self._executor = AgentExecutor(self._adapter)
        self._router = AgentRouter(self._adapter)
        self._task_results: dict[str, dict[str, Any]] = {}

    def register_agent(self, name: str, role: str, capabilities: list[str]) -> None:
        self._adapter.register(name, role, capabilities)
        for cap in capabilities:
            self._router.add_policy(name, cap)

    def process_event(self, event: Event) -> dict[str, Any]:
        outputs = {}
        for capability in self._required_capabilities(event):
            agent_name = self._router.route(capability, event.payload)
            if not agent_name:
                continue
            task = self._executor.dispatch(agent_name, event.payload)
            if task:
                output = self._simulate_agent_work(task)
                outputs[agent_name] = output
                self._task_results[task.task_id] = output
        return outputs

    def process_graph(self, graph_data: dict[str, Any]) -> dict[str, Any]:
        outputs = {}
        for agent in self._adapter.available_agents():
            task = self._executor.dispatch(agent.name, graph_data)
            if task:
                output = self._simulate_agent_work(task)
                outputs[agent.name] = output
        return outputs

    def _required_capabilities(self, event: Event) -> list[str]:
        type_to_cap = {
            "analyze": "analysis",
            "modify": "execution",
            "validate": "validation",
            "security": "security",
            "debug": "debug",
        }
        cap = type_to_cap.get(event.type.split("_")[0] if "_" in event.type else event.type, "analysis")
        return [cap]

    def _simulate_agent_work(self, task: AgentTask) -> dict[str, Any]:
        return {"task_id": task.task_id, "agent": task.agent_name, "status": "completed"}

    def get_results(self) -> dict[str, dict[str, Any]]:
        return dict(self._task_results)
