from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest

from tests.fake_tts import FakeTTS, free_port
from tts_mcp.comms import TTSConnection


@pytest.fixture
def fake_and_conn() -> Iterator[tuple[FakeTTS, TTSConnection]]:
    """A fake TTS and a connection to it, on ephemeral ports so a running real TTS is never touched."""
    reply_port = free_port()
    with (
        FakeTTS(reply_port=reply_port) as fake,
        TTSConnection(send_port=fake.port, listen_port=reply_port, timeout=1.0) as conn,
    ):
        yield fake, conn


def wait_until(condition: Callable[[], bool], timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()
