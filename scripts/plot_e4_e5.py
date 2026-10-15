"""Generate E-4/E-5 figures and summary tables from ``results/summary/e4e5_runs.csv``.

Reads committed data only, so figures regenerate without re-running the 87-minute
experiment.

Every aggregate is reported as **mean +/- std across seeds**. No single-run numbers.

Usage:
    .venv/Scripts/python.exe scripts/plot_e4_e5.py
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMARY = REPO_ROOT / "results" / "summary"
FIGURES = REPO_ROOT / "results" / "figures"

INK = "#1a1a1a"
TPR_C = "#0b6e4f"
FPR_C = "#c1121f"
LEVEL_COLOURS = ["#adb5bd", "#1d4e89", "#0b6e4f", "#e08c00", "#c1121f"]
SYSTEM_COLOURS = {"S0": "#adb5bd", "S1": "#1d4e89", "S2": "#0b6e4f"}
ATTACK_NAMES = {
    "A0": "no attack", "A1": "sign-flip", "A2": "label-flip",
    "A3": "scaled", "A4": "slow-drift",
}
LEVELS = ["E0", "E1", "E2", "E3", "E4"]


def load() -> List[dict]:
    with (SUMMARY / "e4e5_runs.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def stat(values: Sequence[float]) -> Tuple[float, float]:
    """Mean and (population) std, ignoring NaN."""
    clean = [v for v in values if not math.isnan(v)]
    if not clean:
        return float("nan"), 0.0
    mean = sum(clean) / len(clean)
    var = sum((v - mean) ** 2 for v in clean) / len(clean)
    return mean, math.sqrt(var)


def f(row: dict, key: str) -> float:
    raw = row.get(key, "")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float("nan")


def style(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="y", alpha=0.18, linewidth=0.6)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------------------
# E-4: does more disclosure buy more detection?
# ---------------------------------------------------------------------------

def fig_disclosure_ladder(rows: List[dict]) -> Path:
    attacks = ["A1", "A2", "A3"]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.4), sharey=True)

    for ax, attack in zip(axes, attacks):
        tpr_m, tpr_s, fpr_m, fpr_s = [], [], [], []
        for level in LEVELS:
            sel = [
                r for r in rows
                if r["system"] == "S1" and r["disclosure"] == level and r["attack"] == attack
            ]
            m, s = stat([f(r, "tpr") for r in sel]); tpr_m.append(m); tpr_s.append(s)
            m, s = stat([f(r, "fpr") for r in sel]); fpr_m.append(m); fpr_s.append(s)

        x = range(len(LEVELS))
        ax.errorbar(x, tpr_m, yerr=tpr_s, marker="o", color=TPR_C, lw=2, capsize=3,
                    label="TPR (malicious rejected)")
        ax.errorbar(x, fpr_m, yerr=fpr_s, marker="s", color=FPR_C, lw=2, capsize=3,
                    ls="--", label="FPR (honest rejected)")
        ax.set_xticks(list(x)); ax.set_xticklabels(LEVELS)
        ax.set_ylim(-0.05, 1.05)
        ax.set_title(ATTACK_NAMES[attack], fontsize=11, color=INK)
        ax.set_xlabel("Disclosure level")
        style(ax)

    axes[0].set_ylabel("Rate (mean +/- std over seeds)")
    axes[0].legend(frameon=False, fontsize=9, loc="center left")
    fig.suptitle("E-4: Detection power vs disclosure level  (S1, 20% malicious, Dirichlet 0.5)",
                 fontsize=12, color=INK)
    fig.tight_layout()
    out = FIGURES / "e4_disclosure_ladder.png"
    fig.savefig(out, dpi=160); plt.close(fig)
    return out


def fig_system_comparison(rows: List[dict]) -> Path:
    """S0 vs S1 vs S2 -- the S1 == S2 check made visual."""
    attacks = ["A0", "A1", "A2", "A3"]
    systems = ["S0", "S1", "S2"]
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    width = 0.26

    for i, system in enumerate(systems):
        means, stds = [], []
        for attack in attacks:
            sel = [
                r for r in rows
                if r["system"] == system and r["disclosure"] == "E2" and r["attack"] == attack
            ]
            m, s = stat([f(r, "final_accuracy") for r in sel])
            means.append(m); stds.append(s)
        xs = [j + (i - 1) * width for j in range(len(attacks))]
        ax.bar(xs, means, width, yerr=stds, capsize=3, color=SYSTEM_COLOURS[system],
               label={"S0": "S0 plain FedAvg", "S1": "S1 rule, trusted server",
                      "S2": "S2 full BC-FL-SRV"}[system])

    ax.set_xticks(range(len(attacks)))
    ax.set_xticklabels([ATTACK_NAMES[a] for a in attacks])
    ax.set_ylabel("Final test accuracy (mean +/- std)")
    ax.set_title("E-4.3: S1 and S2 are indistinguishable on ML metrics\n"
                 "the mechanism buys verifiability, not detection",
                 fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=9)
    style(ax)
    fig.tight_layout()
    out = FIGURES / "e4_system_comparison.png"
    fig.savefig(out, dpi=160); plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# E-5: the falsification curve
# ---------------------------------------------------------------------------

def fig_slow_drift(rows: List[dict]) -> Path:
    sel_all = [r for r in rows if r["attack"] == "A4" and r["system"] == "S1"
               and r["disclosure"] == "E2" and abs(f(r, "malicious_fraction") - 0.2) < 1e-9]
    betas = sorted({f(r, "beta") for r in sel_all})

    admitted_m, admitted_s, acc_m, acc_s = [], [], [], []
    for beta in betas:
        sel = [r for r in sel_all if abs(f(r, "beta") - beta) < 1e-9]
        m, s = stat([f(r, "malicious_admitted_fraction") for r in sel])
        admitted_m.append(m); admitted_s.append(s)
        m, s = stat([f(r, "final_accuracy") for r in sel])
        acc_m.append(m); acc_s.append(s)

    fig, ax = plt.subplots(figsize=(8.4, 5))
    ax.errorbar(betas, admitted_m, yerr=admitted_s, marker="o", color=FPR_C, lw=2.2,
                capsize=3, label="fraction of malicious updates ADMITTED")
    ax.axvline(1.0, color=INK, ls=":", lw=1.4, alpha=0.7)
    ax.text(1.02, 0.5, "rule threshold", rotation=90, fontsize=8.5, color=INK, alpha=0.75)
    ax.set_xlabel("beta  (attacker magnitude as a fraction of the rule's threshold)")
    ax.set_ylabel("Fraction admitted (mean +/- std)")
    ax.set_ylim(-0.05, 1.05)

    ax2 = ax.twinx()
    ax2.errorbar(betas, acc_m, yerr=acc_s, marker="^", color=TPR_C, lw=1.8, ls="--",
                 capsize=3, label="final accuracy")
    ax2.set_ylabel("Final test accuracy", color=TPR_C)
    ax2.tick_params(axis="y", labelcolor=TPR_C)
    ax2.spines["top"].set_visible(False)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, frameon=False, fontsize=9, loc="center left")

    ax.set_title("E-5.1: The slow-drift falsification curve\n"
                 "an attacker sitting inside the threshold (beta < 1) is admitted",
                 fontsize=11, color=INK)
    style(ax)
    fig.tight_layout()
    out = FIGURES / "e5_slow_drift_curve.png"
    fig.savefig(out, dpi=160); plt.close(fig)
    return out


def fig_slow_drift_by_level(rows: List[dict]) -> Path:
    """E5.3 -- can ANY disclosure level catch it?"""
    sel_all = [r for r in rows if r["attack"] == "A4" and r["system"] == "S1"
               and abs(f(r, "beta") - 0.9) < 1e-9]
    levels = [lvl for lvl in LEVELS if any(r["disclosure"] == lvl for r in sel_all)]

    tpr_m, tpr_s = [], []
    for level in levels:
        sel = [r for r in sel_all if r["disclosure"] == level]
        m, s = stat([f(r, "tpr") for r in sel])
        tpr_m.append(m); tpr_s.append(s)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.bar(range(len(levels)), tpr_m, yerr=tpr_s, capsize=4,
           color=[LEVEL_COLOURS[LEVELS.index(l)] for l in levels])
    ax.set_xticks(range(len(levels))); ax.set_xticklabels(levels)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Disclosure level")
    ax.set_ylabel("TPR against slow drift (mean +/- std)")
    ax.set_title("E-5.3: Detection of a slow-drift attacker at beta = 0.9\n"
                 "does more disclosure help against an attacker that stays inside the rule?",
                 fontsize=11, color=INK)
    style(ax)
    fig.tight_layout()
    out = FIGURES / "e5_slow_drift_by_level.png"
    fig.savefig(out, dpi=160); plt.close(fig)
    return out


def write_tables(rows: List[dict]) -> List[Path]:
    """Aggregated CSVs (mean +/- std) for the report."""
    written = []

    ladder = []
    for level in LEVELS:
        for attack in ["A0", "A1", "A2", "A3"]:
            sel = [r for r in rows if r["system"] == "S1"
                   and r["disclosure"] == level and r["attack"] == attack]
            if not sel:
                continue
            tpr, tpr_sd = stat([f(r, "tpr") for r in sel])
            fpr, fpr_sd = stat([f(r, "fpr") for r in sel])
            acc, acc_sd = stat([f(r, "final_accuracy") for r in sel])
            ev, _ = stat([f(r, "evidence_bytes") for r in sel])
            ladder.append({
                "disclosure": level, "attack": attack, "attack_name": ATTACK_NAMES[attack],
                "n_seeds": len(sel),
                "tpr_mean": tpr, "tpr_std": tpr_sd,
                "fpr_mean": fpr, "fpr_std": fpr_sd,
                "accuracy_mean": acc, "accuracy_std": acc_sd,
                "evidence_bytes_mean": ev,
            })
    path = SUMMARY / "e4_disclosure_table.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ladder[0].keys())); w.writeheader(); w.writerows(ladder)
    written.append(path)

    drift = []
    sel_all = [r for r in rows if r["attack"] == "A4"]
    for system in ("S0", "S1"):
        for beta in sorted({f(r, "beta") for r in sel_all}):
            for frac in sorted({f(r, "malicious_fraction") for r in sel_all}):
                sel = [r for r in sel_all if r["system"] == system
                       and abs(f(r, "beta") - beta) < 1e-9
                       and abs(f(r, "malicious_fraction") - frac) < 1e-9
                       and r["disclosure"] == "E2"]
                if not sel:
                    continue
                adm, adm_sd = stat([f(r, "malicious_admitted_fraction") for r in sel])
                acc, acc_sd = stat([f(r, "final_accuracy") for r in sel])
                tpr, _ = stat([f(r, "tpr") for r in sel])
                drift.append({
                    "system": system, "beta": beta, "malicious_fraction": frac,
                    "n_seeds": len(sel),
                    "malicious_admitted_mean": adm, "malicious_admitted_std": adm_sd,
                    "tpr_mean": tpr,
                    "accuracy_mean": acc, "accuracy_std": acc_sd,
                })
    path = SUMMARY / "e5_slow_drift_table.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(drift[0].keys())); w.writeheader(); w.writerows(drift)
    written.append(path)
    return written


def main() -> int:
    if not (SUMMARY / "e4e5_runs.csv").exists():
        print("Run scripts/exp_e4_e5.py first.")
        return 1
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = load()
    print(f"loaded {len(rows)} runs")
    for fn in (fig_disclosure_ladder, fig_system_comparison, fig_slow_drift,
               fig_slow_drift_by_level):
        print(f"wrote {fn(rows).relative_to(REPO_ROOT)}")
    for path in write_tables(rows):
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
