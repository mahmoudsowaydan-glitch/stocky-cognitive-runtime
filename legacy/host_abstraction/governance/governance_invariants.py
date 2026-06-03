from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from host_abstraction.audit.audit_event import AuditEvent


@dataclass(frozen=True)
class GovernanceViolation:
    invariant: str
    reason: str
    layer: str
    entity_id: str
    event_type: str


def invariant_p4_is_single_authority(event: AuditEvent) -> Optional[GovernanceViolation]:
    if event.layer.lower() == "p4":
        if event.payload.get("policy_override", False) or event.payload.get("decision_mutation", False):
            decision_source = str(event.payload.get("decision_source", "")).lower()
            if decision_source != "p4":
                return GovernanceViolation(
                    invariant="invariant_p4_is_single_authority",
                    reason="P4 event contains a non-P4 decision source or override attempt.",
                    layer=event.layer,
                    entity_id=event.entity_id,
                    event_type=event.event_type,
                )

    if event.payload.get("decision") and event.layer.lower() != "p4":
        if event.payload.get("decision_source") and str(event.payload.get("decision_source", "")).lower() != "p4":
            return GovernanceViolation(
                invariant="invariant_p4_is_single_authority",
                reason="Decision content was generated outside P4 authority.",
                layer=event.layer,
                entity_id=event.entity_id,
                event_type=event.event_type,
            )

    return None


def invariant_stability_is_non_authoritative(event: AuditEvent) -> Optional[GovernanceViolation]:
    if event.layer.lower() != "stability":
        return None

    if event.payload.get("overrides_policy", False):
        return GovernanceViolation(
            invariant="invariant_stability_is_non_authoritative",
            reason="Stability layer attempted to override governance policy.",
            layer=event.layer,
            entity_id=event.entity_id,
            event_type=event.event_type,
        )

    if event.payload.get("mutates_runtime", False) or event.payload.get("injects_dispatch", False):
        return GovernanceViolation(
            invariant="invariant_stability_is_non_authoritative",
            reason="Stability layer attempted runtime mutation or dispatch injection.",
            layer=event.layer,
            entity_id=event.entity_id,
            event_type=event.event_type,
        )

    if event.event_type.lower() in {"dispatch_mutation", "runtime_state_change", "policy_override"}:
        return GovernanceViolation(
            invariant="invariant_stability_is_non_authoritative",
            reason="Stability layer emitted an authoritative event type.",
            layer=event.layer,
            entity_id=event.entity_id,
            event_type=event.event_type,
        )

    return None


def invariant_replay_is_read_only(event: AuditEvent) -> Optional[GovernanceViolation]:
    if event.layer.lower() != "replay":
        return None

    if event.payload.get("attempt_execution", False) or event.payload.get("dispatch_attempt", False):
        return GovernanceViolation(
            invariant="invariant_replay_is_read_only",
            reason="Replay layer attempted to execute or dispatch instead of only analyzing history.",
            layer=event.layer,
            entity_id=event.entity_id,
            event_type=event.event_type,
        )

    if event.payload.get("runtime_effect", False) or event.payload.get("state_change", False):
        return GovernanceViolation(
            invariant="invariant_replay_is_read_only",
            reason="Replay layer attempted a runtime or state-changing effect.",
            layer=event.layer,
            entity_id=event.entity_id,
            event_type=event.event_type,
        )

    return None


def invariant_counterfactual_is_sandboxed(event: AuditEvent) -> Optional[GovernanceViolation]:
    if event.layer.lower() != "counterfactual":
        return None

    if event.payload.get("runtime_effect", False) or event.payload.get("apply_to_runtime", False):
        return GovernanceViolation(
            invariant="invariant_counterfactual_is_sandboxed",
            reason="Counterfactual layer attempted to apply changes to runtime state.",
            layer=event.layer,
            entity_id=event.entity_id,
            event_type=event.event_type,
        )

    if event.event_type.lower() in {"runtime_mutation", "dispatch_override", "policy_override"}:
        return GovernanceViolation(
            invariant="invariant_counterfactual_is_sandboxed",
            reason="Counterfactual layer emitted an authoritative or runtime mutation event.",
            layer=event.layer,
            entity_id=event.entity_id,
            event_type=event.event_type,
        )

    return None


def invariant_dispatch_requires_gate(event: AuditEvent) -> Optional[GovernanceViolation]:
    if event.layer.lower() != "dispatcher":
        return None

    if not event.payload.get("gate_validated", False):
        return GovernanceViolation(
            invariant="invariant_dispatch_requires_gate",
            reason="Dispatcher event was emitted without gate validation.",
            layer=event.layer,
            entity_id=event.entity_id,
            event_type=event.event_type,
        )

    return None


def check_governance_invariants(event: AuditEvent) -> List[GovernanceViolation]:
    invariants: List[Callable[[AuditEvent], Optional[GovernanceViolation]]] = [
        invariant_p4_is_single_authority,
        invariant_stability_is_non_authoritative,
        invariant_replay_is_read_only,
        invariant_counterfactual_is_sandboxed,
        invariant_dispatch_requires_gate,
    ]

    violations: List[GovernanceViolation] = []
    for invariant in invariants:
        violation = invariant(event)
        if violation is not None:
            violations.append(violation)

    return violations
