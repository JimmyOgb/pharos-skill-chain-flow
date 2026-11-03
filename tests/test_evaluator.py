"""Unit tests for SkillEngineEvaluator rule evaluation and fail-closed gates.

NOTE: These tests use controlled synthetic fixtures to exhaustively test each decision rule.
They are strictly isolated from live network calls.
"""

import pytest

from flow.evaluator import SkillEngineEvaluator
from flow.models import (
    ChainInfo,
    DecisionOutcome,
    GasPrice,
    MCPResponse,
    NativeBalance,
    OperationPolicy,
    ValidatedChainContext,
)


def make_valid_context(
    chain_id: int = 1672,
    latest_block: int = 21940000,
    head_block: int = 21940002,
    gas_gwei: float = 10.0,
    balance_pros: float = 1.0,
) -> ValidatedChainContext:
    chain_info = ChainInfo(
        name="Pharos",
        chain_id=chain_id,
        chain_id_hex=hex(chain_id),
        latest_block=latest_block,
        native_symbol="PROS",
        rpc_url="https://rpc.pharos.xyz",
    )
    gas_price = GasPrice(
        gas_price_wei=int(gas_gwei * 1e9),
        gas_price_gwei=gas_gwei,
        gas_price_hex="0x0",
        max_priority_fee_per_gas_gwei=0.0,
    )
    balance = NativeBalance(
        address="0x0000000000000000000000000000000000000000",
        balance_wei=int(balance_pros * 1e18),
        balance_pros=balance_pros,
        symbol="PROS",
    )
    return ValidatedChainContext(
        chain_info=chain_info,
        gas_price=gas_price,
        block_number=head_block,
        balance=balance,
        session_id="test-session-id",
        provenance_hash="test-sha256-hash",
        retrieval_timestamp="2026-11-02T15:00:00Z",
        tool_responses=[
            MCPResponse(
                id=1,
                session_id="test-session-id",
                tool_name="get_gas_price",
                arguments={},
                raw_text="{}",
                parsed_json={},
                is_error=False,
                latency_ms=10.0,
                sha256_hash="hash1",
            )
        ],
    )


def test_evaluator_upstream_error_fails_closed():
    evaluator = SkillEngineEvaluator()
    decision = evaluator.evaluate(context=None, upstream_error="Connection timed out")
    assert decision.outcome == DecisionOutcome.INSUFFICIENT_DATA
    assert decision.deciding_rule == "RULE-UPSTREAM-MCP-ERROR"
    assert "Connection timed out" in decision.justification


def test_evaluator_none_context_fails_closed():
    evaluator = SkillEngineEvaluator()
    decision = evaluator.evaluate(context=None)
    assert decision.outcome == DecisionOutcome.INSUFFICIENT_DATA
    assert decision.deciding_rule == "RULE-UPSTREAM-TELEMETRY-MISSING"


def test_evaluator_chain_mismatch_blocks():
    ctx = make_valid_context(chain_id=688689)  # Atlantic instead of Pacific
    evaluator = SkillEngineEvaluator()
    decision = evaluator.evaluate(context=ctx)
    assert decision.outcome == DecisionOutcome.BLOCK
    assert decision.deciding_rule == "RULE-CHAIN-IDENTITY-MISMATCH"
    assert "688689" in decision.justification


def test_evaluator_corrupt_gas_telemetry_insufficient_data():
    ctx = make_valid_context(gas_gwei=0.0)
    evaluator = SkillEngineEvaluator()
    decision = evaluator.evaluate(context=ctx)
    assert decision.outcome == DecisionOutcome.INSUFFICIENT_DATA
    assert decision.deciding_rule == "RULE-CORRUPT-TELEMETRY"


def test_evaluator_stale_block_height_blocks():
    # Drift by 100 blocks when tolerance is 50
    ctx = make_valid_context(latest_block=21940000, head_block=21940105)
    policy = OperationPolicy(max_block_staleness=50)
    evaluator = SkillEngineEvaluator(policy=policy)
    decision = evaluator.evaluate(context=ctx)
    assert decision.outcome == DecisionOutcome.BLOCK
    assert decision.deciding_rule == "RULE-BLOCK-HEIGHT-STALE"
    assert "105 blocks" in decision.justification


def test_evaluator_gas_ceiling_exceeded_blocks():
    ctx = make_valid_context(gas_gwei=30.0)
    policy = OperationPolicy(max_gas_price_gwei=25.0)
    evaluator = SkillEngineEvaluator(policy=policy)
    decision = evaluator.evaluate(context=ctx)
    assert decision.outcome == DecisionOutcome.BLOCK
    assert decision.deciding_rule == "RULE-GAS-CEILING-EXCEEDED"
    assert "30.00 Gwei" in decision.justification


def test_evaluator_gas_within_ceiling_passes():
    ctx = make_valid_context(gas_gwei=10.0)
    policy = OperationPolicy(max_gas_price_gwei=25.0)
    evaluator = SkillEngineEvaluator(policy=policy)
    decision = evaluator.evaluate(context=ctx)
    assert decision.outcome == DecisionOutcome.PASS
    assert decision.deciding_rule == "RULE-OPERATIONAL-CONDITIONS-SATISFIED"
    assert "10.00 Gwei" in decision.justification


def test_evaluator_balance_required_missing_insufficient_data():
    ctx = make_valid_context()
    ctx.balance = None
    policy = OperationPolicy(require_balance_check=True, min_balance_pros=0.5)
    evaluator = SkillEngineEvaluator(policy=policy)
    decision = evaluator.evaluate(context=ctx)
    assert decision.outcome == DecisionOutcome.INSUFFICIENT_DATA
    assert decision.deciding_rule == "RULE-BALANCE-DATA-MISSING"


def test_evaluator_balance_insufficient_blocks():
    ctx = make_valid_context(balance_pros=0.01)
    policy = OperationPolicy(require_balance_check=True, min_balance_pros=0.1)
    evaluator = SkillEngineEvaluator(policy=policy)
    decision = evaluator.evaluate(context=ctx)
    assert decision.outcome == DecisionOutcome.BLOCK
    assert decision.deciding_rule == "RULE-INSUFFICIENT-RESERVE"
    assert "0.010000 PROS" in decision.justification


def test_evaluator_balance_satisfied_passes():
    ctx = make_valid_context(balance_pros=1.5)
    policy = OperationPolicy(require_balance_check=True, min_balance_pros=0.5)
    evaluator = SkillEngineEvaluator(policy=policy)
    decision = evaluator.evaluate(context=ctx)
    assert decision.outcome == DecisionOutcome.PASS
    assert decision.deciding_rule == "RULE-OPERATIONAL-CONDITIONS-SATISFIED"


def test_evaluator_execution_notice_present():
    ctx = make_valid_context()
    evaluator = SkillEngineEvaluator()
    decision = evaluator.evaluate(context=ctx)
    assert "does NOT authorize, sign, or broadcast" in decision.execution_notice
