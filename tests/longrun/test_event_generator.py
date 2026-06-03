import random

from cognitive_runtime.epoch.event_generator import (
    BASE_WEIGHTS,
    EventGenerator,
    EventProfile,
)


class TestEventGenerator:
    def test_generates_profiles(self):
        gen = EventGenerator(seed=42)
        profiles = gen.generate(cycle_count=1)
        assert len(profiles) >= 1
        assert all(isinstance(p, EventProfile) for p in profiles)

    def test_generates_multiple_per_cycle(self):
        gen = EventGenerator(seed=99)
        all_counts = set()
        for i in range(200):
            profiles = gen.generate(cycle_count=i)
            all_counts.add(len(profiles))
        assert 1 in all_counts
        assert 2 in all_counts or 3 in all_counts

    def test_deterministic_reproduction_same_seed(self):
        gen1 = EventGenerator(seed=42)
        gen2 = EventGenerator(seed=42)
        profiles1 = [gen1.generate(i) for i in range(50)]
        profiles2 = [gen2.generate(i) for i in range(50)]
        types1 = [p.event_type for batch in profiles1 for p in batch]
        types2 = [p.event_type for batch in profiles2 for p in batch]
        assert types1 == types2

    def test_deterministic_reproduction_different_seed(self):
        gen1 = EventGenerator(seed=42)
        gen2 = EventGenerator(seed=99)
        profiles1 = [gen1.generate(i) for i in range(50)]
        profiles2 = [gen2.generate(i) for i in range(50)]
        types1 = [p.event_type for batch in profiles1 for p in batch]
        types2 = [p.event_type for batch in profiles2 for p in batch]
        assert types1 != types2

    def test_distribution_coverage(self):
        gen = EventGenerator(seed=42)
        seen_types = set()
        for i in range(1000):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                seen_types.add(p.event_type)
        assert "NORMAL" in seen_types
        assert "HIGH_RISK" in seen_types
        assert "CONFLICT" in seen_types
        assert "MIGRATION" in seen_types
        assert "ANOMALY" in seen_types
        assert "CHAOS" in seen_types
        assert "RESOURCE_PRESSURE" in seen_types

    def test_recovery_after_consecutive_failures(self):
        gen = EventGenerator(seed=42)
        assert gen._consecutive_failures == 0
        gen._consecutive_failures = 5
        for _ in range(20):
            profiles = gen.generate(cycle_count=3000)
            if any(p.event_type == "RECOVERY" for p in profiles):
                return
        assert False, "No RECOVERY event generated after 5 consecutive failures"

    def test_normal_event_profile(self):
        gen = EventGenerator(seed=42)
        normal_found = False
        for i in range(500):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                if p.event_type == "NORMAL":
                    normal_found = True
                    assert p.preflight_valid in (True, False)
                    assert p.p4_verdict in ("ALLOW", "DENY")
                    assert p.execution_status in ("SUCCESS", "FAILURE")
                    assert 0.0 <= p.risk_score <= 0.5
                    assert p.p4_rule_triggered is None
                    assert p.final_status == ""
                    return
        assert normal_found

    def test_high_risk_event_profile(self):
        gen = EventGenerator(seed=42)
        for i in range(500):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                if p.event_type == "HIGH_RISK":
                    assert p.preflight_valid is True
                    assert p.p4_verdict == "ALLOW"
                    assert p.execution_status in ("SUCCESS", "FAILED")
                    assert 0.70 <= p.risk_score <= 0.99
                    return

    def test_conflict_event_profile(self):
        gen = EventGenerator(seed=42)
        for i in range(500):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                if p.event_type == "CONFLICT":
                    assert p.preflight_valid is True
                    assert p.p4_verdict == "ALLOW"
                    assert p.execution_status == "SUCCESS"
                    assert p.risk_score >= 0.85
                    return

    def test_migration_event_profile(self):
        gen = EventGenerator(seed=42)
        for i in range(500):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                if p.event_type == "MIGRATION":
                    assert "SCHEMA_WRITE" in p.capabilities_checked
                    assert "MIGRATION_EXECUTE" in p.capabilities_checked
                    assert p.p4_verdict in ("ALLOW", "REVIEW")
                    return

    def test_anomaly_event_profile(self):
        gen = EventGenerator(seed=42)
        for i in range(500):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                if p.event_type == "ANOMALY":
                    assert p.preflight_valid is False
                    assert p.p4_verdict == "UNKNOWN"
                    assert p.execution_status == "UNKNOWN"
                    assert p.final_status == "BLOCKED_BY_PREFLIGHT"
                    return

    def test_chaos_event_profile(self):
        gen = EventGenerator(seed=42)
        seen_block = False
        seen_fail = False
        for i in range(1000):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                if p.event_type == "CHAOS":
                    if p.p4_verdict == "BLOCK":
                        assert p.final_status == "P4_BLOCK"
                        assert p.p4_rule_triggered == "CAPABILITY_ESCALATION"
                        seen_block = True
                    else:
                        assert p.execution_status == "FAILED"
                        assert p.execution_error == "chaotic_failure"
                        seen_fail = True
        assert seen_block and seen_fail

    def test_resource_pressure_event_profile(self):
        gen = EventGenerator(seed=42)
        for i in range(500):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                if p.event_type == "RESOURCE_PRESSURE":
                    assert p.p4_verdict in ("REVIEW", "DEFER", "BLOCK")
                    assert p.final_status.startswith("P4_")
                    assert p.p4_rule_triggered is not None
                    assert 0.60 <= p.risk_score <= 0.85
                    return

    def test_recovery_event_profile(self):
        gen = EventGenerator(seed=42)
        gen._consecutive_failures = 5
        for i in range(200):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                if p.event_type == "RECOVERY":
                    assert p.preflight_valid is True
                    assert p.p4_verdict == "ALLOW"
                    assert p.execution_status == "SUCCESS"
                    assert 0.0 <= p.risk_score <= 0.15
                    return

    def test_distribution_schedule_shifts_over_time(self):
        gen = EventGenerator(seed=42)
        early_types = []
        for i in range(100):
            for p in gen.generate(cycle_count=i):
                early_types.append(p.event_type)
        late_types = []
        for i in range(3000, 3100):
            for p in gen.generate(cycle_count=i):
                late_types.append(p.event_type)
        early_normal_ratio = early_types.count("NORMAL") / max(1, len(early_types))
        late_normal_ratio = late_types.count("NORMAL") / max(1, len(late_types))
        assert early_normal_ratio > late_normal_ratio, (
            f"Early NORMAL ratio {early_normal_ratio:.3f} should be > late {late_normal_ratio:.3f}"
        )

    def test_reset_consecutive_failures(self):
        gen = EventGenerator(seed=42)
        gen._consecutive_failures = 10
        gen.reset_consecutive_failures()
        assert gen._consecutive_failures == 0

    def test_distribution_within_tolerance(self):
        gen = EventGenerator(seed=42)
        counts: dict = {}
        total = 0
        for i in range(6000, 8000):
            profiles = gen.generate(cycle_count=i)
            for p in profiles:
                counts[p.event_type] = counts.get(p.event_type, 0) + 1
                total += 1

        total_weight = sum(BASE_WEIGHTS.values())
        for etype, expected_weight in BASE_WEIGHTS.items():
            ratio = counts.get(etype, 0) / max(1, total)
            expected_ratio = expected_weight / total_weight
            assert abs(ratio - expected_ratio) < 0.10, (
                f"{etype}: expected {expected_ratio:.3f}, got {ratio:.3f}"
            )
