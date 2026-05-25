from typing import Optional

from ..agents_bridge.agent_runtime_adapter import AgentRuntimeAdapter
from ..agents_bridge.orchestration_layer import AgentOrchestrationLayer
from ..control_bridge.control_adapter import ControlAdapter
from ..core.lifecycle_manager import LifecycleManager
from ..core.orchestrator import CentralOrchestrator
from ..doctrine.doctrine_engine import DoctrineEngine
from ..doctrine.law_interpreter import LawInterpreterEngine
from ..events.event_bus import EventBus
from ..memory.memory_bridge import MemoryBridge
from ..observation.live_observer import LiveObserver
from ..observation.runtime_metrics import RuntimeMetrics
from .runtime_config import RuntimeConfig


class KernelInitializer:
    def __init__(self, config: Optional[RuntimeConfig] = None):
        self.config = config or RuntimeConfig.default()
        self.orchestrator: Optional[CentralOrchestrator] = None
        self.event_bus: Optional[EventBus] = None
        self.observer: Optional[LiveObserver] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.memory: Optional[MemoryBridge] = None
        self.doctrine: Optional[DoctrineEngine] = None
        self.control: Optional[ControlAdapter] = None
        self.agents: Optional[AgentOrchestrationLayer] = None
        self.lifecycle: Optional[LifecycleManager] = None

    def initialize(self) -> CentralOrchestrator:
        self.event_bus = EventBus()
        self.observer = LiveObserver()
        self.metrics = RuntimeMetrics()
        self.memory = MemoryBridge()
        self.doctrine = DoctrineEngine()
        self.control = ControlAdapter()

        self.agents = AgentOrchestrationLayer()
        if self.config.agent_auto_register:
            self._register_default_agents()

        self.orchestrator = CentralOrchestrator()
        self.orchestrator.doctrine_engine = self.doctrine
        self.orchestrator.control_bridge = self.control
        self.orchestrator.agent_layer = self.agents
        self.orchestrator.memory = self.memory
        self.orchestrator.observer = self.observer
        self.orchestrator.event_bus = self.event_bus

        self.lifecycle = LifecycleManager(self.event_bus, self.observer)

        return self.orchestrator

    def _register_default_agents(self) -> None:
        if not self.agents:
            return
        default_agents = [
            ("architect", "Architecture Analysis", ["analysis", "design"]),
            ("runtime_agent", "Runtime Execution", ["execution"]),
            ("security_agent", "Security Validation", ["security", "validation"]),
            ("debug_agent", "Debug Analysis", ["debug", "analysis"]),
            ("optimization_agent", "Performance Optimization", ["analysis", "optimization"]),
            ("qa_agent", "Quality Assurance", ["validation", "testing"]),
            ("research_agent", "Knowledge Research", ["analysis", "research"]),
            ("coherence_agent", "System Identity", ["validation", "coherence"]),
            ("integrity_agent", "System Integrity", ["validation", "security"]),
        ]
        for name, role, caps in default_agents:
            self.agents.register_agent(name, role, caps)
