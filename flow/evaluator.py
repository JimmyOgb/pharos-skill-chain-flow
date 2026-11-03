"""SkillEngine Decision Core for Pharos Live Network Operations Advisor.

Evaluates live chain context retrieved from official Chain MCP against operator-configured
operational policies in a deterministic, fail-closed pipeline.
"""

import datetime
from typing import Any, Dict, List, Optional

from .models import (
    DecisionOutcome,
    OperationPolicy,
    SkillDecision,
    ValidatedChainContext,
)


class SkillEngineEvaluator:
    """Deterministic evaluator implementing the official SkillEngine specification rules."""

    def __init__(self, policy: Optional[OperationPolicy] = None):
        self.policy = policy or OperationPolicy()

    def evaluate(
        self,
        context: Optional[ValidatedChainContext],
        upstream_error: Optional[str] = None,
    ) -> SkillDecision:
        """Evaluates live chain context against operational policy rules.
        
        Args:
            context: Validated chain context containing live MCP telemetry.
            upstream_error: Error message if upstream MCP call failed.
            
        Returns:
            SkillDecision with definitive outcome, deciding rule, and full evidence.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        policy_dict = {
            "policy_name": self.policy.name,
            "expected_chain_id": self.policy.expected_chain_id,
            "max_gas_price_gwei": self.policy.max_gas_price_gwei,
            "max_block_staleness": self.policy.max_block_staleness,
            "require_balance_check": self.policy.require_balance_check,
            "min_balance_pros": self.policy.min_balance_pros,
            "target_address": self.policy.target_address,
        }

        # GATE 1: Upstream Telemetry Availability Check
        if upstream_error is not None:
            return SkillDecision(
                outcome=DecisionOutcome.INSUFFICIENT_DATA,
                deciding_rule="RULE-UPSTREAM-MCP-ERROR",
                rule_description="Verifies that all required upstream MCP tool calls completed without error.",
                justification=f"Upstream Chain MCP call failed: {upstream_error}. Evaluation aborted fail-closed.",
                policy_inputs=policy_dict,
                live_evidence={},
                tool_traces=[],
                evaluated_at=now_iso,
                provenance_fingerprint="NONE",
            )

        if context is None:
            return SkillDecision(
                outcome=DecisionOutcome.INSUFFICIENT_DATA,
                deciding_rule="RULE-UPSTREAM-TELEMETRY-MISSING",
                rule_description="Verifies that live chain context was received from Chain MCP.",
                justification="No chain context was provided to the SkillEngine. Evaluation aborted fail-closed.",
                policy_inputs=policy_dict,
                live_evidence={},
                tool_traces=[],
                evaluated_at=now_iso,
                provenance_fingerprint="NONE",
            )

        # Assemble live evidence summary
        live_evidence: Dict[str, Any] = {
            "network_name": context.chain_info.name,
            "chain_id": context.chain_info.chain_id,
            "latest_block_chain_info": context.chain_info.latest_block,
            "head_block_number": context.block_number,
            "gas_price_wei": context.gas_price.gas_price_wei,
            "gas_price_gwei": context.gas_price.gas_price_gwei,
            "max_priority_fee_gwei": context.gas_price.max_priority_fee_per_gas_gwei,
            "gas_price_block_context": "UNAVAILABLE_IN_SCHEMA",
            "session_id": context.session_id,
            "retrieval_timestamp": context.retrieval_timestamp,
        }
        if context.balance:
            live_evidence["balance_address"] = context.balance.address
            live_evidence["balance_wei"] = context.balance.balance_wei
            live_evidence["balance_pros"] = context.balance.balance_pros
            live_evidence["balance_symbol"] = context.balance.symbol
            live_evidence["balance_block_context"] = "UNAVAILABLE_IN_SCHEMA"

        # Serialize tool traces
        tool_traces = []
        for tr in context.tool_responses:
            tool_traces.append({
                "id": tr.id,
                "tool_name": tr.tool_name,
                "arguments": tr.arguments,
                "latency_ms": tr.latency_ms,
                "sha256_hash": tr.sha256_hash,
                "block_context": tr.block_context,
                "chain_id": tr.chain_id,
                "utc_timestamp": tr.utc_timestamp,
                "is_error": tr.is_error,
            })

        # GATE 2: Network Identity Check
        if context.chain_info.chain_id != self.policy.expected_chain_id:
            return SkillDecision(
                outcome=DecisionOutcome.BLOCK,
                deciding_rule="RULE-CHAIN-IDENTITY-MISMATCH",
                rule_description="Enforces that live Chain MCP reports the expected Pharos network Chain ID.",
                justification=(
                    f"Reported Chain ID {context.chain_info.chain_id} ({context.chain_info.name}) "
                    f"does not match required policy network Chain ID {self.policy.expected_chain_id}."
                ),
                policy_inputs=policy_dict,
                live_evidence=live_evidence,
                tool_traces=tool_traces,
                evaluated_at=now_iso,
                provenance_fingerprint=context.provenance_hash,
            )

        # GATE 3: Telemetry Validity Check
        if context.gas_price.gas_price_gwei <= 0 or context.block_number <= 0:
            return SkillDecision(
                outcome=DecisionOutcome.INSUFFICIENT_DATA,
                deciding_rule="RULE-CORRUPT-TELEMETRY",
                rule_description="Verifies that all numeric telemetry fields are positive and well-formed.",
                justification=(
                    f"Non-positive telemetry values received from MCP: "
                    f"gas_price_gwei={context.gas_price.gas_price_gwei}, "
                    f"block_number={context.block_number}."
                ),
                policy_inputs=policy_dict,
                live_evidence=live_evidence,
                tool_traces=tool_traces,
                evaluated_at=now_iso,
                provenance_fingerprint=context.provenance_hash,
            )

        # GATE 4: Head Freshness / Block Drift Check
        block_delta = abs(context.block_number - context.chain_info.latest_block)
        if block_delta > self.policy.max_block_staleness:
            return SkillDecision(
                outcome=DecisionOutcome.BLOCK,
                deciding_rule="RULE-BLOCK-HEIGHT-STALE",
                rule_description="Checks that recent block height queries do not drift beyond tolerance.",
                justification=(
                    f"Block height drift between get_chain_info ({context.chain_info.latest_block}) "
                    f"and get_block_number ({context.block_number}) is {block_delta} blocks, "
                    f"exceeding policy tolerance of {self.policy.max_block_staleness} blocks."
                ),
                policy_inputs=policy_dict,
                live_evidence=live_evidence,
                tool_traces=tool_traces,
                evaluated_at=now_iso,
                provenance_fingerprint=context.provenance_hash,
            )

        # GATE 5: Gas Congestion Ceiling Check
        if context.gas_price.gas_price_gwei > self.policy.max_gas_price_gwei:
            return SkillDecision(
                outcome=DecisionOutcome.BLOCK,
                deciding_rule="RULE-GAS-CEILING-EXCEEDED",
                rule_description="Enforces that live Pharos network gas price is at or below the operator ceiling.",
                justification=(
                    f"Live gas price of {context.gas_price.gas_price_gwei:.2f} Gwei exceeds "
                    f"configured operator ceiling of {self.policy.max_gas_price_gwei:.2f} Gwei."
                ),
                policy_inputs=policy_dict,
                live_evidence=live_evidence,
                tool_traces=tool_traces,
                evaluated_at=now_iso,
                provenance_fingerprint=context.provenance_hash,
            )

        # GATE 6: Balance / Solvency Check (Conditionally applied)
        if self.policy.require_balance_check:
            if context.balance is None:
                return SkillDecision(
                    outcome=DecisionOutcome.INSUFFICIENT_DATA,
                    deciding_rule="RULE-BALANCE-DATA-MISSING",
                    rule_description="Ensures balance telemetry is present when balance policy is active.",
                    justification="Policy requires balance verification, but no balance telemetry was supplied.",
                    policy_inputs=policy_dict,
                    live_evidence=live_evidence,
                    tool_traces=tool_traces,
                    evaluated_at=now_iso,
                    provenance_fingerprint=context.provenance_hash,
                )

            if (
                self.policy.min_balance_pros is not None
                and context.balance.balance_pros < self.policy.min_balance_pros
            ):
                return SkillDecision(
                    outcome=DecisionOutcome.BLOCK,
                    deciding_rule="RULE-INSUFFICIENT-RESERVE",
                    rule_description="Ensures monitored address holds at least the minimum required native reserve.",
                    justification=(
                        f"Address {context.balance.address} holds {context.balance.balance_pros:.6f} PROS, "
                        f"which is below required policy threshold of {self.policy.min_balance_pros:.6f} PROS."
                    ),
                    policy_inputs=policy_dict,
                    live_evidence=live_evidence,
                    tool_traces=tool_traces,
                    evaluated_at=now_iso,
                    provenance_fingerprint=context.provenance_hash,
                )

        # GATE 7: All Operational Criteria Satisfied
        justification_msg = (
            f"All live chain parameters satisfy operator policy: "
            f"Network ID {context.chain_info.chain_id} matches {self.policy.expected_chain_id}; "
            f"Live gas price of {context.gas_price.gas_price_gwei:.2f} Gwei is within ceiling ({self.policy.max_gas_price_gwei:.2f} Gwei); "
            f"Head block height is {context.block_number}."
        )
        if context.balance:
            justification_msg += (
                f" Monitored address {context.balance.address} holds {context.balance.balance_pros:.6f} {context.balance.symbol}."
            )

        return SkillDecision(
            outcome=DecisionOutcome.PASS,
            deciding_rule="RULE-OPERATIONAL-CONDITIONS-SATISFIED",
            rule_description="Affirms that all live chain telemetry satisfies operator-configured criteria.",
            justification=justification_msg,
            policy_inputs=policy_dict,
            live_evidence=live_evidence,
            tool_traces=tool_traces,
            evaluated_at=now_iso,
            provenance_fingerprint=context.provenance_hash,
        )
