from typing import Any, Dict, List, Protocol

from host_abstraction.stability.drift_detector import DriftDetector
from host_abstraction.stability.sensitivity_matrix import SensitivityMatrix
from host_abstraction.stability.stability_score import StabilityScore


class PipelineExecutorProtocol(Protocol):
    def __call__(self, proposal_payload: Dict[str, Any]) -> Dict[str, Any]:
        ...


class StabilityEngine:
    def __init__(self):
        self.drift_detector = DriftDetector()
        self.sensitivity_matrix = SensitivityMatrix()

    def assess(self, baseline_results: List[str], current_results: List[str]) -> StabilityScore:
        baseline_distribution = self.sensitivity_matrix.compute(baseline_results)
        current_distribution = self.sensitivity_matrix.compute(current_results)

        distance = self._compare_distributions(baseline_distribution, current_distribution)
        score = max(0.0, 1.0 - distance)
        variance = self._compute_variance(current_distribution)
        confidence = max(0.0, 1.0 - variance)
        status = self.drift_detector.detect(baseline=1.0, current=score)

        interpretation = (
            "Decision stream is stable" if status["status"] == "STABLE" else "Potential instability detected"
        )

        return StabilityScore(
            score=score,
            variance=variance,
            confidence=confidence,
            interpretation=interpretation,
        )

    def _compare_distributions(self, baseline: Dict[str, float], current: Dict[str, float]) -> float:
        return sum(abs(baseline.get(k, 0.0) - current.get(k, 0.0)) for k in baseline) / 2.0

    def _compute_variance(self, distribution: Dict[str, float]) -> float:
        mean = sum(distribution.values()) / len(distribution)
        return sum((v - mean) ** 2 for v in distribution.values()) / len(distribution)
