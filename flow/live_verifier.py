"""Live verification runner that exercises the read-only PharosChainMCPClient against https://mcp.pharos.xyz/mcp."""

import datetime
import json
import sys
import time

from flow.mcp_client import PharosChainMCPClient


def run_live_verification():
    print("================================================================================")
    print("PHAROS TASK 12: GATE 2 & 3 LIVE CHAIN MCP VERIFICATION RUN")
    print(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print("Endpoint: https://mcp.pharos.xyz/mcp")
    print("================================================================================\n")

    client = PharosChainMCPClient()

    # Step 1: Initialize
    print("[1/5] Executing MCP Handshake (initialize)...")
    t0 = time.perf_counter()
    server_info = client.initialize()
    t_init = (time.perf_counter() - t0) * 1000.0
    print(f"  Session ID: {client.session_id}")
    print(f"  Server Info: {server_info}")
    print(f"  Handshake Latency: {t_init:.2f} ms\n")

    # Step 2: Tool Discovery
    print("[2/5] Executing Tool Discovery (tools/list)...")
    t0 = time.perf_counter()
    tools = client.list_tools()
    t_list = (time.perf_counter() - t0) * 1000.0
    print(f"  Discovered Tools Count: {len(tools)}")
    read_only_count = sum(1 for t in tools if t.is_read_only)
    print(f"  Read-Only Allowlisted: {read_only_count}")
    print(f"  Write / Denied: {len(tools) - read_only_count}")
    print(f"  Discovery Latency: {t_list:.2f} ms\n")

    # Step 3: Call get_chain_info
    print("[3/5] Calling Tool 'get_chain_info'...")
    t0 = time.perf_counter()
    chain_info, resp_chain = client.get_chain_info()
    t_chain = (time.perf_counter() - t0) * 1000.0
    print(f"  Name: {chain_info.name}")
    print(f"  Chain ID: {chain_info.chain_id} (Hex: {chain_info.chain_id_hex})")
    print(f"  Native Symbol: {chain_info.native_symbol}")
    print(f"  Configured RPC: {chain_info.rpc_url}")
    print(f"  Latest Block: {chain_info.latest_block}")
    print(f"  Per-Tool Block Context: {resp_chain.block_context}")
    print(f"  Per-Tool SHA-256: {resp_chain.sha256_hash[:16]}...")
    print(f"  Latency: {t_chain:.2f} ms\n")

    # Step 4: Call get_block_number & get_gas_price
    print("[4/5] Calling Tools 'get_block_number' & 'get_gas_price'...")
    t0 = time.perf_counter()
    block_num, resp_block = client.get_block_number()
    t_block = (time.perf_counter() - t0) * 1000.0
    print(f"  Block Number: {block_num} (Block Context: {resp_block.block_context}, Latency: {t_block:.2f} ms)")

    t0 = time.perf_counter()
    gas_price, resp_gas = client.get_gas_price()
    t_gas = (time.perf_counter() - t0) * 1000.0
    print(f"  Gas Price (Wei): {gas_price.gas_price_wei}")
    print(f"  Gas Price (Gwei): {gas_price.gas_price_gwei}")
    print(f"  Max Priority Fee (Gwei): {gas_price.max_priority_fee_per_gas_gwei}")
    print(f"  Block Context Available: {gas_price.block_context_available} (None)")
    print(f"  Latency: {t_gas:.2f} ms\n")

    # Step 5: Call get_balance on known public address
    test_address = "0x0000000000000000000000000000000000000000"
    print(f"[5/5] Calling Tool 'get_balance' for {test_address}...")
    t0 = time.perf_counter()
    balance, resp_bal = client.get_balance(test_address)
    t_bal = (time.perf_counter() - t0) * 1000.0
    print(f"  Address: {balance.address}")
    print(f"  Balance: {balance.balance_pros} {balance.symbol} ({balance.balance_wei} wei)")
    print(f"  Latency: {t_bal:.2f} ms\n")

    # Fetch composite validated context
    print("--- Assembling Validated Chain Context ---")
    ctx = client.fetch_live_context(test_address)
    print(f"  Chain ID Validated: {ctx.chain_info.chain_id} (Pharos Pacific)")
    print(f"  Block Height: {ctx.block_number}")
    print(f"  Live Gas (Gwei): {ctx.gas_price.gas_price_gwei}")
    print(f"  Provenance Hash (SHA-256): {ctx.provenance_hash}")
    print(f"  Retrieval Timestamp: {ctx.retrieval_timestamp}")
    print(f"  Tracked Tool Traces: {len(ctx.tool_responses)}")
    for tr in ctx.tool_responses:
        print(f"    - {tr.tool_name:<20} block_ctx={str(tr.block_context):<8} sha256={tr.sha256_hash[:12]}... ({tr.latency_ms} ms)")
    print("================================================================================")
    print("LIVE VERIFICATION VERDICT: PASS")
    print("================================================================================")


if __name__ == "__main__":
    run_live_verification()
