"""Unit tests for MCP protocol parsing, allowlist enforcement, and error handling.

NOTE: These tests use controlled synthetic protocol fixtures to test parser robustness
and security boundaries. They are strictly isolated from live network calls.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
import requests

from flow.mcp_client import (
    EXPLICITLY_DENIED_TOOLS,
    READ_ONLY_TOOL_ALLOWLIST,
    PharosChainMCPClient,
)
from flow.provenance import (
    NetworkMismatchError,
    ProtocolValidationError,
    SecurityViolationError,
    parse_sse_event,
    validate_jsonrpc_match,
    validate_session,
)


def test_parse_sse_event_valid_single_line():
    raw = 'data: {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}}\n\n'
    parsed = parse_sse_event(raw)
    assert parsed["jsonrpc"] == "2.0"
    assert parsed["id"] == 1
    assert parsed["result"]["status"] == "ok"


def test_parse_sse_event_with_heartbeat_comments():
    raw = ': ping\n\ndata: {"jsonrpc": "2.0", "id": 2, "result": {"val": 42}}\n\n'
    parsed = parse_sse_event(raw)
    assert parsed["id"] == 2
    assert parsed["result"]["val"] == 42


def test_parse_sse_event_empty_raises():
    with pytest.raises(ProtocolValidationError, match="Empty SSE payload"):
        parse_sse_event("   ")


def test_parse_sse_event_malformed_json_raises():
    with pytest.raises(ProtocolValidationError, match="Invalid JSON inside SSE"):
        parse_sse_event("data: {malformed json\n\n")


def test_validate_session_success():
    sid = "test-session-id-mock-12345"
    assert validate_session(sid) == sid


def test_validate_session_missing_raises():
    with pytest.raises(ProtocolValidationError, match="valid 'mcp-session-id'"):
        validate_session(None)
    with pytest.raises(ProtocolValidationError, match="valid 'mcp-session-id'"):
        validate_session("")


def test_validate_jsonrpc_match_success():
    validate_jsonrpc_match(1, {"jsonrpc": "2.0", "id": 1, "result": {}})


def test_validate_jsonrpc_match_mismatch_raises():
    with pytest.raises(ProtocolValidationError, match="ID mismatch: expected 1, got 2"):
        validate_jsonrpc_match(1, {"jsonrpc": "2.0", "id": 2, "result": {}})


def test_read_only_allowlist_contents():
    # Verify core query tools are present
    assert "get_chain_info" in READ_ONLY_TOOL_ALLOWLIST
    assert "get_gas_price" in READ_ONLY_TOOL_ALLOWLIST
    assert "get_balance" in READ_ONLY_TOOL_ALLOWLIST
    assert "get_block_number" in READ_ONLY_TOOL_ALLOWLIST
    assert "eth_call" in READ_ONLY_TOOL_ALLOWLIST

    # Verify write tools are NOT in allowlist
    assert "send_raw_transaction" not in READ_ONLY_TOOL_ALLOWLIST
    assert "send_raw_transaction" in EXPLICITLY_DENIED_TOOLS


def test_explicitly_denied_tool_raises_security_violation():
    client = PharosChainMCPClient()
    for write_tool in EXPLICITLY_DENIED_TOOLS:
        with pytest.raises(SecurityViolationError, match="explicitly denied"):
            client.call_tool(write_tool, {"rawTransaction": "0x1234"})


def test_unregistered_tool_raises_security_violation():
    client = PharosChainMCPClient()
    with pytest.raises(SecurityViolationError, match="not in the verified read-only allowlist"):
        client.call_tool("arbitrary_injected_tool", {})


def test_tool_list_tags_allowlist():
    mock_session = MagicMock()
    # Mock initialize
    init_resp = MagicMock()
    init_resp.headers = {"mcp-session-id": "test-session-123"}
    init_resp.text = 'data: {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "test", "version": "1.0"}}}\n\n'
    
    # Mock tools/list
    tools_resp = MagicMock()
    tools_resp.text = (
        'data: {"jsonrpc": "2.0", "id": 2, "result": {"tools": ['
        '{"name": "get_gas_price", "description": "Get gas", "inputSchema": {}},'
        '{"name": "send_raw_transaction", "description": "Write", "inputSchema": {}},'
        '{"name": "custom_read", "description": "Unknown", "inputSchema": {}}'
        ']}}\n\n'
    )
    mock_session.post.side_effect = [init_resp, MagicMock(), tools_resp]

    client = PharosChainMCPClient(session=mock_session)
    tools = client.list_tools()
    assert len(tools) == 3

    tool_map = {t.name: t.is_read_only for t in tools}
    assert tool_map["get_gas_price"] is True
    assert tool_map["send_raw_transaction"] is False
    assert tool_map["custom_read"] is False
