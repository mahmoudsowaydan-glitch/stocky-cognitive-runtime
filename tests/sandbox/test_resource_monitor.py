import pytest

from cognitive_runtime.sandbox.resource_monitor import (
    ResourceMonitor,
    ResourceLimits,
    ResourceUsage,
    ResourceGuard,
)


class TestResourceLimits:
    def test_defaults(self):
        limits = ResourceLimits()
        assert limits.max_time_ms == 30000
        assert limits.max_operations == 100
        assert limits.max_memory_mb == 128

    def test_custom_values(self):
        limits = ResourceLimits(max_time_ms=5000, max_operations=10, max_memory_mb=256)
        assert limits.max_time_ms == 5000
        assert limits.max_operations == 10
        assert limits.max_memory_mb == 256

    def test_partial_custom(self):
        limits = ResourceLimits(max_operations=5)
        assert limits.max_time_ms == 30000
        assert limits.max_operations == 5
        assert limits.max_memory_mb == 128


class TestResourceUsage:
    def test_defaults(self):
        usage = ResourceUsage()
        assert usage.time_ms == 0.0
        assert usage.operations == 0
        assert usage.memory_mb == 0.0


class TestResourceGuard:
    def test_defaults(self):
        guard = ResourceGuard()
        assert isinstance(guard.limits, ResourceLimits)
        assert isinstance(guard.usage, ResourceUsage)
        assert guard.exceeded is False
        assert guard.violation == ""

    def test_custom_limits(self):
        limits = ResourceLimits(max_time_ms=1000)
        guard = ResourceGuard(limits=limits)
        assert guard.limits.max_time_ms == 1000


class TestResourceMonitor:
    def test_default_limits(self):
        monitor = ResourceMonitor()
        assert monitor.limits.max_time_ms == 30000
        assert monitor.limits.max_operations == 100

    def test_custom_limits(self):
        limits = ResourceLimits(max_time_ms=5000, max_operations=10)
        monitor = ResourceMonitor(limits=limits)
        assert monitor.limits.max_time_ms == 5000
        assert monitor.limits.max_operations == 10

    def test_pre_check_returns_none_for_normal(self):
        monitor = ResourceMonitor()
        assert monitor.pre_check({"action": "read", "confidence": 0.8}) is None

    def test_pre_check_returns_none_at_boundary(self):
        monitor = ResourceMonitor()
        assert monitor.pre_check({"action": "read", "confidence": 0.2}) is None

    def test_pre_check_never_blocks_on_confidence(self):
        monitor = ResourceMonitor()
        assert monitor.pre_check({"action": "read", "confidence": 0.19}) is None

    def test_pre_check_never_blocks_zero_confidence(self):
        monitor = ResourceMonitor()
        assert monitor.pre_check({"action": "read", "confidence": 0.0}) is None

    def test_pre_check_default_confidence(self):
        monitor = ResourceMonitor()
        assert monitor.pre_check({"action": "read"}) is None

    def test_create_guard(self):
        monitor = ResourceMonitor()
        guard = monitor.create_guard()
        assert isinstance(guard, ResourceGuard)
        assert guard.limits.max_time_ms == 30000

    def test_create_guard_with_custom_limits(self):
        limits = ResourceLimits(max_time_ms=1000)
        monitor = ResourceMonitor(limits=limits)
        guard = monitor.create_guard()
        assert guard.limits.max_time_ms == 1000

    def test_check_operation_increments_counter(self):
        monitor = ResourceMonitor()
        guard = monitor.create_guard()
        monitor.check_operation(guard)
        assert guard.usage.operations == 1
        monitor.check_operation(guard)
        assert guard.usage.operations == 2

    def test_check_operation_no_violation_within_limit(self):
        monitor = ResourceMonitor(limits=ResourceLimits(max_operations=5))
        guard = monitor.create_guard()
        for _ in range(5):
            result = monitor.check_operation(guard)
            assert result is None
        assert guard.exceeded is False

    def test_check_operation_violation_when_exceeding(self):
        monitor = ResourceMonitor(limits=ResourceLimits(max_operations=3))
        guard = monitor.create_guard()
        for _ in range(3):
            monitor.check_operation(guard)
        result = monitor.check_operation(guard)
        assert result is not None
        assert "max_operations_exceeded" in result
        assert guard.exceeded is True
        assert guard.violation == result

    def test_check_time_sets_elapsed(self):
        monitor = ResourceMonitor()
        guard = monitor.create_guard()
        monitor.check_time(guard, 123.0)
        assert guard.usage.time_ms == 123.0

    def test_check_time_no_violation_within_limit(self):
        monitor = ResourceMonitor(limits=ResourceLimits(max_time_ms=1000))
        guard = monitor.create_guard()
        result = monitor.check_time(guard, 999.0)
        assert result is None
        assert guard.exceeded is False

    def test_check_time_violation_exact_boundary(self):
        monitor = ResourceMonitor(limits=ResourceLimits(max_time_ms=1000))
        guard = monitor.create_guard()
        result = monitor.check_time(guard, 1000.0)
        assert result is None

    def test_check_time_violation_when_exceeding(self):
        monitor = ResourceMonitor(limits=ResourceLimits(max_time_ms=1000))
        guard = monitor.create_guard()
        result = monitor.check_time(guard, 1001.0)
        assert result is not None
        assert "max_time_exceeded" in result
        assert guard.exceeded is True

    def test_finalize_returns_summary_after_normal(self):
        monitor = ResourceMonitor(limits=ResourceLimits(max_time_ms=5000, max_operations=10))
        guard = monitor.create_guard()
        monitor.check_operation(guard)
        monitor.check_time(guard, 100.0)
        summary = monitor.finalize(guard)
        assert summary["limits"]["max_time_ms"] == 5000
        assert summary["limits"]["max_operations"] == 10
        assert summary["usage"]["time_ms"] == 100.0
        assert summary["usage"]["operations"] == 1
        assert summary["exceeded"] is False
        assert summary["violation"] == ""

    def test_finalize_returns_summary_after_violation(self):
        monitor = ResourceMonitor(limits=ResourceLimits(max_time_ms=100))
        guard = monitor.create_guard()
        monitor.check_time(guard, 200.0)
        summary = monitor.finalize(guard)
        assert summary["exceeded"] is True
        assert "max_time_exceeded" in summary["violation"]

    def test_finalize_with_multiple_operations(self):
        monitor = ResourceMonitor(limits=ResourceLimits(max_operations=5))
        guard = monitor.create_guard()
        for _ in range(6):
            monitor.check_operation(guard)
        summary = monitor.finalize(guard)
        assert summary["usage"]["operations"] == 6
        assert summary["exceeded"] is True
