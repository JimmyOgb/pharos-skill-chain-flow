"""Tests for package assets, networks configuration, SKILL.md specification, and connection errors."""

import json
from pathlib import Path
import pytest
import requests

from flow.mcp_client import PharosChainMCPClient
from flow.models import BlockHeader
from flow.provenance import ProtocolValidationError


def test_networks_json_asset_valid():
    workspace_root = Path(__file__).resolve().parent.parent
    networks_path = workspace_root / "assets" / "networks.json"
    assert networks_path.is_file(), "assets/networks.json must exist"

    with open(networks_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "networks" in data
    assert "defaultNetwork" in data
    networks = {n["name"]: n for n in data["networks"]}

    # Verify Pacific Mainnet
    assert "mainnet" in networks
    assert networks["mainnet"]["chainId"] == 1672
    assert networks["mainnet"]["nativeToken"] == "PROS"
    assert networks["mainnet"]["mcpUrl"] == "https://mcp.pharos.xyz/mcp"

    # Verify Atlantic Testnet
    assert "atlantic-testnet" in networks
    assert networks["atlantic-testnet"]["chainId"] == 688689
    assert networks["atlantic-testnet"]["nativeToken"] == "PHRS"


def test_skill_md_frontmatter_valid():
    workspace_root = Path(__file__).resolve().parent.parent
    skill_path = workspace_root / "SKILL.md"
    assert skill_path.is_file(), "SKILL.md must exist in root"

    content = skill_path.read_text(encoding="utf-8")
    assert content.startswith("---"), "SKILL.md must start with YAML frontmatter"
    assert "name: pharos-skill-chain-flow" in content
    assert "version: 0.1.0" in content
    assert "requires:" in content


def test_mcp_client_invalid_endpoint_raises_protocol_validation():
    # Attempting to initialize against an invalid local port
    client = PharosChainMCPClient(endpoint_url="http://127.0.0.1:59999/invalid_mcp", timeout=1.0)
    with pytest.raises(ProtocolValidationError, match="Failed to connect to MCP"):
        client.initialize()


def test_block_header_dataclass_fields():
    header = BlockHeader(
        hash="0xabcdef123456",
        number=21940000,
        timestamp=1730560000,
        gas_used=123456,
        miner="0x0000000000000000000000000000000000000000",
    )
    assert header.number == 21940000
    assert header.gas_used == 123456
    assert header.hash == "0xabcdef123456"
