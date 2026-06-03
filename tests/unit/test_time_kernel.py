import time
from cognitive_runtime.kernel.time_kernel import TimeKernel, TimeStamp


class TestTimeStamp:
    def test_create(self):
        ts = TimeStamp(
            session_id="s1",
            sequence_no=1,
            event_id="e1",
            wall_time=1000.0,
            parent_event_id=None,
        )
        assert ts.session_id == "s1"
        assert ts.sequence_no == 1
        assert ts.event_id == "e1"
        assert ts.wall_time == 1000.0
        assert ts.parent_event_id is None

    def test_causal_id(self):
        ts = TimeStamp(session_id="s1", sequence_no=5, event_id="e1", wall_time=0.0)
        assert ts.causal_id == "s1:5"

    def test_happens_before_same_session(self):
        early = TimeStamp(session_id="s1", sequence_no=1, event_id="e1", wall_time=0.0)
        late = TimeStamp(session_id="s1", sequence_no=2, event_id="e2", wall_time=0.0)
        assert early.happens_before(late)
        assert not late.happens_before(early)

    def test_happens_before_different_session(self):
        a = TimeStamp(session_id="s1", sequence_no=1, event_id="e1", wall_time=100.0)
        b = TimeStamp(session_id="s2", sequence_no=1, event_id="e2", wall_time=200.0)
        assert a.happens_before(b)
        assert not b.happens_before(a)

    def test_happens_before_same_sequence_same_session(self):
        a = TimeStamp(session_id="s1", sequence_no=1, event_id="e1", wall_time=100.0)
        b = TimeStamp(session_id="s1", sequence_no=1, event_id="e2", wall_time=200.0)
        assert not a.happens_before(b)
        assert not b.happens_before(a)


class TestTimeKernel:
    def test_stamp_returns_correct_session_and_counter(self):
        tk = TimeKernel(session_id="fixed-session")
        ts = tk.stamp("e1")
        assert ts.session_id == "fixed-session"
        assert ts.sequence_no == 1
        assert ts.event_id == "e1"

    def test_stamp_increments_counter(self):
        tk = TimeKernel(session_id="s")
        assert tk.stamp("e1").sequence_no == 1
        assert tk.stamp("e2").sequence_no == 2
        assert tk.stamp("e3").sequence_no == 3

    def test_get_returns_stamp(self):
        tk = TimeKernel(session_id="s")
        ts = tk.stamp("e1")
        assert tk.get("e1") is ts

    def test_get_returns_none_for_unknown(self):
        tk = TimeKernel(session_id="s")
        assert tk.get("nonexistent") is None

    def test_sequence_of(self):
        tk = TimeKernel(session_id="s")
        tk.stamp("e1")
        tk.stamp("e2")
        assert tk.sequence_of("e1") == 1
        assert tk.sequence_of("e2") == 2

    def test_sequence_of_unknown(self):
        tk = TimeKernel(session_id="s")
        assert tk.sequence_of("nonexistent") is None

    def test_is_after_true(self):
        tk = TimeKernel(session_id="s")
        tk.stamp("e1")
        tk.stamp("e2")
        assert tk.is_after("e2", "e1") is True

    def test_is_after_false(self):
        tk = TimeKernel(session_id="s")
        tk.stamp("e1")
        tk.stamp("e2")
        assert tk.is_after("e1", "e2") is False

    def test_is_after_none_for_unknown(self):
        tk = TimeKernel(session_id="s")
        tk.stamp("e1")
        assert tk.is_after("e1", "nonexistent") is None
        assert tk.is_after("nonexistent", "e1") is None
        assert tk.is_after("unknown1", "unknown2") is None

    def test_timeline_returns_all(self):
        tk = TimeKernel(session_id="s")
        tk.stamp("e1")
        tk.stamp("e2")
        tk.stamp("e3")
        tl = tk.timeline()
        assert len(tl) == 3
        assert [ts.sequence_no for ts in tl] == [1, 2, 3]

    def test_timeline_since_seq(self):
        tk = TimeKernel(session_id="s")
        tk.stamp("e1")
        tk.stamp("e2")
        tk.stamp("e3")
        tl = tk.timeline(since_seq=1)
        assert len(tl) == 2
        assert [ts.sequence_no for ts in tl] == [2, 3]

    def test_replay_window(self):
        tk = TimeKernel(session_id="s")
        tk.stamp("e1")
        tk.stamp("e2")
        tk.stamp("e3")
        tk.stamp("e4")
        rw = tk.replay_window(2, 3)
        assert len(rw) == 2
        assert [ts.sequence_no for ts in rw] == [2, 3]

    def test_current_sequence_property(self):
        tk = TimeKernel(session_id="s")
        assert tk.current_sequence == 0
        tk.stamp("e1")
        assert tk.current_sequence == 1
        tk.stamp("e2")
        assert tk.current_sequence == 2

    def test_event_count_property(self):
        tk = TimeKernel(session_id="s")
        assert tk.event_count == 0
        tk.stamp("e1")
        assert tk.event_count == 1
        tk.stamp("e2")
        tk.stamp("e3")
        assert tk.event_count == 3

    def test_reset_clears_all_state(self):
        tk = TimeKernel(session_id="s")
        tk.stamp("e1")
        tk.stamp("e2")
        tk.reset()
        assert tk.current_sequence == 0
        assert tk.event_count == 0
        assert tk.get("e1") is None
        assert tk.get("e2") is None
        assert tk.timeline() == []

    def test_stamp_with_parent(self):
        tk = TimeKernel(session_id="s")
        ts = tk.stamp("e2", parent_event_id="e1")
        assert ts.parent_event_id == "e1"

    def test_default_session_id_is_generated(self):
        tk1 = TimeKernel()
        tk2 = TimeKernel()
        assert tk1.session_id != tk2.session_id
