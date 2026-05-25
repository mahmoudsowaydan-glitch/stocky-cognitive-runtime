from dataclasses import dataclass


@dataclass
class StabilityScore:
    score: float
    variance: float
    confidence: float
    interpretation: str
