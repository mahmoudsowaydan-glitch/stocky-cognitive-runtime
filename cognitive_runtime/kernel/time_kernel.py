import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimeStamp:
    session_id: str
    sequence_no: int
    event_id: str
    wall_time: float
    parent_event_id: Optional[str] = None

    @property
    def causal_id(self) -> str:
        return f"{self.session_id}:{self.sequence_no}"

    def happens_before(self, other: "TimeStamp") -> bool:
        if self.session_id != other.session_id:
            return self.wall_time < other.wall_time
        return self.sequence_no < other.sequence_no


@dataclass
class TimeKernel:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _counter: int = 0
    _timeline: list[TimeStamp] = field(default_factory=list)
    _event_map: dict[str, TimeStamp] = field(default_factory=dict)

    def stamp(self, event_id: str, parent_event_id: Optional[str] = None) -> TimeStamp:
        self._counter += 1
        ts = TimeStamp(
            session_id=self.session_id,
            sequence_no=self._counter,
            event_id=event_id,
            wall_time=time.time(),
            parent_event_id=parent_event_id,
        )
        self._timeline.append(ts)
        self._event_map[event_id] = ts
        return ts

    def get(self, event_id: str) -> Optional[TimeStamp]:
        return self._event_map.get(event_id)

    def sequence_of(self, event_id: str) -> Optional[int]:
        ts = self._event_map.get(event_id)
        return ts.sequence_no if ts else None

    def is_after(self, event_id_a: str, event_id_b: str) -> Optional[bool]:
        a = self._event_map.get(event_id_a)
        b = self._event_map.get(event_id_b)
        if not a or not b:
            return None
        return b.happens_before(a)

    def timeline(self, since_seq: int = 0) -> list[TimeStamp]:
        return [ts for ts in self._timeline if ts.sequence_no > since_seq]

    def replay_window(self, start_seq: int, end_seq: int) -> list[TimeStamp]:
        return [ts for ts in self._timeline if start_seq <= ts.sequence_no <= end_seq]

    @property
    def current_sequence(self) -> int:
        return self._counter

    @property
    def event_count(self) -> int:
        return len(self._timeline)

    def reset(self) -> None:
        self._counter = 0
        self._timeline.clear()
        self._event_map.clear()
