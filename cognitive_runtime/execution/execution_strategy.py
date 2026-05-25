from enum import Enum, auto

from .execution_graph import ExecutionGraph, EdgeType
from .execution_node import ActionType, RiskLevel


class Strategy(Enum):
    SEQUENTIAL = auto()
    PARALLEL_SAFE = auto()
    PARALLEL_WITH_LOCK = auto()
    VALIDATE_FIRST = auto()


def select_strategy(graph: ExecutionGraph) -> Strategy:
    if graph.estimated_risk_level == RiskLevel.CRITICAL:
        return Strategy.VALIDATE_FIRST

    has_data_dep = any(e.type == EdgeType.DATA_DEPENDENCY for e in graph.edges)
    if has_data_dep:
        return Strategy.SEQUENTIAL

    all_read_only = all(
        n.action_type in (ActionType.READ_ANALYSIS, ActionType.VALIDATE)
        for n in graph.nodes.values()
    )
    if all_read_only:
        return Strategy.PARALLEL_SAFE

    files_per_node = {}
    for nid, node in graph.nodes.items():
        files_per_node[nid] = node.action
    target_ids = [n.action for n in graph.nodes.values() if n.action_type == ActionType.MODIFY_FILE]
    if len(target_ids) == len(set(target_ids)):
        return Strategy.PARALLEL_WITH_LOCK

    return Strategy.SEQUENTIAL
