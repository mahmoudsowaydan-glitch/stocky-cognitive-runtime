from typing import Optional

from .kernel_initializer import KernelInitializer
from .runtime_config import RuntimeConfig
from ..core.runtime_engine import RuntimeEngine


class SystemBootloader:
    def __init__(self, config: Optional[RuntimeConfig] = None):
        self.config = config or RuntimeConfig.default()
        self.initializer = KernelInitializer(self.config)
        self.engine: Optional[RuntimeEngine] = None

    def boot(self) -> RuntimeEngine:
        orchestrator = self.initializer.initialize()
        self.engine = RuntimeEngine(
            orchestrator=orchestrator,
            event_bus=self.initializer.event_bus,
            observer=self.initializer.observer,
            metrics=self.initializer.metrics,
        )
        return self.engine

    def boot_and_run(self, max_iterations: int = 0) -> RuntimeEngine:
        engine = self.boot()
        if self.config.autoboot:
            engine.run_forever(max_iterations=max_iterations)
        return engine


def create_system(config: Optional[RuntimeConfig] = None) -> RuntimeEngine:
    bootloader = SystemBootloader(config)
    return bootloader.boot()


def run_system(config: Optional[RuntimeConfig] = None, max_iterations: int = 0) -> RuntimeEngine:
    bootloader = SystemBootloader(config)
    return bootloader.boot_and_run(max_iterations=max_iterations)
