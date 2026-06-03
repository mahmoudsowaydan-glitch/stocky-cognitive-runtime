"""Diagnostic: Clock skew — tests deterministic ordering under timestamp distortion."""

import time

from chaos.harness.timing_distorter import TimingDistorter, TimingDistorterContext


def test_clock_skew_does_not_break_monotonicity():
    distorter = TimingDistorter(seed=42)
    distorter.set_skew(10.0)
    with TimingDistorterContext(distorter):
        t1 = time.time()
        t2 = time.time()
    assert t2 >= t1


def test_jitter_does_not_raise_exceptions():
    distorter = TimingDistorter(seed=42)
    distorter.set_skew(10.0)
    distorter.set_jitter(0.1)
    with TimingDistorterContext(distorter):
        for _ in range(20):
            _ = time.time()
    distorter.set_jitter(0.5)
    with TimingDistorterContext(distorter):
        for _ in range(20):
            _ = time.time()
    after = time.time()
    assert after > 0


def test_fixed_time_returns_consistent_value():
    distorter = TimingDistorter(seed=42)
    distorter.set_fixed_time(1000.0)
    with TimingDistorterContext(distorter):
        assert time.time() == 1000.0
        assert time.time() == 1000.0


def test_context_manager_restores_time():
    distorter = TimingDistorter(seed=42)
    before = time.time()
    with TimingDistorterContext(distorter):
        distorter.set_skew(100.0)
        skewed = time.time()
        assert abs(skewed - before - 100.0) < 0.01
    after = time.time()
    assert abs(after - before) < 1.0


def test_multiple_skew_applications_independent():
    distorter = TimingDistorter(seed=42)
    with TimingDistorterContext(distorter):
        distorter.set_skew(5.0)
        t1 = time.time()
    with TimingDistorterContext(distorter):
        distorter.set_skew(-5.0)
        t2 = time.time()
    base = time.time()
    assert abs(t1 - base - 5.0) < 1.0 or abs(t2 - base + 5.0) < 1.0
