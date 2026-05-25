from typing import Any, Dict, List, Optional

from host_abstraction.counterfactual.counterfactual_engine import CounterfactualEngine
from host_abstraction.counterfactual.intervention_model import Intervention
from host_abstraction.stability.stability_engine import PipelineExecutorProtocol


class StressTester:
    def run(
        self,
        counterfactual_engine: CounterfactualEngine,
        timeline: List[Any],
        pipeline_executor: Optional[PipelineExecutorProtocol] = None,
    ) -> List[Dict[str, Any]]:
        variations = [
            Intervention(confidence=0.1),
            Intervention(confidence=0.3),
            Intervention(confidence=0.5),
            Intervention(confidence=0.7),
            Intervention(confidence=0.9),
            Intervention(risk_level="LOW"),
            Intervention(risk_level="HIGH"),
            Intervention(risk_level="CRITICAL"),
            Intervention(confidence=0.25, risk_level="HIGH"),
            Intervention(confidence=0.75, risk_level="LOW"),
        ]

        results: List[Dict[str, Any]] = []

        for intervention in variations:
            report = counterfactual_engine.run(timeline, intervention)
            pipeline_result = None

            if pipeline_executor is not None:
                proposal_payload = self._find_proposal_payload(report["mutated"])
                if proposal_payload is not None:
                    pipeline_result = pipeline_executor(proposal_payload)

            results.append(
                {
                    "intervention": intervention,
                    "report": report,
                    "pipeline_result": pipeline_result,
                }
            )

        return results

    def _find_proposal_payload(self, mutated: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for step in mutated:
            if step.get("stage") == "HAL" and step.get("event_type") == "proposal":
                return step.get("payload")
        return None
