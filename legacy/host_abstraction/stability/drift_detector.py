class DriftDetector:
    def detect(self, baseline: float, current: float):
        drift = abs(baseline - current)
        return {
            "drift_value": drift,
            "status": "DRIFT" if drift > 0.25 else "STABLE",
        }
