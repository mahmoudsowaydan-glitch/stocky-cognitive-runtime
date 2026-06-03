import time
from unittest.mock import MagicMock

from cognitive_runtime.adapters.opencode.opencode_adapter import (
    OpenCodeAdapter,
)
from cognitive_runtime.adapters.opencode.editor_event import (
    EditorEvent,
    EditorEventType,
)
from cognitive_runtime.adapters.opencode.workspace_snapshot import (
    WorkspaceSnapshot,
)
from cognitive_runtime.contracts.public.dtos import (
    ReceiptDTO,
    PublicTraceDTO,
    EventStatusDTO,
)
from cognitive_runtime.runtime.gateway.local_runtime_gateway import (
    LocalRuntimeGateway,
)


def make_mock_gateway():
    gateway = MagicMock()
    gateway.submit_event.return_value = ReceiptDTO(
        receipt_id="r1",
        event_id="e1",
        correlation_id="",
        submitted_at=time.time(),
    )
    gateway.get_result.return_value = None
    gateway.get_status.return_value = None
    return gateway


class TestOpenCodeAdapterConstruction:
    def test_construction_default_session(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        assert adapter._gateway is gateway
        assert adapter._session_id == "opencode"

    def test_construction_custom_session(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway, session_id="my-session")
        assert adapter._session_id == "my-session"


class TestOpenCodeAdapterWorkspace:
    def test_capture_workspace_returns_snapshot(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        ws = adapter.capture_workspace(".")
        assert isinstance(ws, WorkspaceSnapshot)
        assert ws.root_path != ""

    def test_capture_with_files(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        ws = adapter.capture_workspace(
            ".", open_files=("main.py",)
        )
        assert "main.py" in ws.open_files


class TestOpenCodeAdapterSubmission:
    def test_submit_editor_event(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        event = EditorEvent(
            event_type=EditorEventType.REPOSITORY_OPENED,
            file_path="/repo",
        )
        receipt = adapter.submit_editor_event(event)
        gateway.submit_event.assert_called_once()
        assert receipt.receipt_id == "r1"

    def test_submit_analyze(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        receipt = adapter.submit_analyze("/repo")
        gateway.submit_event.assert_called_once()
        assert receipt.receipt_id == "r1"

    def test_submit_search(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        receipt = adapter.submit_search("/repo", pattern="*.py")
        gateway.submit_event.assert_called_once()
        assert receipt.receipt_id == "r1"


class TestOpenCodeAdapterQuery:
    def test_get_result(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        adapter.get_result("r1")
        gateway.get_result.assert_called_with("r1")

    def test_get_status(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        adapter.get_status("r1")
        gateway.get_status.assert_called_with("r1")


class TestOpenCodeAdapterPoll:
    def test_poll_found(self):
        gateway = make_mock_gateway()
        trace = PublicTraceDTO(
            event_id="e1", status="ALLOW"
        )
        gateway.get_result.side_effect = [None, None, trace]
        adapter = OpenCodeAdapter(gateway)
        result = adapter.poll_result("r1", max_attempts=10)
        assert result is not None
        assert result.status == "ALLOW"

    def test_poll_not_found(self):
        gateway = make_mock_gateway()
        gateway.get_result.return_value = None
        adapter = OpenCodeAdapter(gateway)
        result = adapter.poll_result("r1", max_attempts=3)
        assert result is None
        assert gateway.get_result.call_count <= 3


class TestADAPTER_ISOLATION_001:
    def test_no_runtime_objects(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        assert not hasattr(adapter, "_loop")
        assert not hasattr(adapter, "_p4")
        assert not hasattr(adapter, "_daemon")
        assert not hasattr(adapter, "_runtime")
        assert not hasattr(adapter, "_sandbox")
        assert not hasattr(adapter, "_governance")
        assert not hasattr(adapter, "_recovery")
        assert not hasattr(adapter, "_telemetry")
        assert not hasattr(adapter, "_intelligence")

    def test_gateway_only_communication(self):
        gateway = make_mock_gateway()
        adapter = OpenCodeAdapter(gateway)
        adapter.submit_analyze("/repo")
        adapter.get_result("r1")
        adapter.get_status("r1")
        for name, _, _ in gateway.method_calls:
            assert name in (
                "submit_event", "get_result", "get_status"
            ), f"Illegal gateway call: {name}"

    def test_adapter_only_exposes_gateway_methods(self):
        adapter = OpenCodeAdapter(make_mock_gateway())
        public_methods = {
            "capture_workspace",
            "submit_editor_event",
            "submit_analyze",
            "submit_search",
            "get_result",
            "get_status",
            "poll_result",
        }
        adapter_methods = {
            m for m in dir(adapter) if not m.startswith("_")
        }
        assert public_methods.issubset(adapter_methods)
