"""compatibility_rules.py — FROZEN rules for schema evolution compatibility.

Rules:
  EVOL-COMP-001: No major version jumps allowed.
  EVOL-COMP-002: Only +1 minor step allowed per transition.
  EVOL-COMP-003: Graph must validate all transitions.
  EVOL-COMP-004: Orphan versions are invalid.

Semantics (EVOL-SEM-001): read-only, never mutates graph.
"""

from typing import Tuple

from .evolution_graph import EvolutionGraph


class CompatibilityRules:
    MAX_SUPPORTED_DELTA = 1

    @staticmethod
    def _parse(v: str) -> Tuple[int, int, int]:
        major, minor, patch = map(int, v.split("."))
        return major, minor, patch

    @staticmethod
    def _delta(from_v: str, to_v: str) -> int:
        f = CompatibilityRules._parse(from_v)
        t = CompatibilityRules._parse(to_v)

        if f[0] != t[0]:
            return 999

        return abs(t[1] - f[1])

    @staticmethod
    def is_backward_compatible(from_v: str, to_v: str,
                               graph: EvolutionGraph) -> bool:
        f = CompatibilityRules._parse(from_v)
        t = CompatibilityRules._parse(to_v)

        return (
            f[0] == t[0]
            and t[1] >= f[1]
            and CompatibilityRules._delta(from_v, to_v)
            <= CompatibilityRules.MAX_SUPPORTED_DELTA
        )

    @staticmethod
    def is_forward_compatible(from_v: str, to_v: str,
                              graph: EvolutionGraph) -> bool:
        f = CompatibilityRules._parse(from_v)
        t = CompatibilityRules._parse(to_v)

        return (
            f[0] == t[0]
            and t[1] <= f[1]
            and CompatibilityRules._delta(from_v, to_v)
            <= CompatibilityRules.MAX_SUPPORTED_DELTA
        )

    @staticmethod
    def is_allowed_transition(from_v: str, to_v: str,
                              graph: EvolutionGraph) -> bool:
        if not graph.is_valid_transition(from_v, to_v):
            return False

        if CompatibilityRules._delta(from_v, to_v) > CompatibilityRules.MAX_SUPPORTED_DELTA:
            return False

        return True
