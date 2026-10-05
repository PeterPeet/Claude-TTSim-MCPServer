"""Fake Tabletop Simulator for contract tests (REQ-COM-06).

Mimics the External Editor API as observed in the 2026-10-05 spike (see docs/requirements.md, Q1/Q2):
- receives one JSON message per connection on its own port (real TTS: 39999);
- answers by opening a new connection to the client's reply port (real TTS: 39998) per message,
  sending one pretty-printed JSON object and closing.

Responses are scripted per Lua fragment: the first registered fragment contained in the received
script decides the response. Several responses for one fragment are used in order, the last one
repeating (e.g. "still moving", then "resting"). Unmatched scripts get no reply.
"""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class Value:
    """The wrapped script succeeded and returned `value` (None → no "value" key, like Lua nil)."""

    value: Any = None


@dataclass
class LuaError:
    """The wrapped script raised a runtime error, caught by the wrapper's pcall."""

    message: str


@dataclass
class CompileError:
    """The script failed to compile: TTS sends an error message without returnID, then an empty reply."""

    message: str


@dataclass
class NoReply:
    """TTS never answers (e.g. a raw Lua table was returned, or TTS is busy)."""


Response = Value | LuaError | CompileError | NoReply


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeTTS:
    def __init__(self, reply_port: int) -> None:
        self.reply_port = reply_port
        self.received: list[dict[str, Any]] = []
        self._responses: list[tuple[str, list[Response]]] = []
        self._stop = threading.Event()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen()
        self._server.settimeout(0.1)
        self.port: int = self._server.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self) -> FakeTTS:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self._server.close()

    def respond(self, fragment: str, *responses: Response) -> None:
        self._responses.append((fragment, list(responses)))

    def scripts_containing(self, fragment: str) -> list[str]:
        return [m["script"] for m in self.received if fragment in m.get("script", "")]

    def _next_response(self, script: str) -> Response:
        for fragment, responses in self._responses:
            if fragment in script:
                return responses.pop(0) if len(responses) > 1 else responses[0]
        return NoReply()

    def push_event(self, message: dict[str, Any]) -> None:
        """Send an unsolicited message, as TTS does for print(), errors, game loaded, etc."""
        self._send(message)

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            with conn:
                data = b""
                while chunk := conn.recv(65536):
                    data += chunk
            message = json.loads(data)
            self.received.append(message)
            if message.get("messageID") == 3:
                self._answer(message)

    def _answer(self, message: dict[str, Any]) -> None:
        response = self._next_response(message.get("script", ""))
        return_id = message.get("returnID")
        match response:
            case Value(value):
                payload: dict[str, Any] = {"ok": True}
                if value is not None:
                    payload["value"] = value
                self._send({"returnValue": json.dumps(payload), "returnID": return_id, "messageID": 5})
            case LuaError(text):
                payload = {"ok": False, "error": text}
                self._send({"returnValue": json.dumps(payload), "returnID": return_id, "messageID": 5})
            case CompileError(text):
                self._send(
                    {
                        "error": text,
                        "guid": "-1",
                        "errorMessagePrefix": f"[Global] Lua Error <executeScript>: {text}",
                        "messageID": 3,
                    }
                )
                self._send({"returnID": return_id, "messageID": 5})
            case NoReply():
                pass

    def _send(self, message: dict[str, Any]) -> None:
        with socket.create_connection(("127.0.0.1", self.reply_port), timeout=2) as s:
            s.sendall(json.dumps(message, indent=2).encode())
