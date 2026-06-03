from enum import Enum
from typing import Optional

from .governance import RuleRegistry, SystemLock


class RuntimeAction(str, Enum):
    EXECUTE = "EXECUTE"
    AUDIT = "AUDIT"
    REQUEUE = "REQUEUE"
    QUEUE = "QUEUE"
    IGNORE = "IGNORE"


class ActionDispatcher:
    """Governance kernel for runtime execution decisions.

    This dispatcher is the single enforcement checkpoint in the pipeline.
    It mirrors P4 decisions, validates invariants, enforces the system lock,
    and routes the final execution outcome.
    """

    def __init__(
        self,
        execution_gate=None,
        ledger=None,
        logger=None,
        audit_logger=None,
        lock: Optional[SystemLock] = None,
        registry: Optional[RuleRegistry] = None,
    ):
        self.gate = execution_gate
        self.ledger = ledger
        self.logger = logger
        self.audit_logger = audit_logger
        self.queue = []
        self.lock = lock or SystemLock()
        self.registry = registry or RuleRegistry()
        self._register_default_invariants()

    def _register_default_invariants(self):
        from .governance import (
            invariant_bridge_is_observer,
            invariant_dispatch_after_gate,
            invariant_no_direct_execution,
            invariant_p4_is_authority,
        )

        self.registry.register("no_direct_execution", invariant_no_direct_execution)
        self.registry.register("p4_is_authority", invariant_p4_is_authority)
        self.registry.register("bridge_is_observer", invariant_bridge_is_observer)
        self.registry.register("dispatch_after_gate", invariant_dispatch_after_gate)

    def dispatch(self, ticket, policy_result, gate_result):
        if self.gate is not None:
            gate_result = self.gate.apply(ticket, policy_result)

        mirrored_policy = self._policy_mirror(policy_result)
        context = self._build_governance_context(ticket, mirrored_policy, gate_result)

        if not self._enforce_system_lock(context):
            self._audit_violation(ticket, context, "system_lock_failure")
            return RuntimeAction.AUDIT

        violations = self._validate_invariants(context)
        if violations:
            self._audit_violation(ticket, context, "invariant_violation", violations)
            return RuntimeAction.AUDIT

        action = gate_result.get("action")

        if action == "SIMULATE_EXECUTION":
            self._simulate(ticket)
            result = RuntimeAction.EXECUTE

        elif action == "LOG_ONLY":
            self._log(ticket)
            result = RuntimeAction.AUDIT

        elif action == "REQUEUE_TO_HAL":
            self._requeue(ticket)
            result = RuntimeAction.REQUEUE

        elif action == "QUEUE_LATER":
            self.queue.append(ticket)
            result = RuntimeAction.QUEUE

        else:
            self._log(ticket, prefix="UNKNOWN ACTION")
            result = RuntimeAction.IGNORE

        self._audit_dispatch(ticket, context, action, result)
        return result

    def _policy_mirror(self, policy_result):
        return {
            "final_verdict": getattr(policy_result.final_verdict, "value", policy_result.final_verdict),
            "risk_score": policy_result.risk_score,
            "rule_triggered": policy_result.rule_triggered,
            "override_bridge": policy_result.override_bridge,
        }

    def _build_governance_context(self, ticket, policy_data, gate_result):
        return {
            "policy_verdict": policy_data["final_verdict"],
            "policy_risk": policy_data["risk_score"],
            "policy_rule": policy_data["rule_triggered"],
            "policy_override": policy_data["override_bridge"],
            "authority": "P4",
            "bridge_final": False,
            "gate_action": gate_result.get("action") if gate_result else None,
            "direct_execution": False,
            "policy_override_attempt": False,
        }

    def _enforce_system_lock(self, context):
        return self.lock.enforce(context)

    def _validate_invariants(self, context):
        return self.registry.validate(context)

    def _audit_violation(self, ticket, context, reason, violations=None):
        prefix = "GOVERNANCE VIOLATION"
        message = f"[{prefix}] {ticket.proposal.intent} | reason={reason}"
        if violations:
            message += f" | violations={violations}"
        self._audit_log(message)

    def _audit_dispatch(self, ticket, context, action, result):
        prefix = "DISPATCH"
        message = f"[{prefix}] {ticket.proposal.intent} -> {action} -> {result}"
        self._audit_log(message)

    def _audit_log(self, message: str):
        if self.logger:
            self.logger(message)
        else:
            print(message)

    def _simulate(self, ticket):
        self._log(ticket, prefix="SIMULATION")

    def _log(self, ticket, prefix="LOG ONLY"):
        message = f"[{prefix}] {ticket.proposal.intent}"
        if self.logger:
            self.logger(message)
        else:
            print(message)

    def _requeue(self, ticket):
        self._log(ticket, prefix="REQUEUE")
        # Requeue logic should be implemented in HAL control loop later.
