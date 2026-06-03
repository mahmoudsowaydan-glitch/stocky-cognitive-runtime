"""breaking_change_detector.py — Analyzes version transitions for breaking changes.

Checks:
  1. Orphan risk — target version not in graph
  2. Missing lineage — target has no path to root
  3. Illegal jump — version delta exceeds MAX_SUPPORTED_DELTA
  4. Graph violation — transition not in graph edge set
"""

from typing import Dict, List

from .compatibility_rules import CompatibilityRules
from .evolution_graph import EvolutionGraph

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class BreakingChangeDetector:
    def detect(self, from_version: str, to_version: str,
               graph: EvolutionGraph) -> Dict:
        reasons: List[str] = []
        severity = "low"
        is_breaking = False

        if not graph.has_node(to_version):
            reasons.append("orphan_version_detected")
            severity = "critical"
            is_breaking = True

        if not graph.has_lineage_to_root(to_version):
            reasons.append("missing_lineage")
            severity = max(severity, "high", key=lambda s: SEVERITY_ORDER[s])
            is_breaking = True

        f = CompatibilityRules._parse(from_version)
        t = CompatibilityRules._parse(to_version)

        if f[0] != t[0] or abs(t[1] - f[1]) > CompatibilityRules.MAX_SUPPORTED_DELTA:
            reasons.append("illegal_version_jump")
            severity = "critical"
            is_breaking = True

        if not graph.is_valid_transition(from_version, to_version):
            reasons.append("graph_transition_violation")
            if SEVERITY_ORDER.get(severity, 0) < SEVERITY_ORDER["high"]:
                severity = "high"
            is_breaking = True

        return {
            "from": from_version,
            "to": to_version,
            "is_breaking": is_breaking,
            "severity": severity,
            "reasons": reasons,
        }
