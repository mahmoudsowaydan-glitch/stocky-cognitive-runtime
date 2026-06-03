from typing import List, Optional, Protocol

from .dtos import AgentProfileDTO, RegisterAgentDTO


class AgentAPI(Protocol):
    def register_agent(self, dto: RegisterAgentDTO) -> AgentProfileDTO:
        ...

    def get_agent(self, agent_id: str) -> Optional[AgentProfileDTO]:
        ...

    def list_agents(self) -> List[AgentProfileDTO]:
        ...

    def deactivate_agent(self, agent_id: str) -> bool:
        ...
