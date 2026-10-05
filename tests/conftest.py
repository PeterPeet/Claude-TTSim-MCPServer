from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest

from tests.fake_ttsim import FakeTTSim, free_port
from ttsim_mcp.comms import TTSimConnection


@pytest.fixture
def fake_and_conn() -> Iterator[tuple[FakeTTSim, TTSimConnection]]:
    """A fake TTSim and a connection to it, on ephemeral ports so a running real TTSim is never touched."""
    reply_port = free_port()
    with (
        FakeTTSim(reply_port=reply_port) as fake,
        TTSimConnection(send_port=fake.port, listen_port=reply_port, timeout=1.0) as conn,
    ):
        yield fake, conn


def wait_until(condition: Callable[[], bool], timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()
