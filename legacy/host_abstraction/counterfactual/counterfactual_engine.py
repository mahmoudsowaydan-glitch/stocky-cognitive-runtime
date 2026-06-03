from host_abstraction.counterfactual.simulation_mutator import SimulationMutator
from host_abstraction.counterfactual.comparison_report import ComparisonReport
from host_abstraction.counterfactual.intervention_model import Intervention


class CounterfactualEngine:
    def __init__(self):
        self.mutator = SimulationMutator()
        self.reporter = ComparisonReport()

    def run(self, original_timeline, intervention: Intervention):
        mutated_timeline = self.mutator.apply(original_timeline, intervention)
        return self.reporter.compare(original_timeline, mutated_timeline)
