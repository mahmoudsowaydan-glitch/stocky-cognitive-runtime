from unittest.mock import MagicMock

import pytest

from cognitive_runtime.console.main import Console, main
from cognitive_runtime.contracts.public.dtos import (
    DaemonStatusDTO,
    PublicTraceDTO,
    ReceiptDTO,
    SubmitEventDTO,
)
from cognitive_runtime.runtime.gateway.local_runtime_gateway import (
    LocalRuntimeGateway,
)


@pytest.fixture
def mock_gateway():
    gw = MagicMock(spec=LocalRuntimeGateway)

    gw.get_daemon_status.return_value = DaemonStatusDTO(
        lifecycle="RUNNING", health="healthy", cycle_count=42,
        uptime_seconds=100.0, panic_count=1,
    )

    gw.submit_event.return_value = ReceiptDTO(
        receipt_id="r1", event_id="e1",
        correlation_id="corr-1", submitted_at=1000.0,
    )

    gw.get_result.return_value = PublicTraceDTO(
        event_id="e1", session_id="s1", status="ALLOW",
        risk_score=0.1, total_time_ms=1000.0, error=None, created_at=1.0,
    )

    gw.get_trace_by_id.return_value = PublicTraceDTO(
        event_id="e1", session_id="s1", status="ALLOW",
        risk_score=0.1, total_time_ms=1000.0, error=None, created_at=1.0,
    )

    return gw


@pytest.fixture
def console(mock_gateway):
    return Console(mock_gateway)


class TestConsoleCommands:
    def test_status(self, console, mock_gateway):
        output = console.cmd_status()
        assert "STATUS" in output
        assert "RUNNING" in output
        assert "cycles: 42" in output
        mock_gateway.get_daemon_status.assert_called_once()

    def test_submit_event(self, console, mock_gateway):
        output = console.cmd_submit_event("s1", "test", {"cmd": "analyze"})
        assert "RECEIPT" in output
        assert "r1" in output
        assert "corr-1" in output
        mock_gateway.submit_event.assert_called_once()
        call_dto = mock_gateway.submit_event.call_args[0][0]
        assert isinstance(call_dto, SubmitEventDTO)
        assert call_dto.session_id == "s1"

    def test_show_result(self, console, mock_gateway):
        output = console.cmd_show_result("r1")
        assert "TRACE e1" in output
        assert "ALLOW" in output
        assert "risk_score: 0.1" in output
        mock_gateway.get_result.assert_called_once_with("r1")

    def test_show_trace(self, console, mock_gateway):
        output = console.cmd_show_trace("e1")
        assert "TRACE e1" in output
        assert "ALLOW" in output
        mock_gateway.get_trace_by_id.assert_called_once_with("e1")


class TestConsoleNotFound:
    def test_show_result_not_found(self, console, mock_gateway):
        mock_gateway.get_result.return_value = None
        output = console.cmd_show_result("nonexistent")
        assert "ERROR: no result found" in output

    def test_show_trace_not_found(self, console, mock_gateway):
        mock_gateway.get_trace_by_id.return_value = None
        output = console.cmd_show_trace("nonexistent")
        assert "ERROR: trace not found" in output


class TestConsoleGatewayError:
    def test_status_gateway_error(self, console, mock_gateway):
        mock_gateway.get_daemon_status.side_effect = RuntimeError("connection lost")
        output = console.cmd_status()
        assert "ERROR:" in output
        assert "connection lost" in output

    def test_submit_gateway_error(self, console, mock_gateway):
        mock_gateway.submit_event.side_effect = RuntimeError("queue full")
        output = console.cmd_submit_event("s1", "test", {})
        assert "ERROR:" in output
        assert "queue full" in output

    def test_show_result_gateway_error(self, console, mock_gateway):
        mock_gateway.get_result.side_effect = RuntimeError("timeout")
        output = console.cmd_show_result("r1")
        assert "ERROR:" in output
        assert "timeout" in output


class TestConsoleCONSOLE_LEAK_001:
    def test_console_does_not_expose_daemon(self, console):
        assert not hasattr(console, "_daemon")
        assert not hasattr(console, "daemon")
        assert not hasattr(console, "runtime_daemon")

    def test_console_does_not_expose_loop(self, console):
        assert not hasattr(console, "_loop")
        assert not hasattr(console, "loop")
        assert not hasattr(console, "runtime_loop")

    def test_console_does_not_expose_internal_objects(self, console):
        assert not hasattr(console, "p4")
        assert not hasattr(console, "governance")
        assert not hasattr(console, "telemetry")
        assert not hasattr(console, "recovery")
        assert not hasattr(console, "intelligence")

    def test_console_only_accesses_gateway(self, console):
        attrs = {k for k in dir(console) if not k.startswith("__")}
        public = {a for a in attrs if not a.startswith("_")}
        assert public == {"cmd_status", "cmd_submit_event", "cmd_show_result",
                          "cmd_show_trace"}


class TestConsoleIMMUTABILITY_001:
    def test_console_calls_gateway_not_daemon(self, console, mock_gateway):
        console.cmd_status()
        mock_gateway.get_daemon_status.assert_called_once()
        assert mock_gateway.get_daemon_status.call_count == 1

    def test_submit_event_uses_gateway_only(self, console, mock_gateway):
        console.cmd_submit_event("s1", "test", {})
        mock_gateway.submit_event.assert_called_once()


class TestConsoleStateless:
    def test_two_status_calls_independent(self, console, mock_gateway):
        o1 = console.cmd_status()
        o2 = console.cmd_status()
        assert o1 == o2
        assert mock_gateway.get_daemon_status.call_count == 2

    def test_two_submit_events_independent(self, console, mock_gateway):
        mock_gateway.submit_event.side_effect = [
            ReceiptDTO(receipt_id="r1", event_id="e1", correlation_id="", submitted_at=1.0),
            ReceiptDTO(receipt_id="r2", event_id="e2", correlation_id="", submitted_at=2.0),
        ]
        o1 = console.cmd_submit_event("s1", "test", {})
        o2 = console.cmd_submit_event("s1", "test", {})
        assert "r1" in o1
        assert "r2" in o2

    def test_console_has_no_session_state(self, console):
        assert not hasattr(console, "_session")
        assert not hasattr(console, "_history")
        assert not hasattr(console, "_cache")


class TestConsoleRENDER_001:
    def test_render_status_deterministic(self):
        dto = DaemonStatusDTO(lifecycle="RUNNING", health="healthy",
                              cycle_count=10, uptime_seconds=5.0, panic_count=0)
        r1 = Console._render_status(dto)
        r2 = Console._render_status(dto)
        assert r1 == r2

    def test_render_receipt_deterministic(self):
        dto = ReceiptDTO(receipt_id="x", event_id="y",
                         correlation_id="z", submitted_at=1.0)
        r1 = Console._render_receipt(dto)
        r2 = Console._render_receipt(dto)
        assert r1 == r2

    def test_render_trace_deterministic(self):
        dto = PublicTraceDTO(event_id="e1", session_id="s1", status="ALLOW",
                             risk_score=0.1, total_time_ms=1000.0, error=None)
        r1 = Console._render_trace(dto)
        r2 = Console._render_trace(dto)
        assert r1 == r2

    def test_render_pure_function_no_side_effects(self):
        dto = DaemonStatusDTO(lifecycle="RUNNING", health="healthy",
                              cycle_count=10, uptime_seconds=5.0, panic_count=0)
        before = dto.cycle_count
        Console._render_status(dto)
        after = dto.cycle_count
        assert before == after

    def test_render_status_format(self):
        dto = DaemonStatusDTO(lifecycle="RUNNING", health="healthy",
                              cycle_count=42, uptime_seconds=100.0, panic_count=1)
        output = Console._render_status(dto)
        lines = output.split("\n")
        assert lines[0] == "STATUS"
        assert lines[1] == "  lifecycle: RUNNING"
        assert lines[5] == "  panics: 1"

    def test_render_receipt_format(self):
        dto = ReceiptDTO(receipt_id="abc", event_id="def",
                         correlation_id="ghi", submitted_at=500.0)
        output = Console._render_receipt(dto)
        lines = output.split("\n")
        assert lines[0] == "RECEIPT"
        assert lines[1] == "  receipt_id: abc"

    def test_render_trace_format(self):
        dto = PublicTraceDTO(event_id="e1", session_id="s1", status="BLOCK",
                             risk_score=0.8, total_time_ms=500.0, error="policy")
        output = Console._render_trace(dto)
        lines = output.split("\n")
        assert lines[0] == "TRACE e1"
        assert "BLOCK" in output
        assert "policy" in output


class TestConsoleMainFunction:
    def test_main_status(self, mock_gateway):
        output = main(["status"], gateway=mock_gateway)
        assert "STATUS" in output
        assert "RUNNING" in output

    def test_main_submit_event(self, mock_gateway):
        output = main(["submit_event", "s1", "test", '{"cmd":"run"}'], gateway=mock_gateway)
        assert "RECEIPT" in output
        assert "r1" in output
        mock_gateway.submit_event.assert_called_once()

    def test_main_show_result(self, mock_gateway):
        output = main(["show_result", "r1"], gateway=mock_gateway)
        assert "TRACE e1" in output

    def test_main_show_trace(self, mock_gateway):
        output = main(["show_trace", "e1"], gateway=mock_gateway)
        assert "TRACE e1" in output

    def test_main_no_gateway(self):
        output = main(["status"])
        assert "ERROR: no gateway provided" in output

    def test_main_invalid_json(self, mock_gateway):
        output = main(["submit_event", "s1", "test", "bad json"], gateway=mock_gateway)
        assert "ERROR: invalid JSON payload" in output

    def test_main_unknown_command(self, mock_gateway):
        output = main(["unknown"], gateway=mock_gateway)
        assert "ERROR: unknown command" in output

    def test_main_no_command(self, mock_gateway):
        output = main([], gateway=mock_gateway)
        assert "ERROR: no command" in output
