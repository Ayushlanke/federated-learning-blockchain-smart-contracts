"""Matplotlib-based visualization of the decentralized FL demonstration results.

Generates:
  1. accuracy_vs_round.png  -- test accuracy over FL rounds
  2. loss_vs_round.png      -- test loss over FL rounds
  3. participation.png      -- accepted vs rejected updates per round
  4. blockchain_timeline.png -- blockchain blocks coloured by event type
  5. fl_flow_diagram.png    -- ASCII-art-style architecture diagram
  6. dashboard.png          -- combined 2x3 dashboard figure

All figures saved to the specified output directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")  # headless / no display required
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np

from bcflsrv.demo.blockchain import Block, BlockEvent, DistributedLedger
from bcflsrv.demo.pipeline import DemoResult, RoundRecord

__all__ = ["generate_all_figures", "generate_dashboard"]

_EVENT_COLORS = {
    BlockEvent.ROUND_START:         "#4A90D9",
    BlockEvent.UPDATE_SUBMIT:       "#7ED321",
    BlockEvent.AGGREGATION:        "#F5A623",
    BlockEvent.ROUND_END:           "#9B59B6",
    BlockEvent.TAMPERING_DETECTED:  "#E74C3C",
}

_EVENT_LABELS = {
    BlockEvent.ROUND_START:     "Round Start",
    BlockEvent.UPDATE_SUBMIT:   "Update Submit",
    BlockEvent.AGGREGATION:    "Aggregation",
    BlockEvent.ROUND_END:       "Round End",
    BlockEvent.TAMPERING_DETECTED: "Tampering",
}


def _setup_style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "#F8F9FA",
        "axes.facecolor": "#FFFFFF",
        "axes.grid": True,
        "grid.alpha": 0.4,
        "lines.linewidth": 2,
    })


def plot_accuracy(
    rounds: List[RoundRecord],
    ax: plt.Axes,
    initial_accuracy: float = 0.0,
) -> None:
    rounds_with_acc = [r for r in rounds if r.n_accepted > 0]
    if not rounds_with_acc:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return

    xs = [r.round_id + 1 for r in rounds_with_acc]
    ys = [r.test_accuracy for r in rounds_with_acc]

    ax.plot(xs, ys, marker="o", color="#2196F3", linewidth=2.5, markersize=6, label="Test accuracy")
    if initial_accuracy > 0:
        ax.axhline(initial_accuracy, linestyle="--", color="#9E9E9E", alpha=0.6, label="Random baseline")

    best_round = xs[np.argmax(ys)]
    best_acc   = max(ys)
    ax.annotate(
        f"Best: {best_acc:.3f}",
        xy=(best_round, best_acc),
        xytext=(best_round + 0.5, best_acc - 0.02),
        arrowprops=dict(arrowstyle="->", color="grey"),
        fontsize=9,
    )

    ax.set_xlabel("FL Round")
    ax.set_ylabel("Test Accuracy")
    ax.set_title("Accuracy vs FL Round")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)


def plot_loss(rounds: List[RoundRecord], ax: plt.Axes) -> None:
    rounds_with_data = [r for r in rounds if r.n_accepted > 0]
    if not rounds_with_data:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return

    xs = [r.round_id + 1 for r in rounds_with_data]
    ys = [r.test_loss for r in rounds_with_data]

    ax.plot(xs, ys, marker="s", color="#E91E63", linewidth=2.5, markersize=6)
    ax.set_xlabel("FL Round")
    ax.set_ylabel("Test Loss")
    ax.set_title("Loss vs FL Round")
    ax.set_ylim(bottom=0)


def plot_participation(rounds: List[RoundRecord], ax: plt.Axes) -> None:
    xs = [r.round_id + 1 for r in rounds]
    accepted = [r.n_accepted for r in rounds]
    rejected = [r.n_rejected for r in rounds]

    bar_w = 0.6
    bars_a = ax.bar(xs, accepted, bar_w, label="Accepted", color="#4CAF50", alpha=0.85)
    bars_r = ax.bar(xs, rejected, bar_w, bottom=accepted, label="Rejected", color="#F44336", alpha=0.85)

    ax.set_xlabel("FL Round")
    ax.set_ylabel("Client Updates")
    ax.set_title("Updates per Round")
    ax.legend(fontsize=8)
    ax.set_xticks(xs)


def plot_blockchain(blocks: List[Block], ax: plt.Axes) -> None:
    """Plot blockchain blocks as a coloured timeline."""
    if not blocks:
        ax.text(0.5, 0.5, "No blocks", ha="center", va="center", transform=ax.transAxes)
        return

    # Group by FL round
    rounds_seen = sorted({b.fl_round for b in blocks})
    event_types = list(BlockEvent)

    # Scatter: x = block index, y = fl_round, colour = event_type
    xs, ys, colors, sizes = [], [], [], []
    for blk in blocks:
        xs.append(blk.index)
        ys.append(blk.fl_round + 1)
        colors.append(_EVENT_COLORS.get(blk.event_type, "#999999"))
        sizes.append(80)

    ax.scatter(xs, ys, c=colors, s=sizes, zorder=3, edgecolors="white", linewidths=0.5)

    # Draw chain links
    for i in range(1, len(blocks)):
        ax.plot(
            [blocks[i - 1].index, blocks[i].index],
            [blocks[i - 1].fl_round + 1, blocks[i].fl_round + 1],
            color="#CCCCCC", linewidth=0.8, zorder=2,
        )

    # Legend
    handles = [
        mpatches.Patch(color=_EVENT_COLORS[e], label=_EVENT_LABELS[e])
        for e in BlockEvent
        if any(b.event_type == e for b in blocks)
    ]
    ax.legend(handles=handles, fontsize=7, loc="lower right")
    ax.set_xlabel("Block Index")
    ax.set_ylabel("FL Round")
    ax.set_title(f"Blockchain Timeline ({len(blocks)} blocks)")
    ax.set_yticks(range(1, max(ys) + 2))


def plot_fl_flow(ax: plt.Axes, n_clients: int = 5) -> None:
    """Draw the FL architecture flow diagram."""
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("BC-FL-SRV Architecture", fontsize=12, fontweight="bold")

    # Clients
    client_y_positions = np.linspace(2, 8, n_clients)
    for i, cy in enumerate(client_y_positions):
        rect = mpatches.FancyBboxPatch(
            (0.2, cy - 0.35), 1.6, 0.7,
            boxstyle="round,pad=0.1",
            facecolor="#E3F2FD", edgecolor="#1565C0", linewidth=1.5,
        )
        ax.add_patch(rect)
        ax.text(1.0, cy, f"Client {i+1}", ha="center", va="center", fontsize=8, fontweight="bold")
        # Arrow to blockchain
        ax.annotate("", xy=(4.0, 5.0), xytext=(1.8, cy),
                    arrowprops=dict(arrowstyle="->", color="#42A5F5", lw=1.0))

    # Blockchain box
    bc_rect = mpatches.FancyBboxPatch(
        (3.7, 4.3), 2.6, 1.4,
        boxstyle="round,pad=0.1",
        facecolor="#FFF3E0", edgecolor="#E65100", linewidth=2,
    )
    ax.add_patch(bc_rect)
    ax.text(5.0, 5.0, "Blockchain\nLedger", ha="center", va="center",
            fontsize=9, fontweight="bold", color="#E65100")

    # Verification
    ver_rect = mpatches.FancyBboxPatch(
        (3.7, 2.6), 2.6, 1.2,
        boxstyle="round,pad=0.1",
        facecolor="#E8F5E9", edgecolor="#2E7D32", linewidth=1.5,
    )
    ax.add_patch(ver_rect)
    ax.text(5.0, 3.2, "Verification\n(Sig + Commit)", ha="center", va="center",
            fontsize=8, color="#2E7D32")
    ax.annotate("", xy=(5.0, 4.3), xytext=(5.0, 3.8),
                arrowprops=dict(arrowstyle="->", color="#66BB6A", lw=1.5))

    # Aggregation
    agg_rect = mpatches.FancyBboxPatch(
        (3.7, 6.4), 2.6, 1.0,
        boxstyle="round,pad=0.1",
        facecolor="#F3E5F5", edgecolor="#6A1B9A", linewidth=1.5,
    )
    ax.add_patch(agg_rect)
    ax.text(5.0, 6.9, "Aggregation\n(FedAvg)", ha="center", va="center",
            fontsize=8, color="#6A1B9A")
    ax.annotate("", xy=(5.0, 6.4), xytext=(5.0, 5.7),
                arrowprops=dict(arrowstyle="->", color="#AB47BC", lw=1.5))

    # Global model
    gm_rect = mpatches.FancyBboxPatch(
        (3.7, 8.0), 2.6, 1.0,
        boxstyle="round,pad=0.1",
        facecolor="#FCE4EC", edgecolor="#880E4F", linewidth=2,
    )
    ax.add_patch(gm_rect)
    ax.text(5.0, 8.5, "Global Model", ha="center", va="center",
            fontsize=9, fontweight="bold", color="#880E4F")
    ax.annotate("", xy=(5.0, 8.0), xytext=(5.0, 7.4),
                arrowprops=dict(arrowstyle="->", color="#EC407A", lw=1.5))

    # Feedback loop: global model back to clients
    ax.annotate("", xy=(1.0, 8.0), xytext=(3.7, 8.5),
                arrowprops=dict(arrowstyle="->", color="#EC407A",
                                connectionstyle="arc3,rad=0.4", lw=1.2))
    ax.text(2.0, 9.2, "Next Round", ha="center", va="center",
            fontsize=8, color="#880E4F", style="italic")


def plot_tampering(tampering_results: list, ax: plt.Axes) -> None:
    """Bar chart of tampering test outcomes."""
    if not tampering_results:
        ax.text(0.5, 0.5, "No tampering tests", ha="center", va="center", transform=ax.transAxes)
        return

    names = [r["name"].replace("_", "\n") for r in tampering_results]
    statuses = [r["status"] for r in tampering_results]
    passed = [r["passed"] for r in tampering_results]

    colors = ["#4CAF50" if p else "#F44336" for p in passed]
    ax.barh(range(len(names)), [1] * len(names), color=colors, alpha=0.8)
    for i, (name, status) in enumerate(zip(names, statuses)):
        ax.text(0.5, i, f"{name}\n→ {status}", ha="center", va="center", fontsize=8)

    ax.set_xlim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_title("Tampering Detection Results")
    ax.set_xlabel("Green = correct outcome   Red = unexpected")


def generate_all_figures(result: DemoResult, blocks: List[Block], output_dir: Path) -> None:
    """Save individual figures."""
    _setup_style()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Accuracy
    fig, ax = plt.subplots(figsize=(8, 4))
    plot_accuracy(result.rounds, ax)
    fig.tight_layout()
    fig.savefig(output_dir / "accuracy_vs_round.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Loss
    fig, ax = plt.subplots(figsize=(8, 4))
    plot_loss(result.rounds, ax)
    fig.tight_layout()
    fig.savefig(output_dir / "loss_vs_round.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Participation
    fig, ax = plt.subplots(figsize=(8, 4))
    plot_participation(result.rounds, ax)
    fig.tight_layout()
    fig.savefig(output_dir / "participation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Blockchain timeline
    fig, ax = plt.subplots(figsize=(10, 5))
    plot_blockchain(blocks, ax)
    fig.tight_layout()
    fig.savefig(output_dir / "blockchain_timeline.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Combined dashboard
    generate_dashboard(result, blocks, output_dir)


def generate_dashboard(
    result: DemoResult,
    blocks: List[Block],
    output_dir: Path,
) -> Path:
    """Generate a combined 2x3 dashboard PNG."""
    _setup_style()
    output_dir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(18, 12), facecolor="#F0F4F8")
    fig.suptitle(
        f"BC-FL-SRV Decentralized Federated Learning — "
        f"{result.config.n_clients} clients · {result.config.n_rounds} rounds · "
        f"Final accuracy: {result.final_accuracy:.4f}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

    ax_acc   = fig.add_subplot(gs[0, 0])
    ax_loss  = fig.add_subplot(gs[0, 1])
    ax_part  = fig.add_subplot(gs[0, 2])
    ax_bc    = fig.add_subplot(gs[1, 0:2])
    ax_flow  = fig.add_subplot(gs[1, 2])

    plot_accuracy(result.rounds, ax_acc)
    plot_loss(result.rounds, ax_loss)
    plot_participation(result.rounds, ax_part)
    plot_blockchain(blocks, ax_bc)
    plot_fl_flow(ax_flow, n_clients=result.config.n_clients)

    # Tampering summary as text box in flow diagram area
    tamp = result.tampering_demo_results
    if tamp:
        lines = ["Tampering Demo:"]
        for t in tamp:
            icon = "✓" if t["passed"] else "✗"
            lines.append(f"  {icon} {t['name']}: {t['status']}")
        ax_flow.text(
            0.01, 0.01, "\n".join(lines),
            transform=ax_flow.transAxes,
            fontsize=7,
            va="bottom",
            ha="left",
            bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
        )

    out_path = output_dir / "dashboard.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path
