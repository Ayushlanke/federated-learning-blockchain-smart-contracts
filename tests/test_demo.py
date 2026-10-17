"""Tests for the BC-FL-SRV decentralized FL demonstration layer.

Tests cover:
  1. Blockchain ledger: hashing, chaining, quorum, replication, tamper detection.
  2. FL Client: Ed25519 identity, update commitment, signature, local training step.
  3. Verification layer: valid updates accepted, tampered updates rejected.
  4. Tampering demo: byte flip, forged commitment, unknown identity.
  5. End-to-end mini demo pipeline run.
  6. Visualization generation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from bcflsrv.crypto.identity import Identity, SigContext
from bcflsrv.demo.blockchain import (
    GENESIS_HASH,
    Block,
    BlockEvent,
    BlockVerificationError,
    DistributedLedger,
    LedgerNode,
)
from bcflsrv.demo.client import (
    ClientUpdate,
    FLClient,
    MaliciousClient,
    commit_update,
    verify_update_commitment,
)
from bcflsrv.demo.verification import (
    TamperingDemo,
    UpdateVerifier,
    VerificationResult,
    VerificationStatus,
)
from bcflsrv.demo.pipeline import DemoConfig, run_demo
from bcflsrv.demo.visualize import generate_all_figures
from bcflsrv.fl.data import ClientShard, FashionMNIST
from bcflsrv.fl.model import SmallCNN, TrainConfig, count_parameters, get_flat_params


# --------------------------------------------------------------------------
# Blockchain Ledger Unit Tests
# --------------------------------------------------------------------------

def test_block_hash_deterministic():
    blk = Block(
        index=0,
        prev_hash=GENESIS_HASH,
        fl_round=0,
        event_type=BlockEvent.ROUND_START,
        timestamp="2026-01-01T00:00:00Z",
    )
    h1 = blk.compute_hash()
    h2 = blk.compute_hash()
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_block_chaining_and_node_verification():
    node = LedgerNode("test-node-0")
    assert node.height == 0
    assert node.tip_hash == GENESIS_HASH

    blk0 = Block(
        index=0,
        prev_hash=GENESIS_HASH,
        fl_round=0,
        event_type=BlockEvent.ROUND_START,
        timestamp="2026-01-01T00:00:01Z",
    ).seal()

    ok, reason = node.verify_block(blk0)
    assert ok, reason
    node.append(blk0)
    assert node.height == 1
    assert node.tip_hash == blk0.block_hash

    # Block 1
    blk1 = Block(
        index=1,
        prev_hash=blk0.block_hash,
        fl_round=1,
        event_type=BlockEvent.UPDATE_SUBMIT,
        timestamp="2026-01-01T00:00:02Z",
    ).seal()

    ok, reason = node.verify_block(blk1)
    assert ok, reason
    node.append(blk1)
    assert node.height == 2

    # Block 2 with wrong prev_hash should be rejected
    blk2_bad = Block(
        index=2,
        prev_hash="ff" * 32,
        fl_round=1,
        event_type=BlockEvent.ROUND_END,
        timestamp="2026-01-01T00:00:03Z",
    ).seal()

    ok, reason = node.verify_block(blk2_bad)
    assert not ok
    assert "prev_hash" in reason


def test_distributed_ledger_quorum_and_replication():
    ledger = DistributedLedger(n_nodes=3, quorum_size=2)
    assert len(ledger.nodes) == 3
    assert ledger.height == 0

    # Propose block 0
    blk0, reasons = ledger.propose_block(
        fl_round=0,
        event_type=BlockEvent.ROUND_START,
    )
    assert blk0 is not None
    assert len(reasons) == 0
    assert ledger.height == 1
    assert ledger.chains_are_consistent()

    # All nodes must verify OK
    verifs = ledger.verify_all_nodes()
    for node_id, (ok, bad_idx) in verifs.items():
        assert ok, f"Node {node_id} verification failed at {bad_idx}"


def test_distributed_ledger_tamper_detection():
    ledger = DistributedLedger(n_nodes=3, quorum_size=2)
    blk0, _ = ledger.propose_block(fl_round=0, event_type=BlockEvent.ROUND_START)
    blk1, _ = ledger.propose_block(fl_round=1, event_type=BlockEvent.UPDATE_SUBMIT)
    assert ledger.height == 2
    assert ledger.chains_are_consistent()

    # Intentionally corrupt node 1's block payload
    corrupt_block = ledger.nodes[1]._chain[1]
    corrupt_block.participating_clients = ["malicious_client_injected"]

    # Now node 1's chain should fail verification because hash doesn't match payload
    verifs = ledger.verify_all_nodes()
    ok_node_1, bad_idx = verifs["ledger-node-1"]
    assert not ok_node_1
    assert bad_idx == 1

    # And ledger consistency check should fail
    assert not ledger.chains_are_consistent()


def test_ledger_jsonl_save_and_load(tmp_path: Path):
    ledger = DistributedLedger(n_nodes=3, quorum_size=2)
    ledger.propose_block(fl_round=0, event_type=BlockEvent.ROUND_START)
    ledger.propose_block(
        fl_round=1,
        event_type=BlockEvent.UPDATE_SUBMIT,
        accepted_count=4,
        rejected_count=1,
    )

    save_path = tmp_path / "chain.jsonl"
    ledger.save(save_path)
    assert save_path.exists()

    loaded_blocks = DistributedLedger.load_chain(save_path)
    assert len(loaded_blocks) == 2
    assert loaded_blocks[0].index == 0
    assert loaded_blocks[1].index == 1
    assert loaded_blocks[1].accepted_count == 4


# --------------------------------------------------------------------------
# Client and Commitment Unit Tests
# --------------------------------------------------------------------------

def test_client_commitment_and_signature():
    cid = "client_001"
    fl_round = 1
    update = np.array([0.1, -0.2, 0.5, 0.0], dtype=np.float32)

    c1 = commit_update(cid, fl_round, update)
    c2 = commit_update(cid, fl_round, update)
    assert c1 == c2

    # Different round or different client produces different commitment
    c_diff_round = commit_update(cid, fl_round + 1, update)
    c_diff_client = commit_update("client_002", fl_round, update)
    assert c1 != c_diff_round
    assert c1 != c_diff_client

    assert verify_update_commitment(cid, fl_round, update, c1)
    assert not verify_update_commitment(cid, fl_round, update + 1.0, c1)


def test_fl_client_update_generation():
    seed_bytes = b"\x01" * 32
    # Create small dummy dataset
    x = np.random.randn(10, 1, 28, 28).astype(np.float32)
    y = np.random.randint(0, 10, size=(10,)).astype(np.int64)
    dataset = FashionMNIST(x_train=x, y_train=y, x_test=x, y_test=y)

    shard = ClientShard(client_id="client_test", indices=np.arange(10))

    client = FLClient(
        seed_bytes=seed_bytes,
        shard=shard,
        train_config=TrainConfig(epochs=1, max_batches=2, lr=0.01),
    )

    model = SmallCNN()
    global_params = get_flat_params(model)

    client.receive_global_model(global_params)
    client_up = client.train_and_submit(fl_round=1, dataset=dataset)
    assert client_up.client_id == client.client_id
    assert client_up.fl_round == 1
    assert client_up.verify_signature()
    assert verify_update_commitment(
        client_up.client_id, 1, client_up.update, client_up.commitment
    )


# --------------------------------------------------------------------------
# Verification Layer & Tampering Attacks
# --------------------------------------------------------------------------

def test_update_verifier_normal_and_attacks():
    id_a = Identity.from_seed(b"\x01" * 32)
    id_b = Identity.from_seed(b"\x02" * 32)
    cid_a = id_a.id
    cid_b = id_b.id

    registry = {
        cid_a: id_a.public_key,
        cid_b: id_b.public_key,
    }
    verifier = UpdateVerifier(registry=registry, expected_round=1, max_update_norm=100.0)

    # 1. Honest update
    up_val = np.array([0.5, -0.1], dtype=np.float32)
    commit_a = commit_update(cid_a, 1, up_val)
    sig_a = id_a.sign(SigContext.SUBMISSION, commit_a)

    honest_update = ClientUpdate(
        client_id=cid_a,
        public_key=id_a.public_key,
        fl_round=1,
        update=up_val,
        commitment=commit_a,
        signature=sig_a,
        n_samples=50,
        local_loss=0.5,
    )
    res = verifier.verify(honest_update)
    assert res.accepted
    assert res.status == VerificationStatus.ACCEPTED

    # 2. Tampered update (payload modified after signing)
    tampered_up = TamperingDemo.tamper_update_bytes(honest_update)
    res_tampered = verifier.verify(tampered_up)
    assert not res_tampered.accepted
    assert res_tampered.status == VerificationStatus.REJECTED_COMMIT

    # 3. Forged commitment (commitment modified, sig invalid)
    forged_commit = TamperingDemo.forge_commitment(honest_update)
    res_forged = verifier.verify(forged_commit)
    assert not res_forged.accepted
    assert res_forged.status in (
        VerificationStatus.REJECTED_SIG,
        VerificationStatus.REJECTED_COMMIT,
    )

    # 4. Unknown identity
    spoofed = TamperingDemo.spoof_identity(honest_update)
    res_spoofed = verifier.verify(spoofed)
    assert not res_spoofed.accepted
    assert res_spoofed.status == VerificationStatus.REJECTED_UNKNOWN


# --------------------------------------------------------------------------
# Mini End-to-End Pipeline Run
# --------------------------------------------------------------------------

def test_mini_demo_pipeline_run(tmp_path: Path):
    # Create synthetic dataset to run fast in testing
    rng = np.random.default_rng(42)
    x_train = rng.standard_normal((300, 1, 28, 28)).astype(np.float32)
    y_train = rng.integers(0, 10, size=300).astype(np.int64)
    x_test = rng.standard_normal((50, 1, 28, 28)).astype(np.float32)
    y_test = rng.integers(0, 10, size=50).astype(np.int64)

    dataset = FashionMNIST(
        x_train=x_train, y_train=y_train, x_test=x_test, y_test=y_test
    )

    out_dir = tmp_path / "demo_output"
    cfg = DemoConfig(
        n_clients=3,
        n_rounds=2,
        dirichlet_alpha=1.0,
        train_config=TrainConfig(epochs=1, max_batches=2, lr=0.01),
        n_ledger_nodes=3,
        ledger_quorum=2,
        seed=123,
    )

    result = run_demo(dataset=dataset, config=cfg, output_dir=out_dir, verbose=False)
    assert result.final_accuracy >= 0.0
    assert len(result.rounds) == 2
    for r in result.rounds:
        assert r.n_submitted == 3
        assert r.n_accepted == 3
        assert r.n_rejected == 0

    # Check files created
    assert (out_dir / "blockchain.jsonl").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "rounds.json").exists()
    assert (out_dir / "final_model.npy").exists()

    # Verify blockchain in output
    blocks = DistributedLedger.load_chain(out_dir / "blockchain.jsonl")
    assert len(blocks) > 0

    # Check figures generation
    fig_dir = out_dir / "figures"
    generate_all_figures(result, blocks, fig_dir)
    assert (fig_dir / "dashboard.png").exists()
    assert (fig_dir / "accuracy_vs_round.png").exists()
    assert (fig_dir / "loss_vs_round.png").exists()
    assert (fig_dir / "participation.png").exists()
    assert (fig_dir / "blockchain_timeline.png").exists()


def test_malicious_client_attacks_and_signing():
    seed_bytes = b"\x09" * 32
    x = np.random.randn(10, 1, 28, 28).astype(np.float32)
    y = np.random.randint(0, 10, size=(10,)).astype(np.int64)
    dataset = FashionMNIST(x_train=x, y_train=y, x_test=x, y_test=y)
    shard = ClientShard(client_id="rogue_test", indices=np.arange(10))

    mc = MaliciousClient(
        seed_bytes=seed_bytes,
        shard=shard,
        train_config=TrainConfig(epochs=1, max_batches=2, lr=0.01),
        malice_rate=1.0,  # Guarantee attack
    )

    model = SmallCNN()
    global_params = get_flat_params(model)
    mc.receive_global_model(global_params)

    # Test that train_and_submit does not throw AttributeError: 'MaliciousClient' object has no attribute 'sign'
    for r in range(1, 10):
        up = mc.train_and_submit(fl_round=r, dataset=dataset)
        assert up.client_id == mc.client_id
        assert getattr(up, "tampered", False)
        assert getattr(up, "is_malicious", False)
        assert getattr(up, "attack_type", None) in [
            "broken_weights",
            "poisoned_gradients",
            "tampered_bytes",
            "forged_signature",
        ]

