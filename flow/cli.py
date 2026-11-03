"""Unified CLI entry point for Pharos Skill + Chain MCP Flow."""

import argparse
import json
import sys
from typing import Optional

# Ensure UTF-8 output on Windows consoles if supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .evaluator import SkillEngineEvaluator
from .mcp_client import PharosChainMCPClient
from .models import DecisionOutcome, OperationPolicy


def format_diagram() -> str:
    """Returns an ASCII representation of the composed execution pipeline."""
    return """
+-----------------------------------------------------------------------------+
| USER REQUEST: "Assess Pharos network conditions under operational policy"   |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| [STEP 1: OFFICIAL CHAIN MCP CLIENT (mcp.pharos.xyz)]                       |
|   * initialize -> session ID negotiated                                     |
|   * get_chain_info -> chainId: 1672, latestBlock, rpcUrl                    |
|   * get_block_number -> blockNumber                                         |
|   * get_gas_price -> gasPriceWei, gasPriceGwei                              |
|   * get_balance -> balanceWei, balance_pros (if address provided)          |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| [STEP 2: VALIDATION & PROVENANCE ENGINE]                                    |
|   * Asserts chainId == 1672 (Pharos Pacific Mainnet)                        |
|   * Validates non-positive / malformed data checks                          |
|   * Computes SHA-256 telemetry fingerprint per tool response                |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| [STEP 3: SKILLENGINE DECISION CORE]                                         |
|   * Ingests live telemetry into operator policy rules                       |
|   * Evaluates: Identity -> Freshness -> Gas Ceiling -> Reserve              |
|   * Formulates deterministic outcome (PASS / BLOCK / INSUFFICIENT_DATA)     |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| COMPOSED DECISION + EVIDENCE TRACE (Notice: Read-only, no tx executed)      |
+-----------------------------------------------------------------------------+
"""


def run_assessment(
    endpoint: str = "https://mcp.pharos.xyz/mcp",
    max_gas_gwei: float = 25.0,
    address: Optional[str] = None,
    min_balance_pros: Optional[float] = None,
    output_json: bool = False,
    verbose: bool = False,
) -> int:
    """Runs the full composed pipeline from a single user command."""
    policy = OperationPolicy(
        name="Pharos Network Operations Policy",
        expected_chain_id=1672,
        max_gas_price_gwei=max_gas_gwei,
        max_block_staleness=50,
        min_balance_pros=min_balance_pros,
        target_address=address,
        require_balance_check=(address is not None and min_balance_pros is not None),
    )

    client = PharosChainMCPClient(endpoint_url=endpoint)
    evaluator = SkillEngineEvaluator(policy=policy)

    context = None
    upstream_error = None

    try:
        if not output_json:
            print("Connecting to official Chain MCP endpoint at", endpoint, "...")
        client.initialize()
        context = client.fetch_live_context(address=address)
    except Exception as exc:
        upstream_error = str(exc)

    decision = evaluator.evaluate(context=context, upstream_error=upstream_error)

    if output_json:
        out = {
            "outcome": decision.outcome.value,
            "deciding_rule": decision.deciding_rule,
            "rule_description": decision.rule_description,
            "justification": decision.justification,
            "policy_inputs": decision.policy_inputs,
            "live_evidence": decision.live_evidence,
            "tool_traces": decision.tool_traces,
            "evaluated_at": decision.evaluated_at,
            "provenance_fingerprint": decision.provenance_fingerprint,
            "execution_notice": decision.execution_notice,
        }
        print(json.dumps(out, indent=2))
        return 0 if decision.outcome == DecisionOutcome.PASS else 1

    # Human-readable CLI formatting
    print("=" * 80)
    print("PHAROS LIVE NETWORK OPERATIONS ADVISOR -- COMPOSED AGENT FLOW")
    print("=" * 80)
    print(f"Evaluated At: {decision.evaluated_at}")
    print(f"Deciding Rule: {decision.deciding_rule}")
    print(f"Outcome:       [{decision.outcome.value}]")
    print(f"Justification: {decision.justification}\n")

    print("--- LIVE CHAIN EVIDENCE (From Official Chain MCP) ---")
    if decision.live_evidence:
        for k, v in decision.live_evidence.items():
            print(f"  {k:<28}: {v}")
    else:
        print("  [No live evidence: Upstream call failed]")

    print("\n--- OPERATOR POLICY INPUTS ---")
    for k, v in decision.policy_inputs.items():
        print(f"  {k:<28}: {v}")

    print("\n--- PROVENANCE & PER-TOOL INVOCATION TRACES ---")
    for tr in decision.tool_traces:
        err_str = " (FAILED)" if tr.get("is_error") else ""
        blk = tr.get("block_context")
        blk_str = f"block={blk}" if blk is not None else "block=UNAVAILABLE"
        print(
            f"  Tool: {tr['tool_name']:<20} {blk_str:<18} "
            f"latency={tr['latency_ms']}ms  sha256={tr['sha256_hash'][:16]}...{err_str}"
        )

    print(f"\nComposite Provenance Fingerprint: {decision.provenance_fingerprint}")

    if verbose:
        print("\n--- PIPELINE EXECUTION DIAGRAM ---")
        print(format_diagram())

    print("\n" + "-" * 80)
    print(decision.execution_notice)
    print("-" * 80)

    return 0 if decision.outcome == DecisionOutcome.PASS else 1


def main():
    parser = argparse.ArgumentParser(
        description="Pharos Skill + Chain MCP Flow -- Live Network Operations Advisor"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    assess_parser = subparsers.add_parser(
        "assess-network", help="Assess live Pharos network conditions against operational policy"
    )
    assess_parser.add_argument(
        "--endpoint", default="https://mcp.pharos.xyz/mcp", help="Official Chain MCP endpoint URL"
    )
    assess_parser.add_argument(
        "--max-gas", type=float, default=25.0, help="Operator gas ceiling in Gwei (default: 25.0)"
    )
    assess_parser.add_argument(
        "--address", default=None, help="EVM address to query balance for (e.g. 0x000...000)"
    )
    assess_parser.add_argument(
        "--min-balance", type=float, default=None, help="Required minimum balance in PROS"
    )
    assess_parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    assess_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Include visual pipeline flow diagram"
    )

    args = parser.parse_args()

    if args.command == "assess-network":
        code = run_assessment(
            endpoint=args.endpoint,
            max_gas_gwei=args.max_gas,
            address=args.address,
            min_balance_pros=args.min_balance,
            output_json=args.json,
            verbose=args.verbose,
        )
        sys.exit(code)
    else:
        code = run_assessment(verbose=True)
        sys.exit(code)


if __name__ == "__main__":
    main()
