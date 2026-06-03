import pytest
from cognitive_runtime.intelligence.intelligence_store import (
    IntelligenceStore,
    Pattern,
    FailureSignature,
    DecisionFingerprint,
)


class TestPattern:
    def test_create(self):
        p = Pattern(
            pattern_id="pat_1", frequency=1,
            structure_signature="abc123", context_shape={"key": "val"},
        )
        assert p.pattern_id == "pat_1"
        assert p.frequency == 1
        assert p.structure_signature == "abc123"
        assert p.context_shape == {"key": "val"}

    def test_frozen(self):
        p = Pattern(pattern_id="p", frequency=0, structure_signature="s", context_shape={})
        with pytest.raises(AttributeError):
            p.pattern_id = "other"


class TestFailureSignature:
    def test_create(self):
        fs = FailureSignature(
            signature_id="fs_1", trigger_chain=["PREFLIGHT_BLOCK"],
            frequency=1, severity_distribution={"critical": 1},
        )
        assert fs.signature_id == "fs_1"
        assert fs.trigger_chain == ["PREFLIGHT_BLOCK"]
        assert fs.frequency == 1
        assert fs.severity_distribution == {"critical": 1}

    def test_frozen(self):
        fs = FailureSignature(
            signature_id="fs_1", trigger_chain=[], frequency=0, severity_distribution={},
        )
        with pytest.raises(AttributeError):
            fs.signature_id = "other"


class TestDecisionFingerprint:
    def test_create(self):
        fp = DecisionFingerprint(
            fingerprint_id="fp_1", p4_verdict="ALLOW",
            context_hash="hash1", capability_profile=["filesystem.read"],
        )
        assert fp.fingerprint_id == "fp_1"
        assert fp.p4_verdict == "ALLOW"
        assert fp.context_hash == "hash1"
        assert fp.capability_profile == ["filesystem.read"]

    def test_frozen(self):
        fp = DecisionFingerprint(
            fingerprint_id="fp_1", p4_verdict="ALLOW",
            context_hash="h", capability_profile=[],
        )
        with pytest.raises(AttributeError):
            fp.fingerprint_id = "other"


class TestIntelligenceStore:
    def test_create_defaults(self):
        store = IntelligenceStore()
        assert len(store.patterns) == 0
        assert len(store.failures) == 0
        assert len(store.fingerprints) == 0

    def test_create_custom_max(self):
        store = IntelligenceStore(max_patterns=1, max_failures=2, max_fingerprints=3)
        assert store._max_patterns == 1
        assert store._max_failures == 2
        assert store._max_fingerprints == 3

    # ── upsert_pattern ──

    def test_upsert_pattern_new(self):
        store = IntelligenceStore()
        p = Pattern(pattern_id="pat_1", frequency=1, structure_signature="sig1", context_shape={"k": "v"})
        store.upsert_pattern(p)
        assert len(store.patterns) == 1
        stored = store.get_pattern("sig1")
        assert stored is not None
        assert stored.frequency == 1
        assert stored.context_shape == {"k": "v"}

    def test_upsert_pattern_existing_increments_frequency(self):
        store = IntelligenceStore()
        p = Pattern(pattern_id="pat_1", frequency=1, structure_signature="sig1", context_shape={"k": "v"})
        store.upsert_pattern(p)
        store.upsert_pattern(p)
        stored = store.get_pattern("sig1")
        assert stored is not None
        assert stored.frequency == 2
        assert stored.pattern_id == "pat_1"

    def test_upsert_pattern_multiple_existing_increments(self):
        store = IntelligenceStore()
        p = Pattern(pattern_id="pat_1", frequency=1, structure_signature="sig1", context_shape={})
        for _ in range(5):
            store.upsert_pattern(p)
        stored = store.get_pattern("sig1")
        assert stored.frequency == 5

    def test_upsert_pattern_keeps_original_fields_on_existing(self):
        store = IntelligenceStore()
        p1 = Pattern(pattern_id="pat_1", frequency=1, structure_signature="sig1", context_shape={"k": "v"})
        store.upsert_pattern(p1)
        p2 = Pattern(pattern_id="pat_different", frequency=999, structure_signature="sig1", context_shape={"other": "val"})
        store.upsert_pattern(p2)
        stored = store.get_pattern("sig1")
        assert stored.frequency == 2
        assert stored.pattern_id == "pat_1"
        assert stored.context_shape == {"k": "v"}

    def test_upsert_pattern_eviction(self):
        store = IntelligenceStore(max_patterns=2)
        p1 = Pattern(pattern_id="p1", frequency=1, structure_signature="s1", context_shape={})
        p2 = Pattern(pattern_id="p2", frequency=1, structure_signature="s2", context_shape={})
        p3 = Pattern(pattern_id="p3", frequency=1, structure_signature="s3", context_shape={})
        store.upsert_pattern(p1)
        store.upsert_pattern(p2)
        store.upsert_pattern(p3)
        assert len(store.patterns) == 2
        assert store.get_pattern("s1") is None
        assert store.get_pattern("s2") is not None
        assert store.get_pattern("s3") is not None

    def test_upsert_pattern_eviction_oldest_first(self):
        store = IntelligenceStore(max_patterns=2)
        store.upsert_pattern(Pattern(pattern_id="p1", frequency=1, structure_signature="s1", context_shape={}))
        store.upsert_pattern(Pattern(pattern_id="p2", frequency=1, structure_signature="s2", context_shape={}))
        store.upsert_pattern(Pattern(pattern_id="p3", frequency=1, structure_signature="s3", context_shape={}))
        assert store.get_pattern("s1") is None

    # ── upsert_failure ──

    def test_upsert_failure_new(self):
        store = IntelligenceStore()
        fs = FailureSignature(
            signature_id="fs_1", trigger_chain=["PREFLIGHT_BLOCK"],
            frequency=1, severity_distribution={"low": 1},
        )
        store.upsert_failure(fs)
        assert len(store.failures) == 1
        stored = store.get_failure("fs_1")
        assert stored is not None
        assert stored.frequency == 1

    def test_upsert_failure_existing_increments(self):
        store = IntelligenceStore()
        fs = FailureSignature(
            signature_id="fs_1", trigger_chain=["PREFLIGHT_BLOCK"],
            frequency=1, severity_distribution={"low": 1},
        )
        store.upsert_failure(fs)
        store.upsert_failure(fs)
        stored = store.get_failure("fs_1")
        assert stored.frequency == 2

    def test_upsert_failure_merges_severity(self):
        store = IntelligenceStore()
        fs1 = FailureSignature(
            signature_id="fs_1", trigger_chain=["A"],
            frequency=1, severity_distribution={"low": 1, "medium": 2},
        )
        store.upsert_failure(fs1)
        store.upsert_failure(fs1)
        stored = store.get_failure("fs_1")
        assert stored.severity_distribution["low"] == 2
        assert stored.severity_distribution["medium"] == 4

    def test_upsert_failure_eviction(self):
        store = IntelligenceStore(max_failures=2)
        f1 = FailureSignature(signature_id="f1", trigger_chain=[], frequency=1, severity_distribution={})
        f2 = FailureSignature(signature_id="f2", trigger_chain=[], frequency=1, severity_distribution={})
        f3 = FailureSignature(signature_id="f3", trigger_chain=[], frequency=1, severity_distribution={})
        store.upsert_failure(f1)
        store.upsert_failure(f2)
        store.upsert_failure(f3)
        assert len(store.failures) == 2
        assert store.get_failure("f1") is None

    # ── upsert_fingerprint ──

    def test_upsert_fingerprint_new(self):
        store = IntelligenceStore()
        fp = DecisionFingerprint(
            fingerprint_id="fp_1", p4_verdict="ALLOW",
            context_hash="h1", capability_profile=[],
        )
        store.upsert_fingerprint(fp)
        assert len(store.fingerprints) == 1

    def test_upsert_fingerprint_duplicate_is_noop(self):
        store = IntelligenceStore()
        fp = DecisionFingerprint(
            fingerprint_id="fp_1", p4_verdict="ALLOW",
            context_hash="h1", capability_profile=[],
        )
        store.upsert_fingerprint(fp)
        store.upsert_fingerprint(fp)
        assert len(store.fingerprints) == 1

    def test_upsert_fingerprint_different_context_adds(self):
        store = IntelligenceStore()
        fp1 = DecisionFingerprint(fingerprint_id="fp_1", p4_verdict="ALLOW", context_hash="h1", capability_profile=[])
        fp2 = DecisionFingerprint(fingerprint_id="fp_2", p4_verdict="BLOCK", context_hash="h2", capability_profile=[])
        store.upsert_fingerprint(fp1)
        store.upsert_fingerprint(fp2)
        assert len(store.fingerprints) == 2

    def test_upsert_fingerprint_eviction(self):
        store = IntelligenceStore(max_fingerprints=2)
        fp1 = DecisionFingerprint(fingerprint_id="fp_1", p4_verdict="A", context_hash="h1", capability_profile=[])
        fp2 = DecisionFingerprint(fingerprint_id="fp_2", p4_verdict="B", context_hash="h2", capability_profile=[])
        fp3 = DecisionFingerprint(fingerprint_id="fp_3", p4_verdict="C", context_hash="h3", capability_profile=[])
        store.upsert_fingerprint(fp1)
        store.upsert_fingerprint(fp2)
        store.upsert_fingerprint(fp3)
        assert len(store.fingerprints) == 2
        assert store.get_fingerprint("h1") is None

    # ── getters ──

    def test_get_pattern_missing(self):
        store = IntelligenceStore()
        assert store.get_pattern("nonexistent") is None

    def test_get_failure_missing(self):
        store = IntelligenceStore()
        assert store.get_failure("nonexistent") is None

    def test_get_fingerprint_missing(self):
        store = IntelligenceStore()
        assert store.get_fingerprint("nonexistent") is None

    def test_get_pattern_found(self):
        store = IntelligenceStore()
        p = Pattern(pattern_id="pat_1", frequency=1, structure_signature="sig1", context_shape={})
        store.upsert_pattern(p)
        assert store.get_pattern("sig1") is p

    def test_get_failure_found(self):
        store = IntelligenceStore()
        fs = FailureSignature(signature_id="fs_1", trigger_chain=[], frequency=1, severity_distribution={})
        store.upsert_failure(fs)
        assert store.get_failure("fs_1") is fs

    def test_get_fingerprint_found(self):
        store = IntelligenceStore()
        fp = DecisionFingerprint(fingerprint_id="fp_1", p4_verdict="A", context_hash="h1", capability_profile=[])
        store.upsert_fingerprint(fp)
        assert store.get_fingerprint("h1") is fp

    # ── properties ──

    def test_patterns_property_returns_copy(self):
        store = IntelligenceStore()
        p = Pattern(pattern_id="pat_1", frequency=1, structure_signature="sig1", context_shape={})
        store.upsert_pattern(p)
        pats = store.patterns
        pats["new"] = p
        assert "new" not in store.patterns

    def test_failures_property_returns_copy(self):
        store = IntelligenceStore()
        fs = FailureSignature(signature_id="fs_1", trigger_chain=[], frequency=1, severity_distribution={})
        store.upsert_failure(fs)
        fails = store.failures
        fails["new"] = fs
        assert "new" not in store.failures

    def test_fingerprints_property_returns_copy(self):
        store = IntelligenceStore()
        fp = DecisionFingerprint(fingerprint_id="fp_1", p4_verdict="A", context_hash="h1", capability_profile=[])
        store.upsert_fingerprint(fp)
        fps = store.fingerprints
        fps["new"] = fp
        assert "new" not in store.fingerprints

    # ── top_* ──

    def test_top_patterns_sorted_by_frequency_desc(self):
        store = IntelligenceStore()
        store.upsert_pattern(Pattern(pattern_id="p1", frequency=3, structure_signature="s1", context_shape={}))
        store.upsert_pattern(Pattern(pattern_id="p2", frequency=10, structure_signature="s2", context_shape={}))
        store.upsert_pattern(Pattern(pattern_id="p3", frequency=5, structure_signature="s3", context_shape={}))
        top = store.top_patterns
        assert [p.pattern_id for p in top] == ["p2", "p3", "p1"]

    def test_top_patterns_limited_to_n(self):
        store = IntelligenceStore()
        for i in range(20):
            store.upsert_pattern(Pattern(pattern_id=f"p{i}", frequency=i, structure_signature=f"s{i}", context_shape={}))
        top = store.top_patterns
        assert len(top) <= 10

    def test_top_failures_sorted_by_frequency_desc(self):
        store = IntelligenceStore()
        store.upsert_failure(FailureSignature(signature_id="f1", trigger_chain=[], frequency=3, severity_distribution={}))
        store.upsert_failure(FailureSignature(signature_id="f2", trigger_chain=[], frequency=10, severity_distribution={}))
        store.upsert_failure(FailureSignature(signature_id="f3", trigger_chain=[], frequency=5, severity_distribution={}))
        top = store.top_failures
        assert [f.signature_id for f in top] == ["f2", "f3", "f1"]

    # ── eviction edge ──

    def test_eviction_from_empty_returns_none(self):
        store = IntelligenceStore()
        result = store._eviction_strategies["patterns"].select_for_eviction(store._patterns)
        assert result is None
