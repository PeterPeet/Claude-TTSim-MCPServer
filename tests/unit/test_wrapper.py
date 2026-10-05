"""Unit tests for the Lua wrapper used by execute_lua (REQ-COM-01, REQ-COM-03)."""

from ttsim_mcp.comms import wrap_lua


def test_req_com_01_wrapper_keeps_code_on_first_line() -> None:
    # Keeps Lua error line numbers identical to the caller's code.
    assert wrap_lua("return 1+1").splitlines()[0].endswith("return 1+1")


def test_req_com_01_wrapper_json_encodes_result() -> None:
    script = wrap_lua("return {}")
    assert "pcall(function()" in script
    assert "JSON.encode" in script


def test_req_com_01_wrapper_survives_trailing_comment() -> None:
    lines = wrap_lua("return 1 -- note").splitlines()
    assert lines[1].startswith("end)")
