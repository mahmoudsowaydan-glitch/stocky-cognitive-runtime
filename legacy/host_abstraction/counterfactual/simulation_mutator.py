from typing import List, Any

from host_abstraction.replay.decision_reconstructor import ReconstructedStep
from host_abstraction.counterfactual.intervention_model import Intervention


class SimulationMutator:
    def apply(self, timeline: List[ReconstructedStep], intervention: Intervention) -> List[dict]:
        mutated: List[dict] = []

        for step in timeline:
            payload = dict(step.payload)

            if intervention.confidence is not None and "confidence" in payload:
                payload["confidence"] = intervention.confidence

            if intervention.risk_level is not None and "risk_level" in payload:
                payload["risk_level"] = intervention.risk_level

            if intervention.policy_threshold is not None:
                payload["policy_threshold"] = intervention.policy_threshold

            mutated.append({
                "stage": step.layer,
                "event_type": step.event_type,
                "entity_id": step.entity_id,
                "timestamp": step.timestamp,
                "payload": payload,
            })

        return mutated
