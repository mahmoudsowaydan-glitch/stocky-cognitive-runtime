"""migration_engine.py — Deterministic schema migration between versions.

Rules:
  EVOL-MIG-001: All migrations must be deterministic
  EVOL-MIG-002: No skipping versions (step-by-step only)
  EVOL-MIG-003: No inference or schema guessing allowed
  EVOL-MIG-004: No runtime mutation of graph or registry
  EVOL-MIG-005: Migration must preserve ExecutionTrace semantic integrity
"""

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .compatibility_rules import CompatibilityRules
from .evolution_graph import EvolutionGraph


@dataclass(frozen=True)
class MigrationPlan:
    from_version: str
    to_version: str
    steps: List[str] = field(default_factory=list)
    is_supported: bool = False


Transformer = Callable[[Dict[str, Any]], Dict[str, Any]]


def _normalize_risk_score_scale(trace: Dict[str, Any]) -> Dict[str, Any]:
    t = dict(trace)
    if "risk_score" in t and isinstance(t["risk_score"], float):
        if t["risk_score"] > 1.0:
            t["risk_score"] = t["risk_score"] / 100.0
    return t


def _add_execution_confidence_field(trace: Dict[str, Any]) -> Dict[str, Any]:
    t = dict(trace)
    if "execution_confidence" not in t:
        t["execution_confidence"] = 1.0
    return t


TRANSFORMERS: Dict[str, List[Transformer]] = {
    "1.0.0->1.1.0": [
        _normalize_risk_score_scale,
        _add_execution_confidence_field,
    ],
}


class MigrationEngine:
    def __init__(self, graph: EvolutionGraph):
        self._graph = graph

    def build_path(self, from_v: str, to_v: str) -> MigrationPlan:
        if from_v == to_v:
            return MigrationPlan(
                from_version=from_v, to_version=to_v,
                steps=[], is_supported=False,
            )

        f = CompatibilityRules._parse(from_v)
        t = CompatibilityRules._parse(to_v)

        if f[0] != t[0]:
            return MigrationPlan(
                from_version=from_v, to_version=to_v,
                steps=[], is_supported=False,
            )

        ancestors = self._graph.get_ancestors(to_v)
        if from_v not in ancestors:
            return MigrationPlan(
                from_version=from_v, to_version=to_v,
                steps=[], is_supported=False,
            )

        path: List[str] = []
        current = to_v
        while current != from_v:
            node = self._graph.get_node(current)
            if node is None or not node.parent_versions:
                return MigrationPlan(
                    from_version=from_v, to_version=to_v,
                    steps=[], is_supported=False,
                )
            parent = node.parent_versions[0]
            from_p = CompatibilityRules._parse(parent)
            to_p = CompatibilityRules._parse(current)
            if from_p[0] != to_p[0] or abs(to_p[1] - from_p[1]) > CompatibilityRules.MAX_SUPPORTED_DELTA:
                return MigrationPlan(
                    from_version=from_v, to_version=to_v,
                    steps=[], is_supported=False,
                )
            path.insert(0, current)
            current = parent

        path.insert(0, from_v)
        step_labels = [f"{path[i]}->{path[i+1]}" for i in range(len(path)-1)]

        return MigrationPlan(
            from_version=from_v, to_version=to_v,
            steps=step_labels,
            is_supported=True,
        )

    def migrate_trace(self, trace: Any, from_v: str, to_v: str) -> Any:
        plan = self.build_path(from_v, to_v)
        if not plan.is_supported:
            raise ValueError(
                f"No supported migration path: {from_v} -> {to_v}"
            )

        for step in plan.steps:
            if step not in TRANSFORMERS:
                raise ValueError(
                    f"No transformer registered for step: {step}"
                )

        result = copy.deepcopy(trace)

        if isinstance(result, dict):
            data = dict(result)
        else:
            data = {}
            for attr in dir(result):
                if attr.startswith("_") or callable(getattr(result, attr)):
                    continue
                data[attr] = getattr(result, attr)

        for step in plan.steps:
            for tfn in TRANSFORMERS[step]:
                data = tfn(data)

        if isinstance(result, dict):
            result.clear()
            result.update(data)
        else:
            for k, v in data.items():
                if hasattr(result, k):
                    setattr(result, k, v)

        return result
