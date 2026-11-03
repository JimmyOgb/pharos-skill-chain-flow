"""Provenance tracking and validation gates for Pharos Chain MCP integration."""

import hashlib
import json
from typing import Any, Dict, Optional

from .models import (
    ChainInfo,
    GasPrice,
    NativeBalance,
    BlockHeader,
    ValidatedChainContext,
    MCPResponse,
)


class ProvenanceError(Exception):
    """Base exception for provenance and integrity violations."""
    pass


class NetworkMismatchError(ProvenanceError):
    """Raised when Chain MCP reports an unexpected network or chain ID."""
    pass


class SecurityViolationError(ProvenanceError):
    """Raised when an unauthorized or write-capable tool is requested."""
    pass


class ProtocolValidationError(ProvenanceError):
    """Raised when an MCP response violates JSON-RPC 2.0 or SSE specifications."""
    pass


def compute_sha256(text: str) -> str:
    """Computes a SHA-256 hex digest for verifiable telemetry integrity."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_sse_event(raw_sse: str) -> Dict[str, Any]:
    """Parses Server-Sent Events (SSE) payload to extract the JSON-RPC object.
    
    Args:
        raw_sse: Raw text stream containing SSE events (e.g. 'data: {...}').
        
    Returns:
        The decoded JSON dictionary.
        
    Raises:
        ProtocolValidationError: If SSE contains no data or malformed JSON.
    """
    if not raw_sse or not raw_sse.strip():
        raise ProtocolValidationError("Empty SSE payload received from server")

    for line in raw_sse.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("data:"):
            json_str = line_clean[5:].strip()
            if not json_str:
                continue
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as exc:
                raise ProtocolValidationError(f"Invalid JSON inside SSE data event: {exc}") from exc

    # If raw_sse was a raw JSON-RPC body rather than SSE
    try:
        return json.loads(raw_sse)
    except json.JSONDecodeError:
        raise ProtocolValidationError(f"Failed to find valid 'data:' event in SSE text: {raw_sse[:200]}")


def validate_session(session_id: Optional[str]) -> str:
    """Ensures a valid, non-empty session ID was provided by the MCP server."""
    if not session_id or not session_id.strip():
        raise ProtocolValidationError("MCP server did not provide a valid 'mcp-session-id' header")
    return session_id.strip()


def validate_jsonrpc_match(request_id: int, response_obj: Dict[str, Any]) -> None:
    """Verifies that the JSON-RPC response ID matches the request ID."""
    resp_id = response_obj.get("id")
    if resp_id != request_id:
        raise ProtocolValidationError(
            f"JSON-RPC request/response ID mismatch: expected {request_id}, got {resp_id}"
        )


def validate_chain_identity(chain_info: ChainInfo, expected_chain_id: int = 1672) -> None:
    """Asserts that the MCP server is communicating with the expected Pharos network."""
    if chain_info.chain_id != expected_chain_id:
        raise NetworkMismatchError(
            f"Network mismatch: expected Pharos Pacific Mainnet (Chain ID {expected_chain_id}), "
            f"but MCP server reported Chain ID {chain_info.chain_id} ({chain_info.name})"
        )
    if not chain_info.rpc_url:
        raise NetworkMismatchError("MCP chain info did not include an RPC URL")


def validate_gas_price(gas_price: GasPrice) -> None:
    """Validates that gas price metrics are positive and realistic."""
    if gas_price.gas_price_wei <= 0:
        raise ProtocolValidationError(f"Invalid non-positive gas price: {gas_price.gas_price_wei} wei")
    if gas_price.gas_price_gwei <= 0:
        raise ProtocolValidationError(f"Invalid non-positive gas price in Gwei: {gas_price.gas_price_gwei}")


def validate_balance(balance: NativeBalance) -> None:
    """Validates balance structure."""
    if balance.balance_wei < 0:
        raise ProtocolValidationError(f"Negative balance reported: {balance.balance_wei}")
    if not balance.address.startswith("0x") or len(balance.address) != 42:
        raise ProtocolValidationError(f"Malformed EVM address in balance: {balance.address}")


def build_validated_chain_context(
    chain_info: ChainInfo,
    gas_price: GasPrice,
    block_number: int,
    session_id: str,
    balance: Optional[NativeBalance] = None,
) -> ValidatedChainContext:
    """Constructs a validated context object with composite provenance fingerprint."""
    validate_chain_identity(chain_info)
    validate_gas_price(gas_price)
    if balance is not None:
        validate_balance(balance)
    if block_number <= 0:
        raise ProtocolValidationError(f"Invalid non-positive block number: {block_number}")

    # Compute a composite SHA-256 fingerprint representing the combined live telemetry
    composite_repr = (
        f"chain:{chain_info.chain_id}|block:{block_number}|gas_gwei:{gas_price.gas_price_gwei}|"
        f"session:{session_id}"
    )
    provenance_hash = compute_sha256(composite_repr)

    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return ValidatedChainContext(
        chain_info=chain_info,
        gas_price=gas_price,
        block_number=block_number,
        balance=balance,
        session_id=session_id,
        provenance_hash=provenance_hash,
        retrieval_timestamp=now_iso,
    )
