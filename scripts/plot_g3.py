"""Generate G3 figures from ``results/summary/g3_runs.csv``.

Reads committed data only, so the figures regenerate without re-running the
160-minute experiment. Every point is a mean over seeds with the spread shown.

The three rule generations appear together in every figure. G1 and G2 are never
dropped from a plot to make G3 look better.

Usage:
    .venv/Scripts/python.exe scripts/plot_g3.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMARY = REPO_ROOT / "results" / "summary"
FIGURES = REPO_ROOT / "results" / "figures"

INK = "#1a1a1a"
RULE_COLOURS = {"G1": "#adb5bd", "G2": "#1d4e89", "G3": "#0b6e4f"}
ATTACK_NAMES = {
    "A0": "no attack", "A1": "sign-flip", "A2": "label-flip", "A3": "scaled",
    "A4": "slow-drift", "A5": "noise", "A6": "targeted", "A7": "adaptive",
    "A9": "camouflage",
}


def load() -> pd.DataFrame:
    d = pd.read_csv(SUMMARY / "g3_runs.csv")
    return d.drop_duplicates(subset=[
        "system", "rule", "disclosure", "attack", "beta", "gamma",
        "malicious_fraction", "seed", "g3_population", "g3_accumulate",
        "g3_two_sided", "g3_gap_min",
    ])


def default_g3(d: pd.DataFrame) -> pd.DataFrame:
    return d[(d.rule == "G3") & d.g3_population & d.g3_accumulate
             & ~d.g3_two_sided & (d.g3_gap_min == 0.0)]


def style(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=INK)
    ax.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax.set_axisbelow(True)


def fig_beta_sweep(d: pd.DataFrame) -> None:
    """The headline: how each rule generation handles an evasive slow-drift attacker."""
    sweep = d[(d.attack == "A4") & (d.malicious_fraction == 0.2) & (d.system == "S1")
              & (d.disclosure == "E3") & (d.g3_gap_min == 0.0) & ~d.g3_two_sided
              & d.g3_population & d.g3_accumulate & d.seed.isin([0, 1, 2, 3, 4])]
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.2))
    for rule in ("G1", "G2", "G3"):
        part = sweep[sweep.rule == rule].groupby("beta").tpr.agg(["mean", "std"])
        left.errorbar(part.index, part["mean"], yerr=part["std"], marker="o",
                      capsize=3, color=RULE_COLOURS[rule], label=rule, linewidth=1.8)
        adm = sweep[sweep.rule == rule].groupby("beta").malicious_admitted_fraction.mean()
        right.plot(adm.index, adm.values, marker="o", color=RULE_COLOURS[rule],
                   label=rule, linewidth=1.8)
    left.axvline(1.0, color=INK, linestyle=":", linewidth=1)
    left.text(1.02, 0.02, "rejection\nthreshold", fontsize=8, color=INK)
    left.set_xlabel("attacker magnitude $\\beta$ (fraction of the threshold)")
    left.set_ylabel("detection rate (TPR)")
    left.set_title("Detection vs an evasive attacker", color=INK, fontsize=11)
    right.axvline(1.0, color=INK, linestyle=":", linewidth=1)
    right.set_xlabel("attacker magnitude $\\beta$")
    right.set_ylabel("malicious submissions admitted")
    right.set_title("What still gets through", color=INK, fontsize=11)
    for ax in (left, right):
        style(ax)
        ax.legend(frameon=False, fontsize=9)
    fig.suptitle("Slow-drift attacker: three generations of admission rule",
                 color=INK, fontsize=12.5)
    fig.tight_layout()
    fig.savefig(FIGURES / "g3_beta_sweep.png", dpi=160)
    plt.close(fig)


def fig_main_comparison(d: pd.DataFrame) -> None:
    """Per-attack detection across all three rules, regressions included."""
    rows = d[(d.beta == 0.9) & (d.disclosure == "E3") & (d.system == "S1")
             & (d.malicious_fraction == 0.2) & (d.g3_gap_min == 0.0)
             & ~d.g3_two_sided & d.g3_population & d.g3_accumulate
             & d.seed.isin([0, 1, 2])
             & d.attack.isin(["A1", "A2", "A3", "A4", "A5", "A6"])]
    pivot = rows.pivot_table(index="attack", columns="rule", values="tpr", aggfunc="mean")
    pivot.index = [ATTACK_NAMES[a] for a in pivot.index]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    pivot[["G1", "G2", "G3"]].plot.bar(
        ax=ax, color=[RULE_COLOURS[r] for r in ("G1", "G2", "G3")],
        edgecolor="white", linewidth=0.8, width=0.78,
    )
    ax.set_ylabel("detection rate (TPR)")
    ax.set_xlabel("")
    ax.set_ylim(0, 1.05)
    ax.axhline(0.8, color="#c1121f", linestyle="--", linewidth=1)
    ax.text(-0.45, 0.815, "pre-registered bar for a strong result (0.80)",
            fontsize=8, color="#c1121f")
    plt.setp(ax.get_xticklabels(), rotation=0)
    style(ax)
    ax.legend(frameon=False, fontsize=9, title="rule", title_fontsize=9)
    ax.set_title("Detection by attack, 20% malicious -- regressions shown, not hidden",
                 color=INK, fontsize=11.5)
    fig.tight_layout()
    fig.savefig(FIGURES / "g3_main_comparison.png", dpi=160)
    plt.close(fig)


def fig_where_the_limit_is(d: pd.DataFrame) -> None:
    """The four candidate causes of the residual weakness, measured side by side."""
    drift = d[(d.attack == "A4") & (d.beta == 0.9) & (d.rule == "G3")
              & (d.system == "S1") & ~d.g3_two_sided & (d.g3_gap_min == 0.0)
              & (d.malicious_fraction == 0.2) & d.seed.isin([0, 1, 2, 3, 4])]
    bars, labels, colours = [], [], []

    def add(label, subset, colour):
        if len(subset):
            bars.append(subset.tpr.mean())
            labels.append(label)
            colours.append(colour)

    base = drift[(drift.disclosure == "E3") & drift.g3_population & drift.g3_accumulate]
    add("G2 rule\n(previous)", d[(d.attack == "A4") & (d.beta == 0.9) & (d.rule == "G2")
                                 & (d.system == "S1") & (d.disclosure == "E3")
                                 & (d.malicious_fraction == 0.2)
                                 & d.seed.isin([0, 1, 2, 3, 4])], RULE_COLOURS["G2"])
    add("G3 rule\n(this work)", base, RULE_COLOURS["G3"])
    add("single-round\n(no memory)",
        drift[(drift.disclosure == "E3") & ~drift.g3_accumulate & drift.g3_population],
        "#e08c00")
    add("round-local\nscope",
        drift[(drift.disclosure == "E3") & ~drift.g3_population & drift.g3_accumulate],
        "#e08c00")
    add("full plaintext\n(E4)",
        drift[(drift.disclosure == "E4") & drift.g3_population & drift.g3_accumulate],
        "#1d4e89")

    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.bar(labels, bars, color=colours, edgecolor="white", linewidth=0.8)
    for i, value in enumerate(bars):
        ax.text(i, value + 0.015, f"{value:.2f}", ha="center", fontsize=9, color=INK)
    ax.set_ylabel("detection rate vs slow drift (TPR)")
    ax.set_ylim(0, max(bars) * 1.25 if bars else 1)
    style(ax)
    ax.set_title("Where the remaining limit actually is", color=INK, fontsize=11.5)
    fig.tight_layout()
    fig.savefig(FIGURES / "g3_where_the_limit_is.png", dpi=160)
    plt.close(fig)


def fig_adaptive_and_camouflage(d: pd.DataFrame) -> None:
    """Both attacks that beat us, with the price each pays."""
    clean = default_g3(d[(d.attack == "A0") & (d.system == "S1")
                         & (d.disclosure == "E3")]).final_accuracy
    clean_mean, clean_sd = float(clean.mean()), float(clean.std())

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.2))
    adaptive = default_g3(d[(d.attack == "A7") & (d.system == "S1")]).groupby("gamma").agg(
        tpr=("tpr", "mean"), accuracy=("final_accuracy", "mean"))
    left.plot(adaptive.index, adaptive.tpr, marker="o", color=RULE_COLOURS["G3"],
              label="detection rate", linewidth=1.8)
    damage = clean_mean - adaptive.accuracy
    left.plot(adaptive.index, damage, marker="s", color="#c1121f",
              label="accuracy damage", linewidth=1.8)
    left.axhspan(-clean_sd, clean_sd, color="#c1121f", alpha=0.10)
    left.text(0.02, clean_sd + 0.01, "noise band", fontsize=8, color="#c1121f")
    left.set_xlabel("$\\gamma$ (fraction of malicious direction retained)")
    left.set_ylabel("rate")
    left.set_title("A7 adaptive: evades freely, achieves nothing", color=INK, fontsize=11)

    camo = d[(d.attack == "A9") & (d.system == "S1")].groupby("rule").tpr.mean()
    drift_ref = {
        rule: d[(d.attack == "A4") & (d.beta == 0.9) & (d.rule == rule)
                & (d.system == "S1") & (d.disclosure == "E3")
                & (d.malicious_fraction == 0.2)
                & d.seed.isin([0, 1, 2, 3, 4])].tpr.mean()
        for rule in camo.index
    }
    x = range(len(camo))
    right.bar([i - 0.2 for i in x], [drift_ref[r] for r in camo.index], width=0.4,
              color="#adb5bd", edgecolor="white", label="plain slow drift")
    right.bar([i + 0.2 for i in x], camo.values, width=0.4,
              color=RULE_COLOURS["G3"], edgecolor="white", label="A9 camouflage")
    right.set_xticks(list(x))
    right.set_xticklabels(camo.index)
    right.set_ylabel("detection rate (TPR)")
    right.set_title("A9 camouflage: an attack built to beat G3", color=INK, fontsize=11)
    for ax in (left, right):
        style(ax)
        ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES / "g3_adaptive_camouflage.png", dpi=160)
    plt.close(fig)


def main() -> int:
    FIGURES.mkdir(parents=True, exist_ok=True)
    d = load()
    fig_beta_sweep(d)
    fig_main_comparison(d)
    fig_where_the_limit_is(d)
    fig_adaptive_and_camouflage(d)
    print("wrote 4 figures to results/figures/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
