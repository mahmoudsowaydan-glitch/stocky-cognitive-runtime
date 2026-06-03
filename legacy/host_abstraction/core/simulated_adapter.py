from __future__ import annotations

from typing import Any

from .adapter import EditorAdapter
from .contracts import HostEvent, HostEventSource, WorkspaceState


class SimulatedAdapter(EditorAdapter):
    def __init__(self, host_id: str, initial_root: str) -> None:
        super().__init__()
        self.host_id = host_id
        self.connected = False
        self._workspace_state = WorkspaceState(
            workspace_root=initial_root,
            active_files=[],
            focused_file=None,
            selection_state={},
        )

    def connect(self) -> None:
        self.connected = True
        event = HostEvent(
            source=HostEventSource.HEADLESS,
            type="host.connected",
            payload={"host_id": self.host_id},
        )
        self._notify(event)

    def disconnect(self) -> None:
        self.connected = False
        event = HostEvent(
            source=HostEventSource.HEADLESS,
            type="host.disconnected",
            payload={"host_id": self.host_id},
        )
        self._notify(event)

    def emit_event(self, event: HostEvent) -> None:
        if not self.connected:
            raise RuntimeError("SimulatedAdapter must be connected before emitting events.")
        self._notify(event)

    def get_workspace_state(self) -> WorkspaceState:
        return self._workspace_state

    def execute_command(self, command: str, args: dict | None = None) -> dict:
        if not self.connected:
            raise RuntimeError("SimulatedAdapter must be connected before executing commands.")

        result: dict[str, Any] = {
            "command": command,
            "args": args or {},
            "status": "ok",
        }
        self._notify(
            HostEvent(
                source=HostEventSource.HEADLESS,
                type="command.executed",
                payload={"command": command, "args": args or {}},
            )
        )
        return result

    def set_workspace_state(self, workspace_state: WorkspaceState) -> None:
        self._workspace_state = workspace_state
