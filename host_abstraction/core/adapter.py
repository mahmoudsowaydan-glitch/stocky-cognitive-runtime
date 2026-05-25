from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, List

from .contracts import HostEvent, WorkspaceState

EventListener = Callable[[HostEvent], None]


class EditorAdapter(ABC):
    def __init__(self) -> None:
        self._listeners: List[EventListener] = []

    def register_listener(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def unregister_listener(self, listener: EventListener) -> None:
        self._listeners = [l for l in self._listeners if l is not listener]

    def _notify(self, event: HostEvent) -> None:
        for listener in list(self._listeners):
            listener(event)

    @abstractmethod
    def connect(self) -> None:
        """Initialize connection to the host environment."""

    @abstractmethod
    def disconnect(self) -> None:
        """Cleanly close the connection to the host environment."""

    @abstractmethod
    def emit_event(self, event: HostEvent) -> None:
        """Emit a host event into the HAL event pipeline."""

    @abstractmethod
    def get_workspace_state(self) -> WorkspaceState:
        """Read the current workspace state from the host."""

    @abstractmethod
    def execute_command(self, command: str, args: dict | None = None) -> dict:
        """Request the host to execute a command."""
