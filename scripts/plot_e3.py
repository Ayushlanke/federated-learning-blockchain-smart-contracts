"""Generate E-3 figures from the summary CSVs.

Reads only ``results/summary/*.csv`` so figures regenerate from committed data.

Usage:
    .venv/Scripts/python.exe scripts/plot_e3.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMARY = REPO_ROOT / "results" / "summary"
FIGURES = REPO_ROOT / "results" / "figures"

INK = "#1a1a1a"
OK = "#0b6e4f"
WARN = "#c1121f"
BASE = "#6a4c93"
PALETTE = ["#c1121f", "#e08c00", "#0b6e4f", "#1d4e89", "#6a4c93", "#7a5195", "#2f4858"]


def load(name: str) -> list[dict]:
    with (SUMMARY / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def style(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, which="both", alpha=0.18, linewidth=0.6)
    ax.set_axisbelow(True)


def fig_model_validation() -> Path:
    """Does the real sortition match the hypergeometric model?"""
    rows = load("e3a_model_validation.csv")
    emp = [float(r["empirical_forge_rate"]) for r in rows]
    ana = [float(r["analytic_forge_rate"]) for r in rows]
    sizes = sorted({int(r["committee_size"]) for r in rows})

    fig, ax = plt.subplots(figsize=(6.4, 6))
    lo, hi = 1e-5, 1.0
    ax.plot([lo, hi], [lo, hi], "--", color=INK, lw=1, alpha=0.5, label="perfect agreement")
    for i, size in enumerate(sizes):
        xs = [a for a, r in zip(ana, rows) if int(r["committee_size"]) == size]
        ys = [e for e, r in zip(emp, rows) if int(r["committee_size"]) == size]
        pts = [(x, y) for x, y in zip(xs, ys) if x > 0 and y > 0]
        if pts:
            ax.scatter(*zip(*pts), s=44, color=PALETTE[i % len(PALETTE)],
                       label=f"m={size}", zorder=3, alpha=0.85)

    n_ok = sum(1 for r in rows if r["within_3_sigma"] in ("True", "true", True))
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("Analytic forge probability (hypergeometric)")
    ax.set_ylabel("Empirical forge rate (real sortition)")
    ax.set_title(f"E-3a: The sortition matches the model\n"
                 f"{n_ok}/{len(rows)} cells within 3 sigma", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    style(ax)
    fig.tight_layout()
    out = FIGURES / "e3a_model_validation.png"
    fig.savefig(out, dpi=160); plt.close(fig)
    return out


def fig_design_curve() -> Path:
    """Forge probability vs corruption, per committee size, with the B2 baseline."""
    rows = load("e3b_forge_probability.csv")
    by_size = defaultdict(list)
    for r in rows:
        by_size[int(r["committee_size"])].append(
            (float(r["corrupt_fraction"]), float(r["forge_probability"]))
        )

    fig, ax = plt.subplots(figsize=(8, 5.2))
    floor = 1e-8
    for i, size in enumerate(sorted(by_size)):
        pts = sorted(by_size[size])
        xs = [x for x, _ in pts]
        ys = [max(y, floor) for _, y in pts]
        if size == 1:
            ax.plot(xs, ys, "D--", color=BASE, lw=2.4, ms=6,
                    label="m=1  (baseline B2: self-attestation)", zorder=5)
        else:
            ax.plot(xs, ys, "o-", color=PALETTE[i % len(PALETTE)], lw=1.8, ms=4.5,
                    label=f"m={size}", alpha=0.9)

    ax.axhline(0.01, color=INK, ls=":", lw=1.2, alpha=0.6)
    ax.text(0.021, 0.013, "1% risk budget", fontsize=8.5, color=INK, alpha=0.75)

    ax.set_yscale("log")
    ax.set_ylim(floor, 1.5)
    ax.set_xlabel("Fraction of the client population that is corrupt")
    ax.set_ylabel("P(corrupt coalition reaches the threshold)")
    ax.set_title("E-3b: Forge probability vs committee size\n"
                 "population 50, threshold = ceil(2m/3), analytic",
                 fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8.5, ncol=2, loc="lower right")
    style(ax)
    fig.tight_layout()
    out = FIGURES / "e3b_design_curve.png"
    fig.savefig(out, dpi=160); plt.close(fig)
    return out


def fig_grinding() -> Path:
    """The weakness: what seed grinding does to the design curve."""
    rows = load("e3d_grinding.csv")
    series = defaultdict(list)
    for r in rows:
        key = (int(r["committee_size"]), float(r["corrupt_fraction"]))
        series[key].append((int(r["grind_attempts"]), float(r["forge_probability"])))

    fig, ax = plt.subplots(figsize=(8, 5.2))
    floor = 1e-4
    styles = {5: ":", 9: "--", 15: "-"}
    colours = {0.2: "#0b6e4f", 0.3: "#e08c00", 0.4: "#c1121f"}
    for (size, frac), pts in sorted(series.items()):
        pts = sorted(pts)
        xs = [max(g, 1) for g, _ in pts]
        ys = [max(p, floor) for _, p in pts]
        ax.plot(xs, ys, styles.get(size, "-"), marker="o", ms=4.5, lw=1.9,
                color=colours.get(round(frac, 2), INK),
                label=f"m={size}, corrupt {frac:.0%}")

    ax.axhline(0.01, color=INK, ls=":", lw=1.2, alpha=0.6)
    ax.text(1.1, 0.013, "1% risk budget", fontsize=8.5, color=INK, alpha=0.75)

    ax.set_xscale("log", base=2); ax.set_yscale("log")
    ax.set_ylim(floor, 1.6)
    ax.set_xlabel("Grinding budget G (candidate seeds the adversary may try, log scale)")
    ax.set_ylabel("P(forged admission accepted)")
    ax.set_title("E-3d: Seed grinding breaks the design curve\n"
                 "committee sizes chosen without grinding in mind are optimistic",
                 fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="lower right")
    style(ax)
    fig.tight_layout()
    out = FIGURES / "e3d_grinding.png"
    fig.savefig(out, dpi=160); plt.close(fig)
    return out


def main() -> int:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for fn in (fig_model_validation, fig_design_curve, fig_grinding):
        print(f"wrote {fn().relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
