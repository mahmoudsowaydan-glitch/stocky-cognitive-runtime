from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os


@dataclass
class DecisionRecord:
    intent: str
    risk: float
    bridge_signal: str
    final_verdict: str
    rule_triggered: str
    reason: str
    timestamp: str


class DecisionLedger:

    def __init__(self, path: str = "p4_ledger.log") -> None:
        self.path = path

    def record(self, record: DecisionRecord) -> None:
        line = json.dumps(asdict(record), ensure_ascii=False)
        # make sure directory exists
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def load_all(self):
        if not os.path.exists(self.path):
            return []

        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f.readlines()]
