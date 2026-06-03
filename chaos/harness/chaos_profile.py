"""
chaos_profile.py — Declarative Chaos Profiles.

Defines severity levels and composition rules for chaotic test scenarios.
Each profile controls which injectors are active and their intensity.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Severity(Enum):
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    EXTREME = "EXTREME"


@dataclass
class InjectorConfig:
    enabled: bool = False
    delay_range: tuple = (0.0, 0.0)
    corruption_rate: float = 0.0
    duplication_rate: float = 0.0
    failure_rate: float = 0.0
    latency_mean: float = 0.0
    latency_jitter: float = 0.0
    hang_probability: float = 0.0
    skew_seconds: float = 0.0


@dataclass
class ChaosProfile:
    severity: Severity
    name: str
    event_queue: InjectorConfig = field(default_factory=InjectorConfig)
    runtime_deps: InjectorConfig = field(default_factory=InjectorConfig)
    wal: InjectorConfig = field(default_factory=InjectorConfig)
    causal: InjectorConfig = field(default_factory=InjectorConfig)
    timing: InjectorConfig = field(default_factory=InjectorConfig)

    def active_injectors(self) -> List[str]:
        return [
            name for name, cfg in [
                ("event_queue", self.event_queue),
                ("runtime_deps", self.runtime_deps),
                ("wal", self.wal),
                ("causal", self.causal),
                ("timing", self.timing),
            ] if cfg.enabled
        ]

    @classmethod
    def light(cls) -> "ChaosProfile":
        return cls(
            severity=Severity.LIGHT,
            name="light",
            event_queue=InjectorConfig(
                enabled=True, delay_range=(0.01, 0.05), corruption_rate=0.05,
            ),
        )

    @classmethod
    def moderate(cls) -> "ChaosProfile":
        return cls(
            severity=Severity.MODERATE,
            name="moderate",
            event_queue=InjectorConfig(
                enabled=True, delay_range=(0.02, 0.15),
                corruption_rate=0.1, duplication_rate=0.05,
            ),
            runtime_deps=InjectorConfig(
                enabled=True, latency_mean=0.05, latency_jitter=0.05,
                failure_rate=0.1,
            ),
            timing=InjectorConfig(
                enabled=True, skew_seconds=0.01,
            ),
        )

    @classmethod
    def severe(cls) -> "ChaosProfile":
        return cls(
            severity=Severity.SEVERE,
            name="severe",
            event_queue=InjectorConfig(
                enabled=True, delay_range=(0.05, 0.3),
                corruption_rate=0.2, duplication_rate=0.1,
            ),
            runtime_deps=InjectorConfig(
                enabled=True, latency_mean=0.1, latency_jitter=0.1,
                failure_rate=0.2, hang_probability=0.05,
            ),
            wal=InjectorConfig(
                enabled=True, corruption_rate=0.15,
            ),
            causal=InjectorConfig(
                enabled=True, corruption_rate=0.1,
            ),
            timing=InjectorConfig(
                enabled=True, skew_seconds=0.1,
            ),
        )

    @classmethod
    def extreme(cls) -> "ChaosProfile":
        return cls(
            severity=Severity.EXTREME,
            name="extreme",
            event_queue=InjectorConfig(
                enabled=True, delay_range=(0.1, 0.5),
                corruption_rate=0.3, duplication_rate=0.2,
            ),
            runtime_deps=InjectorConfig(
                enabled=True, latency_mean=0.2, latency_jitter=0.2,
                failure_rate=0.3, hang_probability=0.1,
            ),
            wal=InjectorConfig(
                enabled=True, corruption_rate=0.3,
            ),
            causal=InjectorConfig(
                enabled=True, corruption_rate=0.2,
            ),
            timing=InjectorConfig(
                enabled=True, skew_seconds=0.5,
            ),
        )


# Registry for easy lookup
PROFILES: Dict[str, ChaosProfile] = {
    "light": ChaosProfile.light(),
    "moderate": ChaosProfile.moderate(),
    "severe": ChaosProfile.severe(),
    "extreme": ChaosProfile.extreme(),
}


def get_profile(name: str) -> ChaosProfile:
    if name not in PROFILES:
        raise ValueError(f"Unknown chaos profile: {name}. Choose from {list(PROFILES.keys())}")
    return PROFILES[name]
