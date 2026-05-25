from typing import Dict, Iterable


class SensitivityMatrix:
    def compute(self, results: Iterable[str]) -> Dict[str, float]:
        changes: Dict[str, int] = {
            "ALLOW": 0,
            "BLOCK": 0,
            "DEFER": 0,
            "REVIEW": 0,
            "UNKNOWN": 0,
        }

        for r in results:
            key = str(r).upper()
            if key in changes:
                changes[key] += 1
            else:
                changes["UNKNOWN"] += 1

        total = sum(changes.values()) or 1
        return {k: v / total for k, v in changes.items()}
