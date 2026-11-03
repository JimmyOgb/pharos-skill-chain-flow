---
name: pharos-skill-chain-flow
description: >
  Official composition agent skill connecting Pharos Chain MCP telemetry to an intelligent SkillEngine
  decision pipeline. Dispatches read-only MCP queries to Pharos Pacific Mainnet (Chain ID 1672) to fetch
  live gas price, block height, and account balance, validates payload provenance, and evaluates composite
  treasury safety and transaction readiness rules before proposing action execution.
version: 0.1.0
requires:
  python: ">=3.10"
---

# Pharos Skill + Chain MCP Flow — Live Network Operations Advisor

An end-to-end composed agent workflow where **Chain MCP** (`https://mcp.pharos.xyz/mcp`) supplies real, live on-chain telemetry and **SkillEngine** evaluates composite policy conditions to reach a deterministic operational decision.

## Composition Architecture

```
User Single Request ("Assess network conditions under policy")
                           │
                           ▼
          [Official Chain MCP Client: mcp.pharos.xyz]
           • initialize (session ID: mcp-session-id)
           • get_chain_info   ──► chainId: 1672, latestBlock
           • get_block_number ──► blockNumber
           • get_gas_price    ──► gasPriceWei, gasPriceGwei
           • get_balance      ──► balanceWei, balance_pros (optional)
                           │
                           ▼
          [Provenance & Data Validation Engine]
           • Verifies Chain ID == 1672 (Pharos Pacific Mainnet)
           • Validates numeric positive values and schema bounds
           • Preserves per-tool block context (or marks UNAVAILABLE)
           • Calculates per-tool SHA-256 telemetry fingerprint
                           │
                           ▼
          [SkillEngine Decision Core: flow.evaluator]
           • Evaluates sequential policy gates:
             1. RULE-UPSTREAM-TELEMETRY-CHECK (fail-closed on error)
             2. RULE-CHAIN-IDENTITY-CHECK (enforces 1672)
             3. RULE-TELEMETRY-INTEGRITY-CHECK (ensures positive numbers)
             4. RULE-HEAD-FRESHNESS-CHECK (block drift tolerance)
             5. RULE-GAS-CONGESTION-CHECK (gas <= ceiling)
             6. RULE-BALANCE-SOLVENCY-CHECK (balance >= minimum reserve)
                           │
                           ▼
          [Structured Decision + Complete Provenance Trace]
           • Outcome: PASS | BLOCK | INSUFFICIENT_DATA
           • Deciding rule, human justification, live evidence table
           • Non-removable execution disclaimer (read-only, no tx sent)
```

## Supported Operations & Policies

| Policy Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `expected_chain_id` | `1672` | Pharos Pacific Mainnet required chain identity. |
| `max_gas_price_gwei` | `25.0` | Maximum acceptable gas price threshold (in Gwei). |
| `max_block_staleness` | `50` | Maximum allowable block drift between head block queries. |
| `min_balance_pros` | `None` (Optional) | Minimum native token reserve required (in PROS). |
| `target_address` | `None` (Optional) | EVM address inspected for balance evaluation. |

## Fail-Closed Security Guarantees

1. **NO Mock Data**: Every execution connects directly to `https://mcp.pharos.xyz/mcp`.
2. **NO Write Operations**: Write-capable tool `send_raw_transaction` is permanently blocked in the client.
3. **Fail-Closed on Upstream Error**: If the MCP endpoint is unreachable or a tool call fails, the SkillEngine outputs `INSUFFICIENT_DATA` with deciding rule `RULE-UPSTREAM-MCP-ERROR`. A success state is impossible without genuine upstream telemetry.
4. **Execution Notice**: Every decision includes an immutable disclaimer confirming that `PASS` denotes operational policy compliance only and does NOT authorize or broadcast any blockchain transaction.

## CLI Execution

```bash
# Run standard live assessment with visual flow diagram
python -m flow.cli assess-network --verbose

# Run with custom gas ceiling (e.g. 5.0 Gwei)
python -m flow.cli assess-network --max-gas 5.0

# Run with balance evaluation for an address
python -m flow.cli assess-network --address 0x0000000000000000000000000000000000000000 --min-balance 0.1

# Output machine-readable JSON trace
python -m flow.cli assess-network --json
```
