from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RuntimeConfig:
    system_name: str = "Stocky Engineering OS"
    version: str = "1.0.0"
    max_pending_events: int = 1000
    default_timeout_ms: int = 30000
    state_timeout_enabled: bool = True
    doctrine_enforcement: bool = True
    control_enforcement: bool = True
    memory_append_only: bool = True
    agent_auto_register: bool = True
    observer_trace_limit: int = 10000
    log_level: str = "INFO"
    sandbox_mode: bool = False
    autoboot: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "RuntimeConfig":
        return cls()

    @classmethod
    def sandbox(cls) -> "RuntimeConfig":
        return cls(sandbox_mode=True, doctrine_enforcement=True,
                   control_enforcement=True, autoboot=True)

    @classmethod
    def development(cls) -> "RuntimeConfig":
        return cls(sandbox_mode=True, log_level="DEBUG",
                   observer_trace_limit=50000, autoboot=True)
