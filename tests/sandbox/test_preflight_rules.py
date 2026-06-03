import pytest

from cognitive_runtime.sandbox.preflight_rules import (
    RULES,
    PreflightRule,
    RuleSeverity,
    _check_known_capabilities,
    _check_high_risk_combination,
    _check_write_has_target,
)
from cognitive_runtime.contracts.execution_contract import Capability


class TestRuleSeverity:
    def test_enum_values(self):
        assert RuleSeverity.BLOCK.value == "BLOCK"
        assert RuleSeverity.FLAG.value == "FLAG"


class TestPreflightRule:
    def test_structure(self):
        rule = PreflightRule(
            name="test_rule",
            description="a test rule",
            severity=RuleSeverity.BLOCK,
            check_fn=lambda p: None,
        )
        assert rule.name == "test_rule"
        assert rule.description == "a test rule"
        assert rule.severity == RuleSeverity.BLOCK
        assert callable(rule.check_fn)

    def test_evaluate_returns_none_when_passing(self):
        rule = PreflightRule(
            name="passing", description="", severity=RuleSeverity.BLOCK,
            check_fn=lambda p: None,
        )
        assert rule.evaluate({}) is None

    def test_evaluate_returns_violation_string(self):
        rule = PreflightRule(
            name="failing", description="", severity=RuleSeverity.BLOCK,
            check_fn=lambda p: "something_wrong",
        )
        assert rule.evaluate({}) == "something_wrong"

    def test_evaluate_catches_exception(self):
        rule = PreflightRule(
            name="crashy", description="", severity=RuleSeverity.BLOCK,
            check_fn=lambda p: 1 / 0,
        )
        result = rule.evaluate({})
        assert result.startswith("rule_evaluation_error:")


class TestProposalHasAction:
    def test_valid_action(self):
        rule = _get_rule("proposal_has_action")
        assert rule.evaluate({"action": "read"}) is None

    def test_missing_action(self):
        rule = _get_rule("proposal_has_action")
        assert rule.evaluate({"action": ""}) == "missing_action"

    def test_no_action_key(self):
        rule = _get_rule("proposal_has_action")
        assert rule.evaluate({}) == "missing_action"


class TestProposalHasEventId:
    def test_valid_event_id(self):
        rule = _get_rule("proposal_has_event_id")
        assert rule.evaluate({"event_id": "e1"}) is None

    def test_missing_event_id(self):
        rule = _get_rule("proposal_has_event_id")
        assert rule.evaluate({"event_id": ""}) == "missing_event_id"

    def test_no_event_id_key(self):
        rule = _get_rule("proposal_has_event_id")
        assert rule.evaluate({}) == "missing_event_id"


class TestProposalHasSessionId:
    def test_valid_session_id(self):
        rule = _get_rule("proposal_has_session_id")
        assert rule.evaluate({"session_id": "s1"}) is None

    def test_missing_session_id(self):
        rule = _get_rule("proposal_has_session_id")
        assert rule.evaluate({"session_id": ""}) == "missing_session_id"

    def test_no_session_id_key(self):
        rule = _get_rule("proposal_has_session_id")
        assert rule.evaluate({}) == "missing_session_id"


class TestConfidenceInRange:
    def test_confidence_zero(self):
        rule = _get_rule("confidence_in_range")
        assert rule.evaluate({"confidence": 0.0}) is None

    def test_confidence_half(self):
        rule = _get_rule("confidence_in_range")
        assert rule.evaluate({"confidence": 0.5}) is None

    def test_confidence_one(self):
        rule = _get_rule("confidence_in_range")
        assert rule.evaluate({"confidence": 1.0}) is None

    def test_confidence_below_zero(self):
        rule = _get_rule("confidence_in_range")
        assert rule.evaluate({"confidence": -0.1}) == "confidence_out_of_range"

    def test_confidence_above_one(self):
        rule = _get_rule("confidence_in_range")
        assert rule.evaluate({"confidence": 1.5}) == "confidence_out_of_range"

    def test_default_confidence_is_used(self):
        rule = _get_rule("confidence_in_range")
        assert rule.evaluate({}) is None


class TestRiskScoreInRange:
    def test_risk_zero(self):
        rule = _get_rule("risk_score_in_range")
        assert rule.evaluate({"risk_score": 0.0}) is None

    def test_risk_half(self):
        rule = _get_rule("risk_score_in_range")
        assert rule.evaluate({"risk_score": 0.5}) is None

    def test_risk_one(self):
        rule = _get_rule("risk_score_in_range")
        assert rule.evaluate({"risk_score": 1.0}) is None

    def test_risk_below_zero(self):
        rule = _get_rule("risk_score_in_range")
        assert rule.evaluate({"risk_score": -0.1}) == "risk_score_out_of_range"

    def test_risk_above_one(self):
        rule = _get_rule("risk_score_in_range")
        assert rule.evaluate({"risk_score": 1.5}) == "risk_score_out_of_range"


class TestCapabilitiesNotEmpty:
    def test_with_capabilities(self):
        rule = _get_rule("capabilities_not_empty")
        assert rule.evaluate({"required_capabilities": ["filesystem.read"]}) is None

    def test_empty_capabilities(self):
        rule = _get_rule("capabilities_not_empty")
        assert rule.evaluate({"required_capabilities": []}) == "no_required_capabilities"

    def test_no_capabilities_key(self):
        rule = _get_rule("capabilities_not_empty")
        assert rule.evaluate({}) == "no_required_capabilities"


class TestCapabilitiesAreKnown:
    def test_known_capability(self):
        rule = _get_rule("capabilities_are_known")
        assert rule.evaluate({"required_capabilities": ["filesystem.read"]}) is None

    def test_multiple_known_capabilities(self):
        rule = _get_rule("capabilities_are_known")
        assert rule.evaluate(
            {"required_capabilities": ["network.http", "filesystem.write", "audit.read"]}
        ) is None

    def test_unknown_capability(self):
        rule = _get_rule("capabilities_are_known")
        result = rule.evaluate({"required_capabilities": ["unknown.cap"]})
        assert result == "unknown_capability: unknown.cap"

    def test_mixed_known_and_unknown(self):
        rule = _get_rule("capabilities_are_known")
        result = rule.evaluate(
            {"required_capabilities": ["filesystem.read", "unknown.cap"]}
        )
        assert result == "unknown_capability: unknown.cap"

    def test_empty_caps_list(self):
        rule = _get_rule("capabilities_are_known")
        assert rule.evaluate({"required_capabilities": []}) is None


class TestNoNetworkWriteHighRisk:
    def test_network_write_high_risk_triggers_flag(self):
        rule = _get_rule("no_network_write_high_risk")
        result = rule.evaluate({
            "required_capabilities": ["network.http", "filesystem.write"],
            "risk_score": 0.8,
        })
        assert result == "high_risk_network_write_combination"

    def test_network_write_low_risk_ok(self):
        rule = _get_rule("no_network_write_high_risk")
        assert rule.evaluate({
            "required_capabilities": ["network.http", "filesystem.write"],
            "risk_score": 0.7,
        }) is None

    def test_network_only_no_flag(self):
        rule = _get_rule("no_network_write_high_risk")
        assert rule.evaluate({
            "required_capabilities": ["network.http"],
            "risk_score": 0.9,
        }) is None

    def test_write_only_no_flag(self):
        rule = _get_rule("no_network_write_high_risk")
        assert rule.evaluate({
            "required_capabilities": ["filesystem.write"],
            "risk_score": 0.9,
        }) is None

    def test_no_caps_no_flag(self):
        rule = _get_rule("no_network_write_high_risk")
        assert rule.evaluate({"risk_score": 0.9}) is None

    def test_severity_is_flag(self):
        rule = _get_rule("no_network_write_high_risk")
        assert rule.severity == RuleSeverity.FLAG


class TestTargetPresentForWrite:
    def test_write_with_target_ok(self):
        rule = _get_rule("target_present_for_write")
        assert rule.evaluate({
            "required_capabilities": ["filesystem.write"],
            "target": "/some/path",
        }) is None

    def test_write_without_target_blocked(self):
        rule = _get_rule("target_present_for_write")
        assert rule.evaluate({
            "required_capabilities": ["filesystem.write"],
        }) == "write_without_target"

    def test_write_with_empty_target_blocked(self):
        rule = _get_rule("target_present_for_write")
        assert rule.evaluate({
            "required_capabilities": ["filesystem.write"],
            "target": "",
        }) == "write_without_target"

    def test_read_without_target_ok(self):
        rule = _get_rule("target_present_for_write")
        assert rule.evaluate({
            "required_capabilities": ["filesystem.read"],
        }) is None

    def test_no_caps_ok(self):
        rule = _get_rule("target_present_for_write")
        assert rule.evaluate({}) is None


class TestRulesList:
    def test_all_nine_rules_present(self):
        assert len(RULES) == 9

    def test_rule_names(self):
        names = [r.name for r in RULES]
        assert names == [
            "proposal_has_action",
            "proposal_has_event_id",
            "proposal_has_session_id",
            "confidence_in_range",
            "risk_score_in_range",
            "capabilities_not_empty",
            "capabilities_are_known",
            "no_network_write_high_risk",
            "target_present_for_write",
        ]

    def test_all_have_correct_severity(self):
        block_rules = {
            "proposal_has_action", "proposal_has_event_id",
            "proposal_has_session_id", "confidence_in_range",
            "risk_score_in_range", "capabilities_not_empty",
            "capabilities_are_known", "target_present_for_write",
        }
        for rule in RULES:
            if rule.name in block_rules:
                assert rule.severity == RuleSeverity.BLOCK, f"{rule.name} should be BLOCK"
            else:
                assert rule.severity == RuleSeverity.FLAG, f"{rule.name} should be FLAG"


class TestHelperFunctions:
    def test_check_known_capabilities_all_known(self):
        assert _check_known_capabilities(
            ["filesystem.read", "network.http"]
        ) is None

    def test_check_known_capabilities_unknown(self):
        assert _check_known_capabilities(
            ["bogus.cap"]
        ) == "unknown_capability: bogus.cap"

    def test_check_high_risk_combination_triggers(self):
        result = _check_high_risk_combination({
            "required_capabilities": ["network.http", "filesystem.write"],
            "risk_score": 0.8,
        })
        assert result == "high_risk_network_write_combination"

    def test_check_high_risk_combination_no_trigger(self):
        assert _check_high_risk_combination({
            "required_capabilities": ["network.http"],
            "risk_score": 0.8,
        }) is None

    def test_check_write_has_target_blocked(self):
        assert _check_write_has_target({
            "required_capabilities": ["filesystem.write"],
        }) == "write_without_target"

    def test_check_write_has_target_ok(self):
        assert _check_write_has_target({
            "required_capabilities": ["filesystem.write"],
            "target": "/path",
        }) is None

    def test_check_write_has_target_no_write_cap(self):
        assert _check_write_has_target({
            "required_capabilities": ["filesystem.read"],
        }) is None


def _get_rule(name: str) -> PreflightRule:
    for r in RULES:
        if r.name == name:
            return r
    raise AssertionError(f"Rule '{name}' not found in RULES")
