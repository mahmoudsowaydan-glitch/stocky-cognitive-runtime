from dataclasses import dataclass, field
from typing import Any, Optional

from .agent_runtime_adapter import AgentInfo, AgentRuntimeAdapter, AgentStatus


@dataclass
class AgentTask:
    task_id: str
    agent_name: str
    input_data: dict[str, Any]
    status: str = "pending"
    output: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class AgentExecutor:
    def __init__(self, adapter: AgentRuntimeAdapter):
        self._adapter = adapter
        self._tasks: list[AgentTask] = []

    def dispatch(self, agent_name: str, input_data: dict[str, Any]) -> Optional[AgentTask]:
        agent = self._adapter.get(agent_name)
        if not agent:
            return None

        import uuid
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_name=agent_name,
            input_data=input_data,
        )
        self._tasks.append(task)

        if self._adapter.activate(agent_name, task.task_id):
            task.status = "running"
        else:
            task.status = "failed"
            task.error = f"cannot activate agent {agent_name}"

        return task

    def complete_task(self, task_id: str, output: dict[str, Any]) -> None:
        for task in self._tasks:
            if task.task_id == task_id:
                task.status = "completed"
                task.output = output
                self._adapter.complete(task.agent_name)
                return

    def fail_task(self, task_id: str, error: str) -> None:
        for task in self._tasks:
            if task.task_id == task_id:
                task.status = "failed"
                task.error = error
                return

    def get_result(self, task_id: str) -> Optional[AgentTask]:
        for task in self._tasks:
            if task.task_id == task_id:
                return task
        return None

    @property
    def pending_tasks(self) -> list[AgentTask]:
        return [t for t in self._tasks if t.status == "pending"]

    @property
    def completed_tasks(self) -> list[AgentTask]:
        return [t for t in self._tasks if t.status == "completed"]
