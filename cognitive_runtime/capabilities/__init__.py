"""
capabilities/__init__.py — Capability providers + CapabilityRegistry.
Each provider is an async callable: (proposal, decision) -> dict
Providers are stateless, deterministic, and isolated from runtime internals.
"""

from .analyze import analyze_worker
from .count import count_worker
from .report import execute as report_execute
from .repository import execute as repository_execute
from .search import search_worker
from .discovery import execute as test_discovery_execute

__all__ = [
    "analyze_worker",
    "count_worker",
    "search_worker",
    "CapabilityRegistry",
    "repository_execute",
    "test_discovery_execute",
    "report_execute",
]


class CapabilityRegistry:
    """Deterministic mapping from action name to capability worker.
    No dynamic imports, no reflection — explicit registration only.
    """

    def __init__(self):
        self._map = {}
        self._register_all()

    def _register_all(self):
        self.register("analyze", analyze_worker)
        self.register("search", search_worker)
        self.register("count", count_worker)
        self.register("discover_tests", test_discovery_execute)
        self.register("generate_report", report_execute)

    def register(self, action: str, worker) -> None:
        self._map[action] = worker

    def resolve(self, action: str):
        return self._map.get(action)

    def list_actions(self) -> list[str]:
        return sorted(self._map.keys())

    def __contains__(self, action: str) -> bool:
        return action in self._map

    def __len__(self) -> int:
        return len(self._map)
