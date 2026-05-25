from host_abstraction.p4.models import PolicyResult, PolicyVerdict


class PolicyEngine:
    """
    🔴 P4 GOVERNANCE AUTHORITY LAYER
    SINGLE SOURCE OF AUTHORITY: Decisions produced by this engine are final
    and must not be overridden by downstream components when `locked` is True.
    """

    def __init__(self) -> None:
        self.max_safe_risk = 0.65
        # Governance lock: when True, PolicyEngine decisions are authoritative
        # and cannot be programmatically overridden by downstream systems.
        self.locked = True

    def _calculate_risk(self, ticket) -> float:
        risk_map = {
            "LOW": 0.2,
            "MEDIUM": 0.45,
            "HIGH": 0.7,
            "CRITICAL": 0.95,
        }

        risk_level = getattr(ticket.proposal.risk_level, "value", ticket.proposal.risk_level)
        base = risk_map.get(str(risk_level).upper(), 0.5)
        base += (1 - ticket.proposal.confidence) * 0.25
        return min(base, 1.0)

    def evaluate(self, ticket) -> PolicyResult:
        risk = self._calculate_risk(ticket)
        confidence = ticket.proposal.confidence

        result = None

        if risk >= 0.85:
            result = PolicyResult(
                final_verdict=PolicyVerdict.BLOCK,
                risk_score=risk,
                rule_triggered="CRITICAL_RISK",
                reason="Risk exceeds system safety threshold",
                override_bridge=True,
            )

        elif confidence < 0.35:
            result = PolicyResult(
                final_verdict=PolicyVerdict.REVIEW,
                risk_score=risk,
                rule_triggered="LOW_CONFIDENCE",
                reason="Intent uncertainty too high",
                override_bridge=True,
            )

        elif risk > self.max_safe_risk:
            result = PolicyResult(
                final_verdict=PolicyVerdict.DEFER,
                risk_score=risk,
                rule_triggered="RISK_THRESHOLD",
                reason="Requires delay before execution",
                override_bridge=True,
            )

        else:
            result = PolicyResult(
                final_verdict=PolicyVerdict.ALLOW,
                risk_score=risk,
                rule_triggered="SAFE_PATH",
                reason="All policy checks passed",
                override_bridge=False,
            )

        # 🔴 HARD LOCK: when locked, decisions are authoritative and returned.
        if self.locked:
            return result

        # If unlocked (for advanced operators/testing), still return result.
        return result
