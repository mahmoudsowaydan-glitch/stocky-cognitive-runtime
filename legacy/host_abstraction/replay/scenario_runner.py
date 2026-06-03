from typing import Dict, Any, List

from host_abstraction.replay.decision_reconstructor import ReconstructedStep


class ScenarioRunner:
    def apply_modifications(self, timeline: List[ReconstructedStep], modifications: Dict[str, Any]) -> List[ReconstructedStep]:
        modified_timeline: List[ReconstructedStep] = []

        for step in timeline:
            payload = dict(step.payload)

            if step.layer == "HAL" and step.event_type == "proposal":
                if "confidence" in modifications:
                    payload["confidence"] = modifications["confidence"]
                if "risk_level" in modifications:
                    payload["risk_level"] = modifications["risk_level"]
                if "intent" in modifications:
                    payload["intent"] = modifications["intent"]

            modified_timeline.append(
                ReconstructedStep(
                    layer=step.layer,
                    event_type=step.event_type,
                    entity_id=step.entity_id,
                    timestamp=step.timestamp,
                    payload=payload,
                )
            )

        return modified_timeline

    def run_what_if(
        self,
        reconstructed: Dict[str, Any],
        modifications: Dict[str, Any],
        pipeline_executor=None,
    ) -> Dict[str, Any]:
        timeline = reconstructed.get("timeline", [])
        modified_timeline = self.apply_modifications(timeline, modifications)

        result: Dict[str, Any] = {
            "original": reconstructed,
            "modifications": modifications,
            "modified_timeline": modified_timeline,
        }

        if pipeline_executor is not None:
            proposal_payload = self._find_proposal_payload(modified_timeline)
            if proposal_payload is not None:
                result["pipeline_result"] = pipeline_executor(proposal_payload)

        return result

    def _find_proposal_payload(self, timeline: List[ReconstructedStep]) -> Any:
        for step in timeline:
            if step.layer == "HAL" and step.event_type == "proposal":
                return step.payload
        return None
