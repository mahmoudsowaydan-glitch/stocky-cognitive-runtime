"""
preflight_analyzer.py — EXECUTION ENGINE for preflight validation.

Stateless, deterministic gate.
Produces {valid: bool, reason: str, risk_score: float}.
Uses preflight_rules.py as SOURCE OF TRUTH.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from ..contracts.execution_contract import ExecutionProposal
from ..contracts.enriched_event import EnrichedEvent
from .preflight_rules import RULES, RuleSeverity


@dataclass
class PreflightResult:
    valid: bool
    reason: str = ""
    risk_score: float = 0.0
    flags: list[str] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)


class PreflightAnalyzer:
    def analyze(self, proposal: ExecutionProposal) -> PreflightResult:
        raw_caps = []
        for c in proposal.required_capabilities:
            if isinstance(c, str):
                raw_caps.append(c)
            else:
                raw_caps.append(c.value)
        proposal_dict = {
            "proposal_id": proposal.proposal_id,
            "session_id": proposal.session_id,
            "event_id": proposal.event_id,
            "action": proposal.action,
            "target": proposal.target,
            "params": proposal.params,
            "required_capabilities": raw_caps,
            "confidence": proposal.confidence,
            "risk_score": proposal.risk_score,
            "metadata": proposal.metadata,
        }

        flags: list[str] = []
        triggered: list[str] = []

        for rule in RULES:
            violation = rule.evaluate(proposal_dict)
            if violation is None:
                continue

            triggered.append(rule.name)

            if rule.severity == RuleSeverity.BLOCK:
                return PreflightResult(
                    valid=False,
                    reason=f"BLOCKED_BY_PREFLIGHT: {rule.name} - {violation}",
                    risk_score=proposal.risk_score,
                    flags=flags,
                    triggered_rules=triggered,
                )

            if rule.severity == RuleSeverity.FLAG:
                flags.append(f"{rule.name}: {violation}")

        return PreflightResult(
            valid=True,
            reason="preflight_passed",
            risk_score=proposal.risk_score,
            flags=flags,
            triggered_rules=triggered,
        )
