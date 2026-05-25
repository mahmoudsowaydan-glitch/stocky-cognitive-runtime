from collections import defaultdict
from typing import Optional

from .memory_bridge import MemoryRecord


class LineageGraph:
    def __init__(self):
        self._parents: dict[str, str] = {}
        self._children: dict[str, list[str]] = defaultdict(list)

    def link(self, parent_id: str, child_id: str) -> None:
        self._parents[child_id] = parent_id
        self._children[parent_id].append(child_id)

    def get_parent(self, event_id: str) -> Optional[str]:
        return self._parents.get(event_id)

    def get_children(self, event_id: str) -> list[str]:
        return list(self._children.get(event_id, []))

    def get_lineage(self, event_id: str) -> list[str]:
        lineage = [event_id]
        current = event_id
        while current in self._parents:
            current = self._parents[current]
            lineage.insert(0, current)
        return lineage

    def get_subgraph(self, root_id: str) -> list[str]:
        result = []
        queue = [root_id]
        while queue:
            current = queue.pop(0)
            result.append(current)
            queue.extend(self._children.get(current, []))
        return result

    def detect_cycles(self) -> list[list[str]]:
        visited: dict[str, int] = {}
        cycles = []
        path: list[str] = []

        def dfs(node: str):
            visited[node] = 1
            path.append(node)
            if node in self._children:
                for child in self._children[node]:
                    if child in visited:
                        if visited[child] == 1:
                            cycle_start = path.index(child)
                            cycles.append(path[cycle_start:] + [child])
                    else:
                        dfs(child)
            path.pop()
            visited[node] = 2

        for node in list(self._parents.keys()) + list(self._children.keys()):
            if node not in visited:
                dfs(node)
        return cycles
