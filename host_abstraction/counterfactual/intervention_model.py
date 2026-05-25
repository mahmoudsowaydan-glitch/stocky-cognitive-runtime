from dataclasses import dataclass
from typing import Optional


@dataclass
class Intervention:
    confidence: Optional[float] = None
    risk_level: Optional[str] = None
    policy_threshold: Optional[float] = None
    description: str = "generic intervention"
