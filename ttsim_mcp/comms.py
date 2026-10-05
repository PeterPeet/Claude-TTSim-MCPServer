"""Raw access to Tabletop Simulator's External Editor API (layer 1, REQ-COM).

Protocol as verified against real TTSim (docs/requirements.md, Q1/Q2):
- Messages to TTSim: one JSON object per TCP connection to localhost:39999.
- Messages from TTSim: TTSim opens a new connection to localhost:39998 for every message,
  sends one JSON object and closes it.
- Execute Lua: send messageID 3; the reply is messageID 5 with the same returnID.
  Scripts are wrapped (lua/execute_wrapper.lua) so results and runtime errors come back as JSON.
- Compile errors bypass the wrapper: TTSim sends an error (messageID 3, no returnID) followed by
  a messageID 5 without returnValue.
"""

from __future__ import annotations

import itertools
import json
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_SEND_PORT = 39999
DEFAULT_LISTEN_PORT = 39998
DEFAULT_TIMEOUT = 5.0
DEFAULT_EVENT_BUFFER_SIZE = 500

# How long to wait for the separate error message of a compile error after its empty reply arrived.
_COMPILE_ERROR_GRACE = 0.5

EVENT_KINDS = {
    0: "scripts",
    1: "game_loaded",
    2: "print",
    3: "error",
    4: "custom",
    6: "game_saved",
    7: "object_created",
}


def load_lua(name: str) -> str:
    """Read a Lua template from ttsim_mcp/lua/."""
    return resources.files("ttsim_mcp").joinpath(f"lua/{name}").read_text(encoding="utf-8")


def render_lua(name: str, args: dict[str, Any] | None = None) -> str:
    """Load a Lua template and embed `args` as JSON, decoded in Lua with `JSON.decode([==[{{args}}]==])`."""
    encoded = json.dumps(args or {})
    if "]==]" in encoded:
        raise ValueError("Lua template arguments must not contain ']==]'")
    return load_lua(name).replace("{{args}}", encoded)


_WRAPPER = load_lua("execute_wrapper.lua")


class TTSimError(Exception):
    """Base class for all errors talking to Tabletop Simulator."""


class TTSimTimeoutError(TTSimError):
    """TTSim did not answer in time."""


class TTSimLuaError(TTSimError):
    """The Lua script failed in TTSim; the message is the one TTSim reported."""


class TTSimNotRunningError(TTSimError):
    """Nothing is listening on the TTSim External Editor API port."""


class TTSimListenerError(TTSimError):
    """The reply port could not be opened, usually because another program already uses it."""


@dataclass(frozen=True)
class TTSimEvent:
    seq: int
    time: float
    kind: str
    message: dict[str, Any] = field(repr=False)


@dataclass
class _PendingCall:
    done: threading.Event = field(default_factory=threading.Event)
    reply: dict[str, Any] | None = None


def wrap_lua(code: str) -> str:
    """Wrap caller-supplied Lua so it answers with a JSON-encoded result or error."""
    return _WRAPPER.replace("{{code}}", code, 1)


class TTSimConnection:
    """Connection to a running TTSim. Calls are serialised; events are buffered in the background."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        send_port: int = DEFAULT_SEND_PORT,
        listen_port: int = DEFAULT_LISTEN_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        event_buffer_size: int = DEFAULT_EVENT_BUFFER_SIZE,
    ) -> None:
        self.host = host
        self.send_port = send_port
        self.listen_port = listen_port
        self.timeout = timeout
        self._events: deque[TTSimEvent] = deque(maxlen=event_buffer_size)
        self._event_seq = itertools.count(1)
        self._last_seq = 0
        self._state_lock = threading.Condition()
        self._call_lock = threading.Lock()
        self._return_ids = itertools.count(1)
        self._pending: dict[int, _PendingCall] = {}
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def __enter__(self) -> TTSimConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def start(self) -> None:
        """Open the reply port and start receiving messages from TTSim. Idempotent."""
        if self._server is not None:
            return
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind((self.host, self.listen_port))
        except OSError as e:
            server.close()
            raise TTSimListenerError(
                f"Cannot listen on {self.host}:{self.listen_port} for messages from Tabletop Simulator "
                f"({e.strerror}). Another program is probably using the port, e.g. a TTSim editor plugin "
                "in VS Code/Atom or another TTSim-MCP instance. Close it and try again."
            ) from e
        server.listen()
        server.settimeout(0.1)
        self._server = server
        self._stop.clear()
        self._thread = threading.Thread(target=self._receive_loop, name="tts-listener", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._server is not None:
            self._server.close()
            self._server = None

    def execute_lua(self, code: str, timeout: float | None = None) -> Any:
        """Run Lua in TTSim's global context and return its result as JSON-compatible Python data."""
        self.start()
        timeout = self.timeout if timeout is None else timeout
        with self._call_lock:
            return_id = next(self._return_ids)
            call = _PendingCall()
            with self._state_lock:
                self._pending[return_id] = call
                seq_before = self._last_seq
            try:
                self._send({"messageID": 3, "guid": "-1", "script": wrap_lua(code), "returnID": return_id})
                if not call.done.wait(timeout):
                    raise TTSimTimeoutError(f"Tabletop Simulator did not answer within {timeout:g} s.")
            finally:
                with self._state_lock:
                    self._pending.pop(return_id, None)
        assert call.reply is not None
        return self._parse_reply(call.reply, seq_before)

    def events(self, since: int = 0) -> list[TTSimEvent]:
        """Buffered messages TTSim sent on its own, oldest first, with seq greater than `since`."""
        with self._state_lock:
            return [e for e in self._events if e.seq > since]

    def _send(self, message: dict[str, Any]) -> None:
        try:
            with socket.create_connection((self.host, self.send_port), timeout=self.timeout) as s:
                s.sendall(json.dumps(message).encode("utf-8"))
        except (ConnectionRefusedError, TimeoutError) as e:
            raise TTSimNotRunningError(
                f"Nothing is listening on {self.host}:{self.send_port}. Start Tabletop Simulator "
                "and load a game, then try again."
            ) from e

    def _parse_reply(self, reply: dict[str, Any], seq_before: int) -> Any:
        if "returnValue" not in reply:
            raise TTSimLuaError(self._wait_for_error_after(seq_before))
        raw = reply["returnValue"]
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as e:
            raise TTSimError(f"Unexpected reply from Tabletop Simulator: {raw!r}") from e
        if payload.get("ok"):
            return payload.get("value")
        raise TTSimLuaError(payload.get("error", "Lua error without message"))

    def _wait_for_error_after(self, seq_before: int) -> str:
        deadline = time.monotonic() + _COMPILE_ERROR_GRACE
        with self._state_lock:
            while True:
                errors = [e for e in self._events if e.seq > seq_before and e.kind == "error"]
                if errors:
                    return str(errors[-1].message.get("error", "Lua error without message"))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return "Lua error (TTSim sent no error message)"
                self._state_lock.wait(remaining)

    def _receive_loop(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                conn.settimeout(2)
                data = b""
                try:
                    while chunk := conn.recv(65536):
                        data += chunk
                except TimeoutError:
                    pass
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                self._handle(message)

    def _handle(self, message: dict[str, Any]) -> None:
        with self._state_lock:
            if message.get("messageID") == 5:
                call = self._pending.get(message.get("returnID"))  # type: ignore[arg-type]
                if call is not None:
                    call.reply = message
                    call.done.set()
                return
            seq = next(self._event_seq)
            kind = EVENT_KINDS.get(message.get("messageID"), "unknown")  # type: ignore[arg-type]
            self._events.append(TTSimEvent(seq=seq, time=time.time(), kind=kind, message=message))
            self._last_seq = seq
            self._state_lock.notify_all()
