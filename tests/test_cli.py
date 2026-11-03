"""Unit tests for CLI interface, argument parsing, and output formatting."""

from unittest.mock import MagicMock, patch
import pytest

from flow.cli import format_diagram, run_assessment
from flow.models import (
    ChainInfo,
    DecisionOutcome,
    GasPrice,
    MCPResponse,
    NativeBalance,
    ValidatedChainContext,
)


def make_mock_context(gas_gwei: float = 10.0) -> ValidatedChainContext:
    chain_info = ChainInfo(
        name="Pharos",
        chain_id=1672,
        chain_id_hex="0x688",
        latest_block=21940000,
        native_symbol="PROS",
        rpc_url="https://rpc.pharos.xyz",
    )
    gas_price = GasPrice(
        gas_price_wei=int(gas_gwei * 1e9),
        gas_price_gwei=gas_gwei,
        gas_price_hex="0x0",
        max_priority_fee_per_gas_gwei=0.0,
    )
    return ValidatedChainContext(
        chain_info=chain_info,
        gas_price=gas_price,
        block_number=21940001,
        balance=None,
        session_id="mock-session-id",
        provenance_hash="mock-hash",
        retrieval_timestamp="2026-11-02T15:00:00Z",
        tool_responses=[
            MCPResponse(
                id=1,
                session_id="mock-session-id",
                tool_name="get_gas_price",
                arguments={},
                raw_text="{}",
                parsed_json={},
                is_error=False,
                latency_ms=15.0,
                sha256_hash="hash1234567890",
            )
        ],
    )


def test_format_diagram_contains_steps():
    diagram = format_diagram()
    assert "USER REQUEST" in diagram
    assert "CHAIN MCP CLIENT" in diagram
    assert "VALIDATION & PROVENANCE" in diagram
    assert "SKILLENGINE DECISION CORE" in diagram


@patch("flow.cli.PharosChainMCPClient")
def test_run_assessment_pass(mock_client_cls, capsys):
    mock_instance = MagicMock()
    mock_instance.fetch_live_context.return_value = make_mock_context(gas_gwei=10.0)
    mock_client_cls.return_value = mock_instance

    code = run_assessment(max_gas_gwei=25.0)
    assert code == 0
    captured = capsys.readouterr().out
    assert "[PASS]" in captured
    assert "RULE-OPERATIONAL-CONDITIONS-SATISFIED" in captured
    assert "10.0" in captured


@patch("flow.cli.PharosChainMCPClient")
def test_run_assessment_block_on_gas_ceiling(mock_client_cls, capsys):
    mock_instance = MagicMock()
    mock_instance.fetch_live_context.return_value = make_mock_context(gas_gwei=35.0)
    mock_client_cls.return_value = mock_instance

    code = run_assessment(max_gas_gwei=25.0)
    assert code == 1
    captured = capsys.readouterr().out
    assert "[BLOCK]" in captured
    assert "RULE-GAS-CEILING-EXCEEDED" in captured


@patch("flow.cli.PharosChainMCPClient")
def test_run_assessment_upstream_failure(mock_client_cls, capsys):
    mock_instance = MagicMock()
    mock_instance.initialize.side_effect = Exception("MCP Server Unreachable")
    mock_client_cls.return_value = mock_instance

    code = run_assessment()
    assert code == 1
    captured = capsys.readouterr().out
    assert "[INSUFFICIENT_DATA]" in captured
    assert "RULE-UPSTREAM-MCP-ERROR" in captured


@patch("flow.cli.PharosChainMCPClient")
def test_run_assessment_json_output(mock_client_cls, capsys):
    mock_instance = MagicMock()
    mock_instance.fetch_live_context.return_value = make_mock_context(gas_gwei=10.0)
    mock_client_cls.return_value = mock_instance

    code = run_assessment(output_json=True)
    assert code == 0
    captured = capsys.readouterr().out
    import json
    data = json.loads(captured)
    assert data["outcome"] == "PASS"
    assert data["deciding_rule"] == "RULE-OPERATIONAL-CONDITIONS-SATISFIED"
    assert "provenance_fingerprint" in data
