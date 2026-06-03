from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class HostEventSource(str, Enum):
    IDE = "IDE"
    CLI = "CLI"
    HEADLESS = "HEADLESS"
    REMOTE = "REMOTE"
    PLUGIN = "PLUGIN"


@dataclass
class HostEvent:
    source: HostEventSource
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_id: str | None = None


@dataclass
class WorkspaceState:
    workspace_root: str
    active_files: List[str]
    focused_file: str | None = None
    selection_state: Dict[str, Any] = field(default_factory=dict)
