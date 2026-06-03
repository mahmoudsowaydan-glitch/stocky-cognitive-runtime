from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EvictionPolicy(str, Enum):
    FIFO = "fifo"
    FAA = "faa"


@dataclass
class EvictionConfig:
    policy: EvictionPolicy = EvictionPolicy.FIFO
    max_patterns: int = 100_000
    max_failures: int = 50_000
    max_fingerprints: int = 50_000
    faa_current_cycle: int = 0
