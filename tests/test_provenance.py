"""Unit tests for provenance hashing, data validation, and chain identity checks.

NOTE: These tests use synthetic models to verify validation boundaries.
"""

import pytest

from flow.models import ChainInfo, GasPrice, NativeBalance
from flow.provenance import (
    NetworkMismatchError,
    ProtocolValidationError,
    build_validated_chain_context,
    compute_sha256,
    validate_balance,
    validate_chain_identity,
    validate_gas_price,
)


def test_compute_sha256_deterministic():
    h1 = compute_sha256("test-payload")
    h2 = compute_sha256("test-payload")
    h3 = compute_sha256("different-payload")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64


def test_validate_chain_identity_success():
    info = ChainInfo(
        name="Pharos",
        chain_id=1672,
        chain_id_hex="0x688",
        latest_block=21939000,
        native_symbol="PROS",
        rpc_url="https://rpc.pharos.xyz",
    )
    validate_chain_identity(info)  # Should not raise


def test_validate_chain_identity_mismatch_raises():
    info = ChainInfo(
        name="Atlantic",
        chain_id=688689,
        chain_id_hex="0xa8231",
        latest_block=32000000,
        native_symbol="PHRS",
        rpc_url="https://atlantic.dplabs-internal.com",
    )
    with pytest.raises(NetworkMismatchError, match="Network mismatch: expected Pharos Pacific Mainnet"):
        validate_chain_identity(info, expected_chain_id=1672)


def test_validate_chain_identity_missing_rpc_raises():
    info = ChainInfo(
        name="Pharos",
        chain_id=1672,
        chain_id_hex="0x688",
        latest_block=21939000,
        native_symbol="PROS",
        rpc_url="",
    )
    with pytest.raises(NetworkMismatchError, match="did not include an RPC URL"):
        validate_chain_identity(info, expected_chain_id=1672)


def test_validate_gas_price_success():
    gp = GasPrice(
        gas_price_wei=10000000000,
        gas_price_gwei=10.0,
        gas_price_hex="0x2540be400",
        max_priority_fee_per_gas_gwei=0.0,
    )
    validate_gas_price(gp)


def test_validate_gas_price_non_positive_raises():
    gp = GasPrice(
        gas_price_wei=0,
        gas_price_gwei=0.0,
        gas_price_hex="0x0",
        max_priority_fee_per_gas_gwei=0.0,
    )
    with pytest.raises(ProtocolValidationError, match="Invalid non-positive gas price"):
        validate_gas_price(gp)


def test_validate_balance_success():
    bal = NativeBalance(
        address="0x203987206124B5E28549C65005e8Fe2851532f8D",
        balance_wei=1000000000000000000,
        balance_pros=1.0,
        symbol="PROS",
    )
    validate_balance(bal)


def test_validate_balance_negative_raises():
    bal = NativeBalance(
        address="0x203987206124B5E28549C65005e8Fe2851532f8D",
        balance_wei=-1,
        balance_pros=-0.00001,
        symbol="PROS",
    )
    with pytest.raises(ProtocolValidationError, match="Negative balance reported"):
        validate_balance(bal)


def test_validate_balance_malformed_address_raises():
    bal = NativeBalance(
        address="0xinvalid",
        balance_wei=100,
        balance_pros=0.0001,
        symbol="PROS",
    )
    with pytest.raises(ProtocolValidationError, match="Malformed EVM address"):
        validate_balance(bal)


def test_build_validated_chain_context_creates_provenance_hash():
    info = ChainInfo(
        name="Pharos",
        chain_id=1672,
        chain_id_hex="0x688",
        latest_block=21939000,
        native_symbol="PROS",
        rpc_url="https://rpc.pharos.xyz",
    )
    gp = GasPrice(
        gas_price_wei=10000000000,
        gas_price_gwei=10.0,
        gas_price_hex="0x2540be400",
        max_priority_fee_per_gas_gwei=0.0,
    )
    ctx = build_validated_chain_context(
        chain_info=info,
        gas_price=gp,
        block_number=21939005,
        session_id="session-xyz",
    )
    assert ctx.chain_info.chain_id == 1672
    assert ctx.gas_price.gas_price_gwei == 10.0
    assert len(ctx.provenance_hash) == 64
    assert ctx.retrieval_timestamp is not None
