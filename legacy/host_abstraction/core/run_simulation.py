from datetime import datetime

from .contracts import HostEvent, HostEventSource, WorkspaceState
from .simulated_adapter import SimulatedAdapter
from ..bridges import ArbitrationEvent, ExecutionArbitrationBridge
from ..state import HALSessionState, HALCognitiveLoop, IntentHypothesisGenerator


def main() -> None:
    adapter = SimulatedAdapter(host_id="sim-host-1", initial_root="/workspace")
    session_state = HALSessionState()
    bridge = ExecutionArbitrationBridge()
    cognitive_loop = HALCognitiveLoop(session_state, IntentHypothesisGenerator(), arbitration_bridge=bridge)

    def on_host_event(event: HostEvent) -> None:
        print(f"[HostEvent] {event.source.value} {event.type} {event.payload} {event.timestamp.isoformat()}")

    def on_execution_proposal(proposal) -> None:
        intent = proposal.intent
        print(
            f"[ExecutionProposal] intent={intent.intent_type} confidence={proposal.confidence:.2f} "
            f"risk={proposal.risk_level.value} caps={proposal.required_capabilities} "
            f"suggested_path={proposal.suggested_runtime_path}"
        )

    def on_arbitration_event(event: ArbitrationEvent) -> None:
        ticket = event.ticket
        verdict_value = ticket.final_verdict.value if ticket.final_verdict else "UNKNOWN"
        print(
            f"[ArbitrationEvent] verdict={verdict_value} status={ticket.status} "
            f"proposal_id={ticket.proposal_id} notes={ticket.notes}"
        )

    adapter.register_listener(on_host_event)
    adapter.register_listener(cognitive_loop.process_host_event)
    cognitive_loop.register_listener(on_execution_proposal)
    bridge.register_listener(on_arbitration_event)

    adapter.connect()

    workspace = adapter.get_workspace_state()
    print(f"Workspace state: root={workspace.workspace_root} active={workspace.active_files}")

    adapter.emit_event(
        HostEvent(
            source=HostEventSource.HEADLESS,
            type="file.opened",
            payload={"path": "/workspace/main.py"},
            timestamp=datetime.utcnow(),
        )
    )

    result = adapter.execute_command("format_document", {"path": "/workspace/main.py"})
    print(f"Command result: {result}")

    adapter.disconnect()


if __name__ == "__main__":
    main()
