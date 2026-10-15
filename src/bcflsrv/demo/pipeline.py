"""Decentralized FL pipeline: ties clients, blockchain, verification, and aggregation.

This is the main orchestration layer for the BC-FL-SRV demonstration.

FL round protocol (one round)
------------------------------
1.  ROUND_START block recorded on ledger.
2.  Global model distributed to all participating clients.
3.  Each client trains locally and submits a signed update.
4.  UpdateVerifier checks each submission (sig, commitment, norm).
5.  UPDATE_SUBMIT block recorded on ledger with commitments + verification results.
6.  Accepted updates are aggregated via FedAvg (weighted by dataset size).
7.  New global model evaluated on test set.
8.  AGGREGATION block recorded (includes commitment to global model + accuracy).
9.  ROUND_END block recorded.
10. Next round begins from step 1.

Tampering demonstration
-----------------------
After the clean FL run, the pipeline runs a brief tampering demo:
  * One tampered update (flipped bytes) → rejected at commitment check.
  * One forged commitment → rejected at signature check.
  * One unknown identity → rejected at registry check.
  * Blockchain integrity after each rejection → verified.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from bcflsrv.demo.blockchain import Block, BlockEvent, DistributedLedger
from bcflsrv.demo.client import FLClient, ClientUpdate, commit_update
from bcflsrv.demo.verification import (
    UpdateVerifier,
    VerificationResult,
    VerificationStatus,
    TamperingDemo,
)
from bcflsrv.fl.data import FashionMNIST, ClientShard, dirichlet_partition
from bcflsrv.fl.model import (
    SmallCNN,
    TrainConfig,
    evaluate,
    fedavg,
    get_flat_params,
    set_flat_params,
)

__all__ = ["DemoConfig", "RoundRecord", "DemoResult", "run_demo"]


@dataclass
class DemoConfig:
    """Configuration for the decentralized FL demonstration."""
    n_clients: int = 5
    n_rounds: int = 10
    dirichlet_alpha: float = 0.5     # non-IID skew (lower = more skewed)
    train_config: TrainConfig = field(
        default_factory=lambda: TrainConfig(epochs=2, max_batches=40, lr=0.03, momentum=0.9)
    )
    # Fraction of clients participating in each round (1.0 = all)
    participation_rate: float = 1.0
    # Blockchain
    n_ledger_nodes: int = 3
    ledger_quorum: int = 2
    # Verification
    max_update_norm: Optional[float] = None  # None = no norm clipping
    # Reproducibility
    seed: int = 42
    n_classes: int = 10


@dataclass
class RoundRecord:
    """Metrics for one FL round."""
    round_id: int
    n_submitted: int
    n_accepted: int
    n_rejected: int
    test_accuracy: float
    test_loss: float
    block_hashes: List[str] = field(default_factory=list)
    accepted_clients: List[str] = field(default_factory=list)
    rejected_clients: List[str] = field(default_factory=list)
    wall_clock_s: float = 0.0


@dataclass
class DemoResult:
    """Full result of the demonstration run."""
    config: DemoConfig
    rounds: List[RoundRecord] = field(default_factory=list)
    final_accuracy: float = 0.0
    final_loss: float = 0.0
    final_model_params: Optional[np.ndarray] = None
    blockchain_blocks: int = 0
    chain_integrity_ok: bool = True
    tampering_demo_results: List[Dict[str, Any]] = field(default_factory=list)
    wall_clock_s: float = 0.0


def _global_model_commitment(params: np.ndarray) -> str:
    """SHA-256 hex commitment to model parameters."""
    return hashlib.sha256(params.astype(np.float32).tobytes()).hexdigest()


def _select_participants(
    clients: List[FLClient],
    participation_rate: float,
    rng: np.random.Generator,
) -> List[FLClient]:
    """Select which clients participate in this round."""
    n = max(2, int(len(clients) * participation_rate))
    indices = rng.choice(len(clients), size=n, replace=False)
    return [clients[i] for i in sorted(indices)]


def run_demo(
    dataset: FashionMNIST,
    config: Optional[DemoConfig] = None,
    output_dir: Optional[Path] = None,
    verbose: bool = True,
) -> DemoResult:
    """Run the full end-to-end decentralized FL demonstration.

    Args:
        dataset: pre-loaded Fashion-MNIST (call load_fashion_mnist() first).
        config: demonstration configuration.
        output_dir: where to save blockchain and results (None = no saving).
        verbose: print progress to stdout.

    Returns:
        DemoResult with per-round metrics, final model, and blockchain summary.
    """
    cfg = config or DemoConfig()
    rng = np.random.default_rng(cfg.seed)
    t_start = time.time()

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    # ------------------------------------------------------------------
    # 1. Create clients with non-IID data partitions
    # ------------------------------------------------------------------
    log(f"\n{'='*60}")
    log(f"  BC-FL-SRV Decentralized FL Demo")
    log(f"  {cfg.n_clients} clients | {cfg.n_rounds} rounds | α={cfg.dirichlet_alpha}")
    log(f"{'='*60}")

    client_ids = [f"client-{i:02d}" for i in range(cfg.n_clients)]
    shards = dirichlet_partition(
        dataset.y_train,
        client_ids,
        alpha=cfg.dirichlet_alpha,
        seed=cfg.seed,
    )
    shard_map = {s.client_id: s for s in shards}

    clients: List[FLClient] = []
    registry: Dict[str, bytes] = {}

    for cid, shard in zip(client_ids, shards):
        # Deterministic seed from client string
        seed_bytes = hashlib.sha256(f"BC-FL-SRV/demo/client/{cid}".encode()).digest()
        client = FLClient(
            seed_bytes=seed_bytes,
            shard=shard,
            train_config=cfg.train_config,
            n_classes=cfg.n_classes,
        )
        clients.append(client)
        registry[client.client_id] = client.public_key

    log(f"\n[SETUP] {cfg.n_clients} clients created with non-IID data (α={cfg.dirichlet_alpha})")
    log(f"  Shard sizes: {[len(s) for s in shards]}")
    log(f"  Registry contains {len(registry)} public keys")

    # ------------------------------------------------------------------
    # 2. Initialise blockchain
    # ------------------------------------------------------------------
    ledger = DistributedLedger(
        n_nodes=cfg.n_ledger_nodes,
        quorum_size=cfg.ledger_quorum,
    )
    log(f"\n[BLOCKCHAIN] Initialised: {cfg.n_ledger_nodes} nodes, quorum={cfg.ledger_quorum}")

    # ------------------------------------------------------------------
    # 3. Initialise global model
    # ------------------------------------------------------------------
    init_model = SmallCNN(cfg.n_classes)
    # Deterministic initialisation
    import torch
    torch.manual_seed(cfg.seed)
    init_model = SmallCNN(cfg.n_classes)
    global_params = get_flat_params(init_model)

    init_metrics = evaluate(global_params, dataset.x_test, dataset.y_test, cfg.n_classes)
    log(f"\n[INIT] Global model: {global_params.size} parameters")
    log(f"  Initial test accuracy: {init_metrics['accuracy']:.4f}")
    log(f"  Initial test loss:     {init_metrics['loss']:.4f}")

    # ------------------------------------------------------------------
    # 4. FL rounds
    # ------------------------------------------------------------------
    result = DemoResult(config=cfg)
    verifier = UpdateVerifier(
        registry=registry,
        max_update_norm=cfg.max_update_norm,
    )

    for fl_round in range(cfg.n_rounds):
        round_start = time.time()
        log(f"\n{'─'*50}")
        log(f"  FL ROUND {fl_round + 1}/{cfg.n_rounds}")
        log(f"{'─'*50}")

        round_blocks: List[str] = []

        # ── 4a. ROUND_START block ──────────────────────────────────────
        participants = _select_participants(clients, cfg.participation_rate, rng)
        participant_ids = [c.client_id for c in participants]
        model_commit = _global_model_commitment(global_params)

        start_block, _ = ledger.propose_block(
            fl_round=fl_round,
            event_type=BlockEvent.ROUND_START,
            participating_clients=participant_ids,
            extra={
                "model_commitment": model_commit,
                "n_clients_total": cfg.n_clients,
            },
        )
        if start_block:
            round_blocks.append(start_block.block_hash)
            log(f"  [BLOCK] ROUND_START #{start_block.index} → {start_block.short_hash()}...")

        # ── 4b. Distribute global model & collect updates ──────────────
        log(f"  [TRAIN] Distributing global model to {len(participants)} clients...")
        raw_updates: List[ClientUpdate] = []
        for client in participants:
            client.receive_global_model(global_params)
            cu = client.train_and_submit(fl_round=fl_round, dataset=dataset)
            raw_updates.append(cu)

        # ── 4c. Verification ───────────────────────────────────────────
        verifier.expected_round = fl_round
        v_results: List[VerificationResult] = verifier.verify_batch(raw_updates)

        accepted_updates: List[ClientUpdate] = []
        update_commitments: Dict[str, str] = {}
        verification_ledger: Dict[str, str] = {}
        accepted_clients: List[str] = []
        rejected_clients: List[str] = []

        for cu, vr in zip(raw_updates, v_results):
            update_commitments[cu.client_id] = cu.commitment_hex()
            verification_ledger[cu.client_id] = vr.to_ledger_value()
            if vr.accepted:
                accepted_updates.append(cu)
                accepted_clients.append(cu.client_id)
            else:
                rejected_clients.append(cu.client_id)
                log(f"  [VERIFY] REJECTED {cu.client_id[:12]}...: {vr.detail}")

        n_accepted = len(accepted_updates)
        n_rejected = len(rejected_clients)
        log(f"  [VERIFY] {n_accepted}/{len(participants)} updates accepted")

        # ── 4d. UPDATE_SUBMIT block ────────────────────────────────────
        submit_block, _ = ledger.propose_block(
            fl_round=fl_round,
            event_type=BlockEvent.UPDATE_SUBMIT,
            participating_clients=participant_ids,
            update_commitments=update_commitments,
            verification_results=verification_ledger,
            accepted_count=n_accepted,
            rejected_count=n_rejected,
        )
        if submit_block:
            round_blocks.append(submit_block.block_hash)
            log(f"  [BLOCK] UPDATE_SUBMIT #{submit_block.index} → {submit_block.short_hash()}...")

        # ── 4e. Aggregation ────────────────────────────────────────────
        if n_accepted == 0:
            log("  [WARN] No accepted updates; skipping aggregation this round")
            round_rec = RoundRecord(
                round_id=fl_round,
                n_submitted=len(participants),
                n_accepted=0,
                n_rejected=n_rejected,
                test_accuracy=init_metrics["accuracy"] if fl_round == 0 else result.rounds[-1].test_accuracy,
                test_loss=init_metrics["loss"] if fl_round == 0 else result.rounds[-1].test_loss,
                block_hashes=round_blocks,
                accepted_clients=[],
                rejected_clients=rejected_clients,
                wall_clock_s=time.time() - round_start,
            )
            result.rounds.append(round_rec)
            continue

        # Weighted FedAvg
        updates_arr = [cu.update for cu in accepted_updates]
        weights = [float(cu.n_samples) for cu in accepted_updates]
        aggregate_delta = fedavg(updates_arr, weights)
        global_params = (global_params + aggregate_delta).astype(np.float32)

        # Evaluate new global model
        metrics = evaluate(global_params, dataset.x_test, dataset.y_test, cfg.n_classes)
        new_commit = _global_model_commitment(global_params)

        log(f"  [AGGREG] FedAvg of {n_accepted} updates complete")
        log(f"  [EVAL]   Test accuracy: {metrics['accuracy']:.4f}  loss: {metrics['loss']:.4f}")

        # ── 4f. AGGREGATION block ──────────────────────────────────────
        agg_block, _ = ledger.propose_block(
            fl_round=fl_round,
            event_type=BlockEvent.AGGREGATION,
            participating_clients=accepted_clients,
            aggregation_commitment=new_commit,
            global_model_accuracy=metrics["accuracy"],
            global_model_loss=metrics["loss"],
            accepted_count=n_accepted,
            rejected_count=n_rejected,
        )
        if agg_block:
            round_blocks.append(agg_block.block_hash)
            log(f"  [BLOCK] AGGREGATION #{agg_block.index} → {agg_block.short_hash()}...")

        # ── 4g. ROUND_END block ────────────────────────────────────────
        end_block, _ = ledger.propose_block(
            fl_round=fl_round,
            event_type=BlockEvent.ROUND_END,
            extra={"final_accuracy": metrics["accuracy"], "final_loss": metrics["loss"]},
        )
        if end_block:
            round_blocks.append(end_block.block_hash)

        round_rec = RoundRecord(
            round_id=fl_round,
            n_submitted=len(participants),
            n_accepted=n_accepted,
            n_rejected=n_rejected,
            test_accuracy=metrics["accuracy"],
            test_loss=metrics["loss"],
            block_hashes=round_blocks,
            accepted_clients=accepted_clients,
            rejected_clients=rejected_clients,
            wall_clock_s=time.time() - round_start,
        )
        result.rounds.append(round_rec)

    # ------------------------------------------------------------------
    # 5. Final model evaluation
    # ------------------------------------------------------------------
    final_metrics = evaluate(global_params, dataset.x_test, dataset.y_test, cfg.n_classes)
    result.final_accuracy = final_metrics["accuracy"]
    result.final_loss = final_metrics["loss"]
    result.final_model_params = global_params.copy()
    result.blockchain_blocks = ledger.height

    # ------------------------------------------------------------------
    # 6. Blockchain integrity verification
    # ------------------------------------------------------------------
    integrity = ledger.verify_all_nodes()
    result.chain_integrity_ok = all(ok for ok, _ in integrity.values())
    chains_consistent = ledger.chains_are_consistent()

    log(f"\n{'='*60}")
    log(f"  TRAINING COMPLETE")
    log(f"{'='*60}")
    log(f"  Final test accuracy: {result.final_accuracy:.4f}")
    log(f"  Final test loss:     {result.final_loss:.4f}")
    log(f"  Blockchain height:   {ledger.height} blocks")
    log(f"  Chain integrity:     {'OK' if result.chain_integrity_ok else 'BROKEN'}")
    log(f"  All nodes consistent: {chains_consistent}")

    # ------------------------------------------------------------------
    # 7. Tampering demonstration
    # ------------------------------------------------------------------
    log(f"\n{'='*60}")
    log(f"  TAMPERING DEMONSTRATION")
    log(f"{'='*60}")

    # Use client 0 to generate a real update for tampering tests
    demo_client = clients[0]
    demo_client.receive_global_model(global_params)
    real_update = demo_client.train_and_submit(fl_round=cfg.n_rounds, dataset=dataset)
    verifier.expected_round = cfg.n_rounds

    tampering_tests = [
        ("valid_update", real_update, "Should be ACCEPTED"),
        ("tampered_bytes", TamperingDemo.tamper_update_bytes(real_update), "Should be REJECTED (commitment mismatch)"),
        ("forged_commitment", TamperingDemo.forge_commitment(real_update), "Should be REJECTED (signature invalid)"),
        ("unknown_identity", TamperingDemo.spoof_identity(real_update), "Should be REJECTED (unknown client)"),
    ]

    for name, update, expectation in tampering_tests:
        vr = verifier.verify(update)
        log(f"  [{name}] {vr.status.value} — {expectation}")
        result.tampering_demo_results.append({
            "name": name,
            "expected": expectation,
            "status": vr.status.value,
            "detail": vr.detail,
            "passed": (name == "valid_update") == vr.accepted,
        })

    # ------------------------------------------------------------------
    # 8. Save outputs
    # ------------------------------------------------------------------
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Blockchain
        ledger.save(output_dir / "blockchain.jsonl")
        log(f"\n[SAVE] Blockchain → {output_dir / 'blockchain.jsonl'}")

        # Final model
        np.save(str(output_dir / "final_model.npy"), global_params)
        log(f"[SAVE] Final model → {output_dir / 'final_model.npy'}")

        # Per-round metrics JSON
        rounds_data = []
        for r in result.rounds:
            rounds_data.append({
                "round": r.round_id,
                "n_submitted": r.n_submitted,
                "n_accepted": r.n_accepted,
                "n_rejected": r.n_rejected,
                "test_accuracy": r.test_accuracy,
                "test_loss": r.test_loss,
                "wall_clock_s": r.wall_clock_s,
                "block_hashes": r.block_hashes,
            })
        with (output_dir / "rounds.json").open("w") as f:
            json.dump(rounds_data, f, indent=2)
        log(f"[SAVE] Round metrics → {output_dir / 'rounds.json'}")

        # Summary
        summary = {
            "n_clients": cfg.n_clients,
            "n_rounds": cfg.n_rounds,
            "dirichlet_alpha": cfg.dirichlet_alpha,
            "final_accuracy": result.final_accuracy,
            "final_loss": result.final_loss,
            "blockchain_blocks": result.blockchain_blocks,
            "chain_integrity_ok": result.chain_integrity_ok,
            "chains_consistent": chains_consistent,
            "tampering_demo": result.tampering_demo_results,
        }
        with (output_dir / "summary.json").open("w") as f:
            json.dump(summary, f, indent=2)
        log(f"[SAVE] Summary → {output_dir / 'summary.json'}")

    result.wall_clock_s = time.time() - t_start
    log(f"\n[DONE] Total wall time: {result.wall_clock_s:.1f}s")
    return result
