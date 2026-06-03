"""
runtime_distorter.py — Distorts injected runtime dependencies.

Wraps p3_context_builder, p4_authority, and SandboxPool to inject:
- Latency spikes
- Random failures / exceptions
- Hang simulation
- Bad return values
"""

import asyncio
import random
import time
from typing import Any, Callable, Optional

from ..harness.chaos_profile import InjectorConfig


class P3Distorter:
    """Wraps the p3_context_builder (HostEvent → ExecutionProposal) callable."""

    def __init__(self, inner: Callable, config: InjectorConfig, seed: Optional[int] = None):
        self._inner = inner
        self._config = config
        self._rng = random.Random(seed)

    async def __call__(self, event: Any) -> Any:
        await self._simulate_latency()
        if self._rng.random() < self._config.failure_rate:
            raise RuntimeError("CHAOS: p3_context_builder injected failure")
        return await self._inner(event)

    async def _simulate_latency(self):
        if self._config.latency_mean > 0:
            jitter = self._rng.uniform(0, self._config.latency_jitter)
            total = self._config.latency_mean + jitter
            await asyncio.sleep(total)


class P4Distorter:
    """Wraps the p4_authority (ExecutionProposal → PolicyDecision) callable."""

    def __init__(self, inner: Callable, config: InjectorConfig, seed: Optional[int] = None):
        self._inner = inner
        self._config = config
        self._rng = random.Random(seed)
        self._hang_notified = False

    async def __call__(self, proposal: Any) -> Any:
        if self._rng.random() < self._config.hang_probability:
            if not self._hang_notified:
                self._hang_notified = True
            await asyncio.sleep(3600)
            return None
        await self._simulate_latency()
        if self._rng.random() < self._config.failure_rate:
            raise RuntimeError("CHAOS: p4_authority injected failure")
        return await self._inner(proposal)

    async def _simulate_latency(self):
        if self._config.latency_mean > 0:
            jitter = self._rng.uniform(0, self._config.latency_jitter)
            total = self._config.latency_mean + jitter
            await asyncio.sleep(total)


class SandboxDistorter:
    """Wraps SandboxPool.execute to inject execution faults."""

    def __init__(self, inner: Any, config: InjectorConfig, seed: Optional[int] = None):
        self._inner = inner
        self._config = config
        self._rng = random.Random(seed)
        self._original_execute = inner.execute

    async def execute(self, proposal: Any, decision: Any) -> Any:
        if self._rng.random() < self._config.hang_probability:
            await asyncio.sleep(3600)
            return None
        await self._simulate_latency()
        if self._rng.random() < self._config.failure_rate:
            raise RuntimeError("CHAOS: sandbox execute injected failure")
        return await self._original_execute(proposal, decision)

    async def acquire(self, *args, **kwargs):
        return await self._inner.acquire(*args, **kwargs)

    def release(self, cell):
        self._inner.release(cell)

    @property
    def available_count(self):
        return self._inner.available_count

    async def _simulate_latency(self):
        if self._config.latency_mean > 0:
            jitter = self._rng.uniform(0, self._config.latency_jitter)
            total = self._config.latency_mean + jitter
            await asyncio.sleep(total)


def distort_runtime_deps(p3: Callable, p4: Callable, pool: Any,
                         config: InjectorConfig, seed: Optional[int] = None):
    """Apply distortion wrappers to all three runtime dependencies."""
    return (
        P3Distorter(p3, config, seed),
        P4Distorter(p4, config, seed),
        SandboxDistorter(pool, config, seed),
    )
