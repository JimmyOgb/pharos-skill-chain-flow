# Pharos Skill + Chain MCP Flow (`skill-chain-mcp-flow`)

[![Pharos Agent Arena](https://img.shields.io/badge/Pharos%20Arena-Task%2012-blue)](https://pharos-agent-arena.vercel.app/tasks/skill-chain-mcp-flow)
[![Track: Composition](https://img.shields.io/badge/Track-Composition-green)](https://pharos-agent-arena.vercel.app)
[![Difficulty: Medium](https://img.shields.io/badge/Difficulty-Medium%20(150%20pts)-orange)](https://pharos-agent-arena.vercel.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Tests: 42 Passed](https://img.shields.io/badge/Tests-42%20Passed%20(100%25)-brightgreen)](tests/)

An official composition agent workflow where **Pharos Chain MCP** (`https://mcp.pharos.xyz/mcp`) supplies real, live on-chain telemetry and **SkillEngine** executes composite evaluation rules to reach an actionable decision in a single user request.

---

## 1. What the Project Does

The **Pharos Live Network Operations Advisor** connects directly to the official Pharos Model Context Protocol (MCP) server over HTTP/SSE, retrieves live Pacific Mainnet telemetry (`get_chain_info`, `get_block_number`, `get_gas_price`, `get_balance`), validates data provenance, and feeds the parameters into a deterministic SkillEngine decision core.

From a single user prompt or CLI command, the agent evaluates whether network congestion, block freshness, chain identity, and native reserve criteria satisfy operator policy, producing an evidence-backed `PASS`, `BLOCK`, or `INSUFFICIENT_DATA` advisory verdict with complete per-tool provenance traces.

---

## 2. Requirements

- **Python**: `>= 3.10` (tested on Python 3.12.10)
- **Dependencies**: `requests >= 2.31.0` (core), `pytest >= 8.0.0` (testing)
- **Network**: Internet access to `https://mcp.pharos.xyz/mcp` (free, read-only, non-custodial)
- **Cost**: **$0.00** (Zero fees, no wallet, no gas spent)

---

## 3. Installation

From a clean checkout:

```bash
# Clone or navigate to the workspace
cd skills/pharos-skill-chain-flow

# (Optional) Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 4. How to Test It

### A. Run Automated Unit Test Suite (Offline / Fast)
```bash
pytest -v
```
*Executes 42 unit tests covering SSE parsing, tool allowlist enforcement, write-tool blocking, provenance hashing, and decision rules in ~0.5s.*

### B. Run One-Command Live Assessment (Real Pharos Mainnet)
```bash
python -m flow.cli assess-network --verbose
```
*Connects live to `https://mcp.pharos.xyz/mcp`, performs MCP protocol handshake, discovers tools, ingests live gas and block height, and prints the evidence-backed decision.*

### C. Test Dynamic Policy Gating (Verifying Live Data Dependency)
```bash
# Test 1: Restrictive Gas Ceiling (Live 10 Gwei > 5 Gwei ceiling -> BLOCK)
python -m flow.cli assess-network --max-gas 5.0

# Test 2: Balance Reserve Check on Public Zero Address (0.0 PROS < 0.5 PROS -> BLOCK)
python -m flow.cli assess-network --address 0x0000000000000000000000000000000000000000 --min-balance 0.5

# Test 3: Machine-Readable JSON Provenance Output
python -m flow.cli assess-network --json
```

---

## 5. Expected Real MCP Data Flow

```
+-----------------------------------------------------------------------------+
| USER REQUEST: "Assess Pharos network conditions under operational policy"   |
+-----------------------------------------------------------------------------+
                                      │
                                      ▼
+─────────────────────────────────────────────────────────────────────────────+
| [STEP 1: OFFICIAL CHAIN MCP CLIENT (mcp.pharos.xyz/mcp)]                    |
|   • initialize ──────────► session ID negotiated (HTTP POST + SSE)          |
|   • get_chain_info ──────► chainId: 1672, latestBlock, rpcUrl               |
|   • get_block_number ────► blockNumber (head height)                        |
|   • get_gas_price ───────► gasPriceWei, gasPriceGwei (10 Gwei)              |
|   • get_balance ─────────► balanceWei, balance_pros (if address provided)   |
+─────────────────────────────────────────────────────────────────────────────+
                                      │
                                      ▼
+─────────────────────────────────────────────────────────────────────────────+
| [STEP 2: VALIDATION & PROVENANCE ENGINE (flow/provenance.py)]               |
|   • Verifies chainId == 1672 (Pharos Pacific Mainnet)                       |
|   • Validates positive numeric bounds and JSON-RPC ID matching              |
|   • Computes SHA-256 telemetry fingerprint per tool response                |
+─────────────────────────────────────────────────────────────────────────────+
                                      │
                                      ▼
+─────────────────────────────────────────────────────────────────────────────+
| [STEP 3: SKILLENGINE DECISION CORE (flow/evaluator.py)]                     |
|   • Ingests live telemetry into operator-configured policy rules            |
|   • Evaluates: Identity -> Freshness -> Gas Ceiling -> Reserve              |
|   • Formulates deterministic outcome (PASS / BLOCK / INSUFFICIENT_DATA)     |
+─────────────────────────────────────────────────────────────────────────────+
                                      │
                                      ▼
+-----------------------------------------------------------------------------+
| COMPOSED DECISION + EVIDENCE TRACE (Notice: Read-only advisory verdict)     |
+-----------------------------------------------------------------------------+
```

---

## 6. Decision Rules & Fail-Closed Logic

| Rule ID | Type | Condition | Outcome on Failure |
| :--- | :---: | :--- | :---: |
| `RULE-UPSTREAM-MCP-ERROR` | Availability | Upstream MCP tool call succeeds without error | `INSUFFICIENT_DATA` |
| `RULE-CHAIN-IDENTITY-CHECK` | Network | `context.chain_id == policy.expected_chain_id` (1672) | `BLOCK` |
| `RULE-CORRUPT-TELEMETRY` | Integrity | Numeric fields (`gas_price_gwei`, `block_number`) > 0 | `INSUFFICIENT_DATA` |
| `RULE-BLOCK-HEIGHT-STALE` | Freshness | `abs(head_block - latest_block) <= max_staleness` (50) | `BLOCK` |
| `RULE-GAS-CEILING-EXCEEDED` | Gas Limit | `gas_price_gwei <= max_gas_price_gwei` (e.g. 25 Gwei) | `BLOCK` |
| `RULE-INSUFFICIENT-RESERVE` | Balance | `balance_pros >= min_balance_pros` (when enabled) | `BLOCK` |
| `RULE-OPERATIONAL-CONDITIONS-SATISFIED` | Success | All operational criteria satisfied | **`PASS`** |

---

## 7. Security Boundaries & Invariants

1. **Strict Read-Only Tool Allowlist**: Only 13 audited read-only tools are permitted (`get_chain_info`, `get_block_number`, `get_gas_price`, `get_balance`, `get_block`, `get_transaction_count`, `get_transaction`, `get_transaction_receipt`, `get_code`, `get_storage_at`, `eth_call`, `estimate_gas`, `get_logs`).
2. **Explicit Write Denial**: `send_raw_transaction` and arbitrary unallowlisted tools are blocked at the client boundary before any network dispatch.
3. **Zero Private Keys**: No private keys are generated, stored, requested, or processed.
4. **No Financial Authority**: Every decision includes an immutable execution notice stating that `PASS` indicates policy compliance only and does NOT authorize or broadcast any blockchain transaction.
5. **No Mock Fallback**: If `https://mcp.pharos.xyz/mcp` is unreachable, the system halts with an honest connection error (`INSUFFICIENT_DATA`). It never falls back to synthetic or static balances.

---

## 8. Limitations & Provenance

- **Hosted Server Binding**: The official hosted MCP server at `https://mcp.pharos.xyz/mcp` connects to **Pharos Pacific Mainnet (Chain ID 1672)**. It does not provide tool parameters to switch to Atlantic Testnet (`688689`). This is documented as an official platform characteristic.
- **Non-Atomic Queries**: Separate MCP tool calls return blocks from their respective execution instants (`latestBlock` vs `blockNumber`). The system honestly records per-tool block context rather than pretending queries are atomic.
- **Block Context Availability**: `get_gas_price` and `get_balance` schemas return only numeric prices/balances without block numbers; their block context is explicitly labeled `UNAVAILABLE_IN_SCHEMA`.
- **SkillEngine Implementation**: The project follows the official `SKILL.md` specification standard. The Python evaluator in `flow/evaluator.py` is a project-authored local orchestration runtime implementing these instructions deterministically; no claim is made of a proprietary hosted SkillEngine execution service.

---

## 9. Official Pharos Resources

- **Pharos DevHub**: [https://www.pharos.xyz/devhub](https://www.pharos.xyz/devhub)
- **Pharos AI Platform**: [https://ai.pharos.xyz/](https://ai.pharos.xyz/)
- **Hosted Chain MCP**: `https://mcp.pharos.xyz/mcp`
- **Chain MCP Repository**: [https://github.com/PharosNetwork/pharos-mcp](https://github.com/PharosNetwork/pharos-mcp)
- **SkillEngine Repository**: [https://github.com/PharosNetwork/pharos-skill-engine](https://github.com/PharosNetwork/pharos-skill-engine)
- **Pharos Pacific Explorer**: [https://www.pharosscan.xyz/](https://www.pharosscan.xyz/)
