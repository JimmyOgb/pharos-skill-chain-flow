"""Data models for Pharos Chain MCP protocol, provenance tracking, and SkillEngine decision rules."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import datetime


class DecisionOutcome(str, Enum):
    """Possible outcomes of the SkillEngine operational evaluation."""
    PASS = "PASS"
    BLOCK = "BLOCK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class MCPToolDefinition:
    """Metadata for a discovered MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    is_read_only: bool


@dataclass
class MCPResponse:
    """Preserves raw protocol response with verifiable per-tool provenance."""
    id: int
    session_id: str
    tool_name: str
    arguments: Dict[str, Any]
    raw_text: str
    parsed_json: Dict[str, Any]
    is_error: bool
    latency_ms: float
    sha256_hash: str
    utc_timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    # Block context is tracked per-tool: None indicates the tool schema does not supply block height
    block_context: Optional[int] = None
    chain_id: Optional[int] = None


@dataclass(frozen=True)
class ChainInfo:
    """Normalized network identity from get_chain_info."""
    name: str
    chain_id: int
    chain_id_hex: str
    latest_block: int
    native_symbol: str
    rpc_url: str


@dataclass(frozen=True)
class GasPrice:
    """Normalized gas telemetry from get_gas_price."""
    gas_price_wei: int
    gas_price_gwei: float
    gas_price_hex: str
    max_priority_fee_per_gas_gwei: float
    # get_gas_price does not report block context in its return schema
    block_context_available: bool = False


@dataclass(frozen=True)
class NativeBalance:
    """Normalized account balance from get_balance."""
    address: str
    balance_wei: int
    balance_pros: float
    symbol: str


@dataclass(frozen=True)
class BlockHeader:
    """Normalized block context from get_block."""
    hash: str
    number: int
    timestamp: int
    gas_used: int
    miner: str


@dataclass
class ValidatedChainContext:
    """Guaranteed live, unmocked chain context passed to downstream SkillEngine."""
    chain_info: ChainInfo
    gas_price: GasPrice
    block_number: int
    balance: Optional[NativeBalance]
    session_id: str
    provenance_hash: str
    retrieval_timestamp: str
    tool_responses: List[MCPResponse] = field(default_factory=list)


@dataclass
class OperationPolicy:
    """User-configurable operational policy thresholds.
    
    NOTE: These are operator-defined policy criteria, NOT authoritative Pharos
    consensus rules or blockchain execution limits.
    """
    name: str = "Default Live Network Operations Policy"
    expected_chain_id: int = 1672
    max_gas_price_gwei: float = 25.0
    max_block_staleness: int = 50
    min_balance_pros: Optional[float] = None
    target_address: Optional[str] = None
    require_balance_check: bool = False


@dataclass
class SkillDecision:
    """The structured, traceable result produced by SkillEngine evaluation."""
    outcome: DecisionOutcome
    deciding_rule: str
    rule_description: str
    justification: str
    policy_inputs: Dict[str, Any]
    live_evidence: Dict[str, Any]
    tool_traces: List[Dict[str, Any]]
    evaluated_at: str
    provenance_fingerprint: str
    execution_notice: str = (
        "CONFIRMATION NOTICE: A PASS outcome indicates that live chain parameters "
        "satisfy operator policy criteria. It does NOT authorize, sign, or broadcast "
        "any blockchain transaction."
    )
