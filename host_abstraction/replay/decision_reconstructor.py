from dataclasses import dataclass
from typing import List, Any, Dict, Optional

from host_abstraction.audit.audit_event import AuditEvent


@dataclass
class ReconstructedStep:
    layer: str
    event_type: str
    entity_id: str
    timestamp: str
    payload: Dict[str, Any]


class DecisionReconstructor:
    def rebuild(self, events: List[AuditEvent]) -> Dict[str, Any]:
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        timeline: List[ReconstructedStep] = []

        for event in sorted_events:
            timeline.append(
                ReconstructedStep(
                    layer=event.layer,
                    event_type=event.event_type,
                    entity_id=event.entity_id,
                    timestamp=event.timestamp.isoformat(),
                    payload=event.payload,
                )
            )

        return {
            "timeline": timeline,
            "final_state": timeline[-1] if timeline else None,
            "snapshots": self._build_snapshots(timeline),
        }

    def _build_snapshots(self, timeline: List[ReconstructedStep]) -> Dict[str, Optional[Dict[str, Any]]]:
        snapshots: Dict[str, Optional[Dict[str, Any]]] = {
            "proposal": None,
            "arbitration": None,
            "policy_result": None,
            "gate_result": None,
            "runtime_dispatch": None,
        }

        for step in timeline:
            if step.layer == "HAL" and step.event_type == "proposal":
                snapshots["proposal"] = {
                    "entity_id": step.entity_id,
                    "payload": step.payload,
                }
            elif step.layer == "Bridge" and step.event_type == "observation":
                snapshots["arbitration"] = {
                    "entity_id": step.entity_id,
                    "payload": step.payload,
                }
            elif step.layer == "P4" and step.event_type == "decision":
                snapshots["policy_result"] = {
                    "entity_id": step.entity_id,
                    "payload": step.payload,
                }
            elif step.layer == "Gate" and step.event_type == "evaluation":
                snapshots["gate_result"] = {
                    "entity_id": step.entity_id,
                    "payload": step.payload,
                }
            elif step.layer == "Runtime" and step.event_type == "dispatch":
                snapshots["runtime_dispatch"] = {
                    "entity_id": step.entity_id,
                    "payload": step.payload,
                }

        return snapshots
