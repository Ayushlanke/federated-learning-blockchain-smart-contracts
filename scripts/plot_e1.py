"""Generate E-1 figures from the summary CSVs.

Reads only ``results/summary/*.csv`` -- never in-memory state -- so figures are
regenerable from committed data alone, as required by the reproducibility contract
(EVALUATION_PLAN.md section 6).

Usage:
    .venv/Scripts/python.exe scripts/plot_e1.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display on this machine
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMARY = REPO_ROOT / "results" / "summary"
FIGURES = REPO_ROOT / "results" / "figures"

INK = "#1a1a1a"
AUDITOR = "#0b6e4f"
CLIENT = "#c1121f"
WRITER = "#e08c00"
BASELINE = "#6a4c93"


def load(name: str) -> list[dict]:
    with (SUMMARY / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def style(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, which="both", alpha=0.18, linewidth=0.6)
    ax.set_axisbelow(True)


def bytes_fmt(value, _pos=None) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f}{unit}" if value >= 1 else f"{value:g}{unit}"
        value /= 1024
    return str(value)


def fig_payload_independence() -> Path:
    """The headline figure: auditor cost is flat in N, client cost is not."""
    rows = load("e1a_payload_size.csv")
    n = [int(r["payload_bytes"]) for r in rows]
    auditor = [float(r["auditor_inclusion_us"]) for r in rows]
    consistency = [float(r["auditor_consistency_us"]) for r in rows]
    client = [float(r["client_end_to_end_us"]) for r in rows]
    writer = [float(r["writer_append_us"]) for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.loglog(n, auditor, "o-", color=AUDITOR, lw=2, ms=6, label="Auditor: inclusion check")
    ax.loglog(n, consistency, "s--", color=AUDITOR, lw=1.6, ms=5, alpha=0.75,
              label="Auditor: consistency check (AG3)")
    ax.loglog(n, client, "^-", color=CLIENT, lw=2, ms=6, label="Client: end-to-end (hashes own update)")
    ax.loglog(n, writer, "v:", color=WRITER, lw=1.6, ms=5, alpha=0.85, label="Writer: append")

    growth = n[-1] / n[0]
    aud_growth = auditor[-1] / auditor[0]
    cli_growth = client[-1] / client[0]

    # Labels sit in clear space; no arrows crossing the data.
    ax.text(n[2], auditor[0] * 2.4,
            f"auditor: {growth:,.0f}x payload  ->  {aud_growth:.2f}x time  (flat)",
            color=AUDITOR, fontsize=9.5, ha="center", va="bottom", fontweight="bold")
    ax.text(n[-1], client[-1] * 1.7,
            f"client / writer: {cli_growth:,.0f}x  (linear in N)",
            color=CLIENT, fontsize=9.5, ha="right", va="bottom")

    ax.set_xlabel("Model update size N (log scale)")
    ax.set_ylabel("Time per verification (microseconds, log scale)")
    ax.set_title("E-1a: Auditor verification cost is independent of model size\n"
                 "(transcript held fixed at 1024 entries)", fontsize=11, color=INK)
    ax.set_xticks(n)
    ax.set_xticklabels([bytes_fmt(v) for v in n])
    ax.minorticks_off()
    ax.set_ylim(top=client[-1] * 6)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    style(ax)
    fig.tight_layout()

    out = FIGURES / "e1a_payload_independence.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def fig_transcript_scaling() -> Path:
    """O(log T) verification against an O(T) signed-log baseline."""
    rows = load("e1b_transcript_size.csv")
    t = [int(r["transcript_entries"]) for r in rows]
    incl = [float(r["auditor_inclusion_us"]) for r in rows]
    cons = [float(r["auditor_consistency_us"]) for r in rows]

    b1_t = [int(r["transcript_entries"]) for r in rows if r["baseline_b1_inclusion_us"]]
    b1 = [float(r["baseline_b1_inclusion_us"]) for r in rows if r["baseline_b1_inclusion_us"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.loglog(t, incl, "o-", color=AUDITOR, lw=2, ms=6, label="BC-FL-SRV: inclusion check  O(log T)")
    ax.loglog(t, cons, "s--", color=AUDITOR, lw=1.6, ms=5, alpha=0.75,
              label="BC-FL-SRV: consistency check (AG3)")
    ax.loglog(b1_t, b1, "D-", color=BASELINE, lw=2, ms=6,
              label="Baseline B1: signed log, no tree  O(T)")

    ratio = b1[-1] / incl[t.index(b1_t[-1])]
    # Sit in the empty band between the two curves, clear of the legend.
    ax.text(t[2], (incl[-1] * b1[-1]) ** 0.5,
            f"baseline is {ratio:,.0f}x slower at T={b1_t[-1]:,}\nand the gap widens with T",
            color=BASELINE, fontsize=9.5, ha="center", va="center")

    ax.set_xticks(t)
    ax.set_xticklabels([f"{v:,}" for v in t], fontsize=8.5)
    ax.minorticks_off()
    ax.set_xlabel("Transcript size T (entries, log scale)")
    ax.set_ylabel("Time per verification (microseconds, log scale)")
    ax.set_title("E-1b: Verification scales logarithmically; the signed-log baseline scales linearly\n"
                 "(update size held fixed at 1 KiB)", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    style(ax)
    fig.tight_layout()

    out = FIGURES / "e1b_transcript_scaling.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def fig_proof_size() -> Path:
    """Proof size: what an auditor must actually download."""
    rows = load("e1b_transcript_size.csv")
    t = [int(r["transcript_entries"]) for r in rows]
    proof_bytes = [int(r["proof_bytes"]) for r in rows]
    b1_t = [int(r["transcript_entries"]) for r in rows if r["baseline_b1_bytes_transferred"]]
    b1_bytes = [int(r["baseline_b1_bytes_transferred"]) for r in rows
                if r["baseline_b1_bytes_transferred"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.loglog(t, proof_bytes, "o-", color=AUDITOR, lw=2, ms=6,
              label="BC-FL-SRV: Merkle audit path")
    ax.loglog(b1_t, b1_bytes, "D-", color=BASELINE, lw=2, ms=6,
              label="Baseline B1: entire log must be transferred")

    ax.set_xticks(t)
    ax.set_xticklabels([f"{v:,}" for v in t], fontsize=8.5)
    ax.minorticks_off()
    ax.set_xlabel("Transcript size T (entries, log scale)")
    ax.set_ylabel("Bytes an auditor must receive (log scale)")
    ax.set_title("E-1b: Proof size — 512 bytes vs the whole log\n"
                 "(update size held fixed at 1 KiB)", fontsize=11, color=INK)
    ax.yaxis.set_major_formatter(FuncFormatter(bytes_fmt))
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    style(ax)
    fig.tight_layout()

    out = FIGURES / "e1b_proof_size.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main() -> int:
    if not SUMMARY.exists():
        print("No summary CSVs. Run scripts/exp_e1_verification_cost.py first.", file=sys.stderr)
        return 1
    FIGURES.mkdir(parents=True, exist_ok=True)
    for fn in (fig_payload_independence, fig_transcript_scaling, fig_proof_size):
        print(f"wrote {fn().relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
