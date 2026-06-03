from typing import Protocol

from .dtos import DaemonStatusDTO, HealthDTO


class RuntimeAPI(Protocol):
    def get_daemon_status(self) -> DaemonStatusDTO:
        ...

    def get_health(self) -> HealthDTO:
        ...

    def get_version(self) -> str:
        ...
