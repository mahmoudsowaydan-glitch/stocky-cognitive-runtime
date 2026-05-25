from dataclasses import dataclass, field
from typing import Any, Optional

from .agent_runtime_adapter import AgentInfo, AgentRuntimeAdapter


@dataclass
class RoutingPolicy:
    agent_name: str
    capability_required: str
    priority: int = 0


class AgentRouter:
    def __init__(self, adapter: AgentRuntimeAdapter):
        self._adapter = adapter
        self._policies: list[RoutingPolicy] = []

    def add_policy(self, agent_name: str, capability: str, priority: int = 0) -> None:
        self._policies.append(RoutingPolicy(agent_name, capability, priority))

    def route(self, capability: str, task: dict[str, Any]) -> Optional[str]:
        candidates = self._adapter.available_agents(capability=capability)
        if not candidates:
            return None

        candidates.sort(
            key=lambda a: self._policy_priority(a.name, capability),
            reverse=True,
        )
        return candidates[0].name if candidates else None

    def _policy_priority(self, agent_name: str, capability: str) -> int:
        for policy in self._policies:
            if policy.agent_name == agent_name and policy.capability_required == capability:
                return policy.priority
        return 0
