from host_abstraction.replay.trace_loader import TraceLoader
from host_abstraction.replay.decision_reconstructor import DecisionReconstructor
from host_abstraction.replay.replay_report import ReplayReport


class ReplayEngine:
    def __init__(self, audit_store):
        self.loader = TraceLoader(audit_store)
        self.reconstructor = DecisionReconstructor()
        self.reporter = ReplayReport()

    def replay(self, trace_id: str):
        events = self.loader.load(trace_id)
        reconstructed = self.reconstructor.rebuild(events)
        self.reporter.generate(reconstructed)
        return reconstructed
