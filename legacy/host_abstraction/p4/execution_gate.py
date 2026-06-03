from host_abstraction.p4.models import PolicyVerdict


class ExecutionGate:

    def __init__(self):
        self.execution_log = []

    def apply(self, ticket, policy_result):
        verdict = policy_result.final_verdict

        if verdict == PolicyVerdict.ALLOW:
            action = "SIMULATE_EXECUTION"
        elif verdict == PolicyVerdict.BLOCK:
            action = "LOG_ONLY"
        elif verdict == PolicyVerdict.REVIEW:
            action = "REQUEUE_TO_HAL"
        elif verdict == PolicyVerdict.DEFER:
            action = "QUEUE_LATER"
        else:
            action = "UNKNOWN"

        record = {
            "intent": getattr(ticket.proposal, "intent", "unknown"),
            "verdict": verdict.value if verdict is not None else "UNKNOWN",
            "action": action,
            "risk": policy_result.risk_score,
            "rule": policy_result.rule_triggered,
            "reason": policy_result.reason,
        }

        self.execution_log.append(record)
        return record
