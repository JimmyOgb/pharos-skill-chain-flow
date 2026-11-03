"""Official Pharos Chain MCP client with strict read-only tool allowlisting."""

import json
import time
from typing import Any, Dict, List, Optional
import requests

from .models import (
    BlockHeader,
    ChainInfo,
    GasPrice,
    MCPResponse,
    MCPToolDefinition,
    NativeBalance,
    ValidatedChainContext,
)
from .provenance import (
    NetworkMismatchError,
    ProtocolValidationError,
    SecurityViolationError,
    build_validated_chain_context,
    compute_sha256,
    parse_sse_event,
    validate_chain_identity,
    validate_jsonrpc_match,
    validate_session,
)

DEFAULT_MCP_ENDPOINT = "https://mcp.pharos.xyz/mcp"
DEFAULT_TIMEOUT_SECONDS = 25.0
DEFAULT_USER_AGENT = "PharosChainFlowClient/1.0 (+https://github.com/JimmyOgb/pharos-skill-chain-flow)"

# Strict read-only allowlist: Only audited read-only tools may be invoked
READ_ONLY_TOOL_ALLOWLIST = {
    "get_chain_info",
    "get_block_number",
    "get_gas_price",
    "get_balance",
    "get_block",
    "get_transaction_count",
    "get_transaction",
    "get_transaction_receipt",
    "get_code",
    "get_storage_at",
    "eth_call",
    "estimate_gas",
    "get_logs",
}

# Explicitly forbidden write-capable tools
EXPLICITLY_DENIED_TOOLS = {
    "send_raw_transaction",
    "eth_sendTransaction",
    "eth_sendRawTransaction",
}


class PharosChainMCPClient:
    """Official client for interacting with the Pharos Chain MCP server over HTTP/SSE."""

    def __init__(
        self,
        endpoint_url: str = DEFAULT_MCP_ENDPOINT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })
        self._session_id: Optional[str] = None
        self._server_info: Optional[Dict[str, Any]] = None
        self._request_counter = 0

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def server_info(self) -> Optional[Dict[str, Any]]:
        return self._server_info

    def _next_id(self) -> int:
        self._request_counter += 1
        return self._request_counter

    def initialize(self) -> Dict[str, Any]:
        """Performs official MCP protocol initialize handshake."""
        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "pharos-chain-flow-client",
                    "version": "1.0.0",
                },
            },
        }

        try:
            resp = self.session.post(self.endpoint_url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ProtocolValidationError(f"Failed to connect to MCP endpoint: {exc}") from exc

        session_id = resp.headers.get("mcp-session-id")
        self._session_id = validate_session(session_id)
        self.session.headers["mcp-session-id"] = self._session_id

        parsed = parse_sse_event(resp.text)
        validate_jsonrpc_match(req_id, parsed)

        result = parsed.get("result", {})
        self._server_info = result.get("serverInfo", {})

        # Send initialized notification per MCP specification
        self._send_notification("notifications/initialized")
        return self._server_info

    def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Sends an un-id'd MCP notification."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        try:
            self.session.post(self.endpoint_url, json=payload, timeout=self.timeout)
        except requests.exceptions.RequestException:
            pass

    def list_tools(self) -> List[MCPToolDefinition]:
        """Discovers tools advertised by the MCP server and tags them with allowlist status."""
        if not self._session_id:
            self.initialize()

        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/list",
            "params": {},
        }

        resp = self.session.post(self.endpoint_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()

        parsed = parse_sse_event(resp.text)
        validate_jsonrpc_match(req_id, parsed)

        raw_tools = parsed.get("result", {}).get("tools", [])
        definitions = []
        for t in raw_tools:
            name = t.get("name", "")
            is_read_only = name in READ_ONLY_TOOL_ALLOWLIST and name not in EXPLICITLY_DENIED_TOOLS
            definitions.append(
                MCPToolDefinition(
                    name=name,
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    is_read_only=is_read_only,
                )
            )
        return definitions

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> MCPResponse:
        """Invokes a tool on the MCP server with strict read-only allowlisting."""
        if tool_name in EXPLICITLY_DENIED_TOOLS:
            raise SecurityViolationError(
                f"Security Violation: Tool '{tool_name}' is explicitly denied (write/signing capability)."
            )

        if tool_name not in READ_ONLY_TOOL_ALLOWLIST:
            raise SecurityViolationError(
                f"Security Violation: Tool '{tool_name}' is not in the verified read-only allowlist."
            )

        if not self._session_id:
            self.initialize()

        req_id = self._next_id()
        args = arguments or {}
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args,
            },
        }

        start_time = time.perf_counter()
        resp = self.session.post(self.endpoint_url, json=payload, timeout=self.timeout)
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        resp.raise_for_status()

        raw_text = resp.text
        sha256_hash = compute_sha256(raw_text)
        parsed = parse_sse_event(raw_text)
        validate_jsonrpc_match(req_id, parsed)

        is_error = "error" in parsed or parsed.get("result", {}).get("isError", False)

        # Extract per-tool block and chain metadata if available
        block_ctx: Optional[int] = None
        chain_ctx: Optional[int] = None
        content = parsed.get("result", {}).get("content", [])
        if content and isinstance(content, list):
            try:
                inner = json.loads(content[0].get("text", "{}"))
                if "chainId" in inner:
                    chain_ctx = int(inner["chainId"])
                if "latestBlock" in inner:
                    block_ctx = int(inner["latestBlock"])
                elif "blockNumber" in inner:
                    block_ctx = int(inner["blockNumber"])
                elif "number" in inner:
                    val = str(inner["number"])
                    block_ctx = int(val, 16) if val.startswith("0x") else int(val)
            except Exception:
                pass

        return MCPResponse(
            id=req_id,
            session_id=self._session_id or "",
            tool_name=tool_name,
            arguments=args,
            raw_text=raw_text,
            parsed_json=parsed,
            is_error=is_error,
            latency_ms=round(latency_ms, 2),
            sha256_hash=sha256_hash,
            block_context=block_ctx,
            chain_id=chain_ctx,
        )

    # High-level typed read operations

    def get_chain_info(self) -> (ChainInfo, MCPResponse):
        """Retrieves and normalizes live chain metadata from get_chain_info."""
        resp = self.call_tool("get_chain_info", {})
        content = resp.parsed_json.get("result", {}).get("content", [])
        if not content:
            raise ProtocolValidationError("Empty content in get_chain_info response")
        inner = json.loads(content[0]["text"])

        info = ChainInfo(
            name=inner.get("name", ""),
            chain_id=int(inner.get("chainId", 0)),
            chain_id_hex=inner.get("chainIdHex", ""),
            latest_block=int(inner.get("latestBlock", 0)),
            native_symbol=inner.get("nativeSymbol", "PROS"),
            rpc_url=inner.get("rpcUrl", ""),
        )
        validate_chain_identity(info)
        return info, resp

    def get_block_number(self) -> (int, MCPResponse):
        """Retrieves current block height from get_block_number."""
        resp = self.call_tool("get_block_number", {})
        content = resp.parsed_json.get("result", {}).get("content", [])
        if not content:
            raise ProtocolValidationError("Empty content in get_block_number response")
        inner = json.loads(content[0]["text"])
        return int(inner.get("blockNumber", 0)), resp

    def get_gas_price(self) -> (GasPrice, MCPResponse):
        """Retrieves current gas price from get_gas_price."""
        resp = self.call_tool("get_gas_price", {})
        content = resp.parsed_json.get("result", {}).get("content", [])
        if not content:
            raise ProtocolValidationError("Empty content in get_gas_price response")
        inner = json.loads(content[0]["text"])

        gp = GasPrice(
            gas_price_wei=int(inner.get("gasPriceWei", 0)),
            gas_price_gwei=float(inner.get("gasPriceGwei", 0)),
            gas_price_hex=inner.get("gasPriceHex", ""),
            max_priority_fee_per_gas_gwei=float(inner.get("maxPriorityFeePerGasGwei", 0)),
            block_context_available=False,
        )
        return gp, resp

    def get_balance(self, address: str) -> (NativeBalance, MCPResponse):
        """Retrieves native token balance for an address from get_balance."""
        resp = self.call_tool("get_balance", {"address": address})
        content = resp.parsed_json.get("result", {}).get("content", [])
        if not content:
            raise ProtocolValidationError("Empty content in get_balance response")
        inner = json.loads(content[0]["text"])

        wei = int(inner.get("balanceWei", 0))
        pros = wei / 1e18

        bal = NativeBalance(
            address=inner.get("address", address),
            balance_wei=wei,
            balance_pros=pros,
            symbol=inner.get("symbol", "PROS"),
        )
        return bal, resp

    def get_block(self, block: str = "latest") -> (BlockHeader, MCPResponse):
        """Retrieves block details from get_block."""
        resp = self.call_tool("get_block", {"block": block, "includeTransactions": False})
        content = resp.parsed_json.get("result", {}).get("content", [])
        if not content:
            raise ProtocolValidationError("Empty content in get_block response")
        inner = json.loads(content[0]["text"])

        blk = BlockHeader(
            hash=inner.get("hash", ""),
            number=int(str(inner.get("number", "0")), 16) if str(inner.get("number", "")).startswith("0x") else int(inner.get("number", 0)),
            timestamp=int(str(inner.get("timestamp", "0")), 16) if str(inner.get("timestamp", "")).startswith("0x") else int(inner.get("timestamp", 0)),
            gas_used=int(str(inner.get("gasUsed", "0")), 16) if str(inner.get("gasUsed", "")).startswith("0x") else int(inner.get("gasUsed", 0)),
            miner=inner.get("miner", ""),
        )
        return blk, resp

    def fetch_live_context(self, address: Optional[str] = None) -> ValidatedChainContext:
        """Retrieves and validates live chain context for downstream SkillEngine execution."""
        traces: List[MCPResponse] = []

        chain_info, resp_chain = self.get_chain_info()
        traces.append(resp_chain)

        block_number, resp_block = self.get_block_number()
        traces.append(resp_block)

        gas_price, resp_gas = self.get_gas_price()
        traces.append(resp_gas)

        balance: Optional[NativeBalance] = None
        if address:
            balance, resp_bal = self.get_balance(address)
            traces.append(resp_bal)

        ctx = build_validated_chain_context(
            chain_info=chain_info,
            gas_price=gas_price,
            block_number=block_number,
            session_id=self._session_id or "",
            balance=balance,
        )
        ctx.tool_responses = traces
        return ctx
