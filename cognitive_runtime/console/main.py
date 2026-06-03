import argparse
import json
import sys

from ..contracts.public.dtos import (
    DaemonStatusDTO,
    PublicTraceDTO,
    ReceiptDTO,
    SubmitEventDTO,
)
from ..runtime.gateway.local_runtime_gateway import LocalRuntimeGateway


class Console:
    def __init__(self, gateway: LocalRuntimeGateway):
        self._gateway = gateway

    # ── Commands ──

    def cmd_status(self) -> str:
        try:
            status = self._gateway.get_daemon_status()
        except Exception as e:
            return f"ERROR: {e}"
        return self._render_status(status)

    def cmd_submit_event(self, session_id: str, source: str, payload: dict) -> str:
        dto = SubmitEventDTO(session_id=session_id, source=source, payload=payload)
        try:
            receipt = self._gateway.submit_event(dto)
        except Exception as e:
            return f"ERROR: {e}"
        return self._render_receipt(receipt)

    def cmd_show_result(self, receipt_id: str) -> str:
        try:
            result = self._gateway.get_result(receipt_id)
        except Exception as e:
            return f"ERROR: {e}"
        if result is None:
            return "ERROR: no result found"
        return self._render_trace(result)

    def cmd_show_trace(self, event_id: str) -> str:
        try:
            trace = self._gateway.get_trace_by_id(event_id)
        except Exception as e:
            return f"ERROR: {e}"
        if trace is None:
            return "ERROR: trace not found"
        return self._render_trace(trace)

    # ── Renderers (CONSOLE-RENDER-001: deterministic pure functions) ──

    @staticmethod
    def _render_status(dto: DaemonStatusDTO) -> str:
        lines = [
            "STATUS",
            f"  lifecycle: {dto.lifecycle}",
            f"  health: {dto.health}",
            f"  cycles: {dto.cycle_count}",
            f"  uptime: {dto.uptime_seconds}s",
            f"  panics: {dto.panic_count}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_receipt(dto: ReceiptDTO) -> str:
        lines = [
            "RECEIPT",
            f"  receipt_id: {dto.receipt_id}",
            f"  event_id: {dto.event_id}",
            f"  correlation_id: {dto.correlation_id}",
            f"  submitted_at: {dto.submitted_at}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_trace(dto: PublicTraceDTO) -> str:
        lines = [
            f"TRACE {dto.event_id}",
            f"  status: {dto.status}",
            f"  risk_score: {dto.risk_score}",
            f"  total_time_ms: {dto.total_time_ms}",
            f"  error: {dto.error}",
        ]
        return "\n".join(lines)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stocky", description="Stocky Engineering OS Console")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show runtime status")

    submit = sub.add_parser("submit_event", help="submit an event to the runtime")
    submit.add_argument("session_id", type=str)
    submit.add_argument("source", type=str)
    submit.add_argument("payload", type=str, help="JSON payload string")

    show_result = sub.add_parser("show_result", help="show execution result by receipt_id")
    show_result.add_argument("receipt_id", type=str)

    show_trace = sub.add_parser("show_trace", help="show trace by event_id")
    show_trace.add_argument("event_id", type=str)

    return parser


def main(argv: list = None, gateway: LocalRuntimeGateway = None) -> str:
    if gateway is None:
        return "ERROR: no gateway provided"

    args = argv or []
    if not args:
        return "ERROR: no command"

    command = args[0]
    rest = args[1:]
    console = Console(gateway)

    if command == "status":
        return console.cmd_status()
    elif command == "submit_event":
        if len(rest) < 3:
            return "ERROR: submit_event requires 3 arguments: session_id source payload_json"
        try:
            payload = json.loads(rest[2])
        except json.JSONDecodeError as e:
            return f"ERROR: invalid JSON payload — {e}"
        return console.cmd_submit_event(rest[0], rest[1], payload)
    elif command == "show_result":
        if len(rest) < 1:
            return "ERROR: show_result requires receipt_id"
        return console.cmd_show_result(rest[0])
    elif command == "show_trace":
        if len(rest) < 1:
            return "ERROR: show_trace requires event_id"
        return console.cmd_show_trace(rest[0])

    return f"ERROR: unknown command — {command}"


def entry_point() -> None:
    result = main(sys.argv[1:])
    print(result)


if __name__ == "__main__":
    entry_point()
