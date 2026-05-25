from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class AgentStatus(Enum):
    IDLE = auto()
    ACTIVATED = auto()
    WORKING = auto()
    OUTPUT_READY = auto()
    VALIDATING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class AgentInfo:
    name: str
    role: str
    status: AgentStatus = AgentStatus.IDLE
    capabilities: list[str] = field(default_factory=list)
    current_task: Optional[str] = None


class AgentRuntimeAdapter:
    def __init__(self):
        self._agents: dict[str, AgentInfo] = {}

    def register(self, name: str, role: str, capabilities: list[str]) -> AgentInfo:
        agent = AgentInfo(name=name, role=role, capabilities=capabilities)
        self._agents[name] = agent
        return agent

    def get(self, name: str) -> Optional[AgentInfo]:
        return self._agents.get(name)

    def activate(self, name: str, task: str) -> bool:
        agent = self._agents.get(name)
        if not agent or agent.status != AgentStatus.IDLE:
            return False
        agent.status = AgentStatus.ACTIVATED
        agent.current_task = task
        return True

    def complete(self, name: str) -> bool:
        agent = self._agents.get(name)
        if not agent:
            return False
        agent.status = AgentStatus.COMPLETED
        agent.current_task = None
        return True

    def available_agents(self, capability: Optional[str] = None) -> list[AgentInfo]:
        agents = [a for a in self._agents.values() if a.status == AgentStatus.IDLE]
        if capability:
            agents = [a for a in agents if capability in a.capabilities]
        return agents

    @property
    def active_agents(self) -> list[AgentInfo]:
        return [a for a in self._agents.values() if a.status in (
            AgentStatus.ACTIVATED, AgentStatus.WORKING, AgentStatus.VALIDATING)]
