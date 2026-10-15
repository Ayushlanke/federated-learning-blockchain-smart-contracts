#!/usr/bin/env python3
"""
BC-FL-SRV Decentralized Federated Learning Demonstration
=========================================================

Single-command end-to-end demo:

    python scripts/run_demo.py

What this runs
--------------
1.  Load Fashion-MNIST (auto-downloads if not cached in data/raw/).
2.  Create N FL clients with unique Ed25519 identities and non-IID data shards.
3.  Initialise a distributed blockchain ledger (3 nodes, quorum=2).
4.  Run M FL rounds:
      a. ROUND_START recorded on blockchain.
      b. Global model distributed to clients.
      c. Clients train locally and submit signed updates.
      d. Updates verified (signature + commitment + optional norm check).
      e. UPDATE_SUBMIT block recorded with commitments and verification results.
      f. Accepted updates aggregated via FedAvg.
      g. AGGREGATION block recorded (global model commitment + accuracy).
      h. ROUND_END block recorded.
5.  Final model evaluated on test set.
6.  Blockchain integrity verified across all nodes.
7.  Tampering demonstration (3 attacks, all caught).
8.  Results saved to results/demo_decentralized_fl/.
9.  Dashboard and graphs generated.

Results are written to:
    results/demo_decentralized_fl/
      blockchain.jsonl        -- complete blockchain (JSONL)
      final_model.npy         -- final model parameters
      rounds.json             -- per-round metrics
      summary.json            -- high-level summary
      figures/
        dashboard.png         -- combined dashboard
        accuracy_vs_round.png
        loss_vs_round.png
        participation.png
        blockchain_timeline.png

The existing E1-E5, G2, G3 results in results/ are NOT touched.
"""

import argparse
import json
import sys
from pathlib import Path

# ── make sure the project src is on the path ──────────────────────────────────
_root = Path(__file__).resolve().parents[1]
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))

from bcflsrv.fl.data import load_fashion_mnist
from bcflsrv.fl.model import TrainConfig
from bcflsrv.demo.pipeline import DemoConfig, run_demo
from bcflsrv.demo.blockchain import DistributedLedger
from bcflsrv.demo.visualize import generate_all_figures, generate_dashboard


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BC-FL-SRV Decentralized FL Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--clients", type=int, default=5,
                   help="Number of FL clients")
    p.add_argument("--rounds", type=int, default=10,
                   help="Number of FL rounds")
    p.add_argument("--alpha", type=float, default=0.5,
                   help="Dirichlet concentration for non-IID partition (lower = more skewed)")
    p.add_argument("--epochs", type=int, default=2,
                   help="Local training epochs per round")
    p.add_argument("--max-batches", type=int, default=40,
                   help="Max training batches per client per round (for speed)")
    p.add_argument("--lr", type=float, default=0.03,
                   help="Local SGD learning rate")
    p.add_argument("--nodes", type=int, default=3,
                   help="Number of blockchain ledger nodes")
    p.add_argument("--quorum", type=int, default=2,
                   help="Quorum size for block acceptance")
    p.add_argument("--seed", type=int, default=42,
                   help="Master random seed for reproducibility")
    p.add_argument("--output-dir", type=Path,
                   default=_root / "results" / "demo_decentralized_fl",
                   help="Output directory (existing research results are not touched)")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress progress output")
    p.add_argument("--no-figures", action="store_true",
                   help="Skip figure generation (faster)")
    return p.parse_args()


def print_blockchain_summary(ledger_path: Path) -> None:
    """Print a human-readable summary of the saved blockchain."""
    blocks = DistributedLedger.load_chain(ledger_path)
    print(f"\n{'═'*60}")
    print(f"  BLOCKCHAIN SUMMARY ({len(blocks)} blocks)")
    print(f"{'═'*60}")
    print(f"  {'Index':>5}  {'Event':20}  {'FL Rd':>5}  {'Hash':16}  {'Acc/Rej':>8}")
    print(f"  {'─'*5}  {'─'*20}  {'─'*5}  {'─'*16}  {'─'*8}")
    for blk in blocks:
        acc_rej = (
            f"{blk.accepted_count}/{blk.rejected_count}"
            if blk.event_type.value in ("UPDATE_SUBMIT", "AGGREGATION")
            else "–"
        )
        acc_str = (
            f"  acc={blk.global_model_accuracy:.4f}"
            if blk.global_model_accuracy >= 0
            else ""
        )
        print(
            f"  {blk.index:>5}  {blk.event_type.value:20}  {blk.fl_round:>5}  "
            f"{blk.short_hash():<16}  {acc_rej:>8}{acc_str}"
        )


def main() -> int:
    args = parse_args()

    # Safety check: never write into the existing results subdirectories
    protected = [
        "runs", "figures", "summary",
    ]
    out = args.output_dir.resolve()
    results_root = (_root / "results").resolve()
    if out == results_root or any(out == results_root / p for p in protected):
        print(
            f"[ERROR] Output dir '{out}' would overwrite existing research results. "
            "Use a different --output-dir.", file=sys.stderr
        )
        return 1

    print(f"\nBC-FL-SRV Decentralized FL Demo")
    print(f"Output: {args.output_dir}")

    # ── Load dataset ──────────────────────────────────────────────────
    print("\n[DATA] Loading Fashion-MNIST (downloading if needed)...")
    dataset = load_fashion_mnist()
    print(f"[DATA] Train: {len(dataset.x_train)}, Test: {len(dataset.x_test)} samples")

    # ── Build config ──────────────────────────────────────────────────
    cfg = DemoConfig(
        n_clients=args.clients,
        n_rounds=args.rounds,
        dirichlet_alpha=args.alpha,
        train_config=TrainConfig(
            epochs=args.epochs,
            max_batches=args.max_batches,
            lr=args.lr,
        ),
        n_ledger_nodes=args.nodes,
        ledger_quorum=args.quorum,
        seed=args.seed,
    )

    # ── Run demo ──────────────────────────────────────────────────────
    result = run_demo(
        dataset=dataset,
        config=cfg,
        output_dir=args.output_dir,
        verbose=not args.quiet,
    )

    # ── Print blockchain summary ───────────────────────────────────────
    bc_path = args.output_dir / "blockchain.jsonl"
    if bc_path.exists():
        print_blockchain_summary(bc_path)

    # ── Figures ───────────────────────────────────────────────────────
    if not args.no_figures:
        print("\n[FIGURES] Generating visualizations...")
        fig_dir = args.output_dir / "figures"
        from bcflsrv.demo.blockchain import DistributedLedger
        blocks = DistributedLedger.load_chain(bc_path)

        generate_all_figures(result, blocks, fig_dir)
        dashboard_path = generate_dashboard(result, blocks, fig_dir)
        print(f"[FIGURES] Dashboard saved to: {dashboard_path}")

    # ── Final summary ─────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  DEMO COMPLETE")
    print(f"{'═'*60}")
    print(f"  Final test accuracy:  {result.final_accuracy:.4f}")
    print(f"  Final test loss:      {result.final_loss:.4f}")
    print(f"  Blockchain blocks:    {result.blockchain_blocks}")
    print(f"  Chain integrity:      {'OK ✓' if result.chain_integrity_ok else 'BROKEN ✗'}")

    print(f"\n  Tampering Demo Results:")
    all_correct = True
    for t in result.tampering_demo_results:
        icon = "✓" if t["passed"] else "✗"
        print(f"    {icon} {t['name']:25s} → {t['status']}")
        if not t["passed"]:
            all_correct = False

    if not all_correct:
        print("\n  [WARN] Some tampering tests had unexpected outcomes!")
        return 2

    print(f"\n  Wall time: {result.wall_clock_s:.1f}s")
    print(f"\n  Output: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
