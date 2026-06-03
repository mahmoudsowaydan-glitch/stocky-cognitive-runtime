"""
schema_version.py — Semantic versioning for runtime contracts.

Provides:
  - SchemaVersion dataclass (major.minor.patch)
  - FROZEN_SCHEMA_VERSION — current frozen schema version
  - fingerprint() — deterministic hash of a contract's interface
  - compatibility check helpers
"""

import hashlib
import inspect
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SchemaVersion:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"

    def is_compatible_with(self, other: "SchemaVersion") -> bool:
        if self.major != other.major:
            return False
        if self.minor != other.minor:
            return False
        return True

    def is_backward_compatible(self, other: "SchemaVersion") -> bool:
        if self.major == other.major and self.minor == other.minor:
            return True
        if self.major == other.major and other.minor > self.minor:
            return True
        return False


# Current frozen schema version
# 1.0.0 → 1.1.0: Added Runtime Doctrine v1 (FROZEN/GUARDED/ADVISORY invariants),
#                     DoctrineRuntimeGuard, fixed INV-CONF-001 and INV-REC-001 violations.
FROZEN_SCHEMA_VERSION = SchemaVersion(major=1, minor=1, patch=0)
FROZEN_SCHEMA_VERSION_STR: str = str(FROZEN_SCHEMA_VERSION)


def fingerprint(obj: Any) -> str:
    attrs = {}
    for attr in dir(obj):
        if attr.startswith("_"):
            continue
        val = getattr(obj, attr)
        if inspect.ismethod(val) or inspect.isfunction(val):
            continue
        attrs[attr] = val
    raw = str(sorted(attrs.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fingerprint_class(cls: type) -> str:
    members: Dict[str, str] = {}
    for name, typ in cls.__annotations__.items():
        members[name] = str(typ)
    for name in dir(cls):
        if name.startswith("_"):
            continue
        val = getattr(cls, name)
        if inspect.isfunction(val) or inspect.ismethod(val):
            sig = inspect.signature(val)
            members[name] = str(sig)
    raw = str(sorted(members.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


ContractFingerprints: Dict[str, str] = {}


def register_fingerprint(name: str, fp: str) -> None:
    ContractFingerprints[name] = fp


def get_expected_fingerprint(name: str) -> Optional[str]:
    return ContractFingerprints.get(name)
