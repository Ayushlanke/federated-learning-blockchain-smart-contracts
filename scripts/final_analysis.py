"""Final corrected analysis of the G3 confirmatory experiment.

Answers ten questions explicitly, in order, with paired statistics rather than bare
means. Seeds are matched across arms, so every arm-vs-arm comparison is **paired by
seed** -- far more powerful than an unpaired comparison at n = 3-5, and the only
correct treatment when the same seed drives both arms.

Every effect is reported as::

    mean difference  [95% CI]  Cohen's d_z  n

A confidence interval that straddles zero is reported as straddling zero. No claim of
equality is made from a non-significant difference; equality is only claimed where the
measured difference is exactly zero.

Usage:
    .venv/Scripts/python.exe scripts/final_analysis.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMARY = REPO_ROOT / "results" / "summary"
FINAL = SUMMARY / "g3_runs.csv"
RUN1 = SUMMARY / "g3_runs_run1_prefix.csv"

ATTACK_NAMES = {
    "A0": "no attack", "A1": "sign-flip", "A2": "label-flip", "A3": "scaled",
    "A4": "slow-drift", "A5": "noise", "A6": "targeted", "A7": "adaptive",
    "A8": "null-space", "A9": "camouflage",
}
KEY = [
    "system", "rule", "disclosure", "attack", "beta", "gamma",
    "malicious_fraction", "seed", "g3_population", "g3_accumulate",
    "g3_two_sided", "g3_gap_min",
]


# ------------------------------------------------------------------ statistics
def describe(values: Sequence[float]) -> str:
    """mean +/- sd [95% CI] (n) for a single group."""
    x = np.asarray([v for v in values if not np.isnan(v)], dtype=float)
    n = x.size
    if n == 0:
        return "no data"
    if n == 1:
        return f"{x[0]:.3f} (n=1, no interval)"
    mean, sd = x.mean(), x.std(ddof=1)
    half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    return f"{mean:.3f} +/- {sd:.3f} [{mean-half:.3f}, {mean+half:.3f}] (n={n})"


def paired(a: pd.Series, b: pd.Series, index: str = "seed") -> Dict[str, object]:
    """Paired difference a - b, aligned on ``index``.

    Returns mean difference, its 95% CI, Cohen's d_z, and the number of pairs. A
    paired design is used because the same seed drives both arms; treating the arms
    as independent would throw away that pairing and inflate the interval.
    """
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    diff = (joined.a - joined.b).to_numpy(dtype=float)
    n = diff.size
    if n < 2:
        return {"n": n, "mean": float(diff.mean()) if n else float("nan"),
                "ci": (float("nan"), float("nan")), "d": float("nan"), "p": float("nan")}
    mean, sd = diff.mean(), diff.std(ddof=1)
    if sd == 0:
        return {"n": n, "mean": float(mean), "ci": (float(mean), float(mean)),
                "d": float("inf") if mean else 0.0, "p": 0.0 if mean else 1.0}
    half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    t_stat, p_value = stats.ttest_rel(joined.a, joined.b)
    return {"n": n, "mean": float(mean), "ci": (float(mean - half), float(mean + half)),
            "d": float(mean / sd), "p": float(p_value)}


def fmt(result: Dict[str, object], label: str = "") -> str:
    if result["n"] < 2:
        return f"{label:<44s} insufficient pairs (n={result['n']})"
    low, high = result["ci"]
    if result["mean"] == 0.0 and low == 0.0 and high == 0.0:
        return (f"{label:<44s} EXACTLY ZERO in every one of "
                f"{result['n']} paired runs")
    crosses = "  (CI straddles zero -- not distinguishable from no effect)"         if low <= 0 <= high else ""
    return (f"{label:<44s} {result['mean']:+.3f}  [{low:+.3f}, {high:+.3f}]  "
            f"d_z={result['d']:+.2f}  p={result['p']:.3f}  n={result['n']}{crosses}")


def header(text: str) -> None:
    print(f"\n{'='*80}\n{text}\n{'='*80}")


# --------------------------------------------------------------------- loading
def load(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    for column in ("g3_population", "g3_accumulate", "g3_two_sided"):
        if d[column].dtype == object:
            d[column] = d[column].map({"True": True, "False": False}).astype(bool)
    d = d.drop_duplicates(subset=KEY)
    d["attack_name"] = d.attack.map(ATTACK_NAMES)
    return d


def g3_default(d: pd.DataFrame) -> pd.DataFrame:
    return d[(d.rule == "G3") & d.g3_population & d.g3_accumulate
             & ~d.g3_two_sided & (d.g3_gap_min == 0.0)]


def drift_arm(d: pd.DataFrame, rule: str, **overrides) -> pd.Series:
    """Slow-drift TPR indexed by seed for one arm, for paired comparison."""
    sel = d[(d.attack == "A4") & (d.beta == 0.9) & (d.malicious_fraction == 0.2)
            & (d.rule == rule) & (d.system == overrides.pop("system", "S1"))
            & (d.disclosure == overrides.pop("disclosure", "E3"))
            & (d.g3_gap_min == overrides.pop("g3_gap_min", 0.0))
            & (d.g3_two_sided == overrides.pop("g3_two_sided", False))
            & (d.g3_population == overrides.pop("g3_population", True))
            & (d.g3_accumulate == overrides.pop("g3_accumulate", True))]
    return sel.set_index("seed").tpr.sort_index()


# ----------------------------------------------------------------------- main
def main() -> int:
    if not FINAL.exists():
        print(f"missing {FINAL}", file=sys.stderr)
        return 1
    d = load(FINAL)
    print(f"FINAL CORRECTED ANALYSIS -- {len(d)} distinct configurations "
          f"(deterministic seeding)")

    # ============================================================= QUESTION 1
    header("Q1  Did fixing deterministic seeding change any headline conclusion?")
    if RUN1.exists():
        r1 = load(RUN1)
        print("Run 1 is INVALIDATED (process-salted training seeds). Shown only to")
        print("quantify how much the defect moved the numbers.\n")
        print(f"{'metric':<34s} {'Run 1 (invalid)':>16s} {'Run 2 (valid)':>16s} {'delta':>9s}")
        print("-" * 80)
        for label, rule in (("slow-drift TPR, G1", "G1"), ("slow-drift TPR, G2", "G2"),
                            ("slow-drift TPR, G3", "G3")):
            a, b = drift_arm(r1, rule), drift_arm(d, rule)
            if len(a) and len(b):
                print(f"{label:<34s} {a.mean():>16.3f} {b.mean():>16.3f} "
                      f"{b.mean()-a.mean():>+9.3f}")
        for label, attack in (("sign-flip TPR, G3", "A1"), ("label-flip TPR, G3", "A2")):
            va, vb = [
                g3_default(x[(x.attack == attack) & (x.system == "S1")
                             & (x.disclosure == "E3")]).tpr
                for x in (r1, d)
            ]
            if len(va) and len(vb):
                print(f"{label:<34s} {va.mean():>16.3f} {vb.mean():>16.3f} "
                      f"{vb.mean()-va.mean():>+9.3f}")
    else:
        print("Run 1 artefact not found.")

    # ============================================================= QUESTION 2/3
    header("Q2/Q3  Is E3 genuinely worse than E4, and by how much? (paired by seed)")
    e3 = drift_arm(d, "G3", disclosure="E3")
    e4 = drift_arm(d, "G3", disclosure="E4")
    print(f"E3  64-dim sketch : {describe(e3.values)}")
    print(f"E4  full plaintext: {describe(e4.values)}\n")
    print(fmt(paired(e4, e3), "E4 - E3 (detection lost to the sketch)"))
    ev = d[(d.attack == "A4") & (d.rule == "G3") & (d.system == "S1")].groupby(
        "disclosure").evidence_bytes.mean()
    if len(ev) > 1:
        print(f"\nEvidence disclosed per run: E3 {ev.get('E3', 0):,.0f} bytes, "
              f"E4 {ev.get('E4', 0):,.0f} bytes "
              f"({ev.get('E4', 1)/max(ev.get('E3', 1), 1):.0f}x more)")
    print("\nPre-registered G3-P5: E4 within 0.05 TPR of E3 => disclosure NOT the limit.")

    # ============================================================= QUESTION 4
    header("Q4  Which is the bottleneck? Every intervention, paired, same metric")
    print("All rows: effect on slow-drift TPR at beta=0.9, 20% malicious, paired by seed.\n")
    g1, g2, g3 = (drift_arm(d, r) for r in ("G1", "G2", "G3"))
    rows: List[Tuple[str, Dict[str, object]]] = [
        ("[RULE] G2 - G1", paired(g2, g1)),
        ("[RULE] G3 - G2", paired(g3, g2)),
        ("[RULE] G3 - G1 (cumulative)", paired(g3, g1)),
        ("[AGGREGATION] accumulate - single-round",
         paired(g3, drift_arm(d, "G3", g3_accumulate=False))),
        ("[AGGREGATION] population - round-local",
         paired(g3, drift_arm(d, "G3", g3_population=False))),
        ("[DISCLOSURE] E4 plaintext - E3 sketch", paired(e4, e3)),
        ("[GATE] gap 0 - gap 0.35", paired(g3, drift_arm(d, "G3", g3_gap_min=0.35))),
        ("[MECHANISM] S3 full - S1c trusted", paired(drift_arm(d, "G3", system="S2"), g3)),
    ]
    for label, result in rows:
        print(fmt(result, label))

    print("\nAttacker adaptation, against the SAME rule (G3), unpaired across attacks:")
    for attack in ("A4", "A9", "A7"):
        sel = g3_default(d[(d.attack == attack) & (d.system == "S1")
                           & (d.disclosure == "E3")])
        if attack == "A7":
            sel = sel[sel.gamma == 0.5]
        if attack == "A4":
            sel = sel[sel.beta == 0.9]
        if len(sel):
            print(f"  {ATTACK_NAMES[attack]:<12s} TPR {describe(sel.tpr.values)}")

    # ============================================================= QUESTION 5
    header("Q5  S1c (trusted) vs S3 (full verifiable mechanism), deterministic seeds")
    print("Exact equality is claimed ONLY where the measured difference is exactly 0.\n")
    print(f"{'attack':<14s} {'S1c acc':>10s} {'S3 acc':>10s} {'max |diff|':>12s} "
          f"{'TPR diff':>10s} {'seeds':>6s}")
    print("-" * 80)
    any_nonzero = False
    for attack in ("A1", "A2", "A3", "A4", "A5", "A6"):
        base = d[(d.attack == attack) & (d.rule == "G3") & (d.beta == 0.9)
                 & (d.disclosure == "E3") & (d.malicious_fraction == 0.2)
                 & d.g3_population & d.g3_accumulate & ~d.g3_two_sided
                 & (d.g3_gap_min == 0.0)]
        s1c = base[base.system == "S1"].set_index("seed").sort_index()
        s3 = base[base.system == "S2"].set_index("seed").sort_index()
        shared = s1c.index.intersection(s3.index)
        if len(shared) == 0:
            continue
        acc_diff = np.abs(s1c.loc[shared].final_accuracy.values
                          - s3.loc[shared].final_accuracy.values)
        tpr_diff = np.abs(s1c.loc[shared].tpr.values - s3.loc[shared].tpr.values)
        any_nonzero |= bool(acc_diff.max() > 0 or np.nanmax(tpr_diff) > 0)
        print(f"{ATTACK_NAMES[attack]:<14s} {s1c.loc[shared].final_accuracy.mean():>10.4f} "
              f"{s3.loc[shared].final_accuracy.mean():>10.4f} {acc_diff.max():>12.2e} "
              f"{np.nanmax(tpr_diff):>10.3f} {len(shared):>6d}")
    print(f"\nAny nonzero difference anywhere: {any_nonzero}")
    tb = d[(d.system == "S2") & (d.rule == "G3")].transcript_bytes.mean()
    print(f"Transcript overhead of the full mechanism: {tb:,.0f} bytes per run")

    # ============================================================= QUESTION 9
    header("Q9  Main comparison with intervals -- every arm, every attack")
    main_rows = d[(d.beta == 0.9) & (d.disclosure == "E3") & d.seed.isin([0, 1, 2])
                  & (d.malicious_fraction.isin([0.0, 0.2]))
                  & ~d.g3_two_sided & (d.g3_gap_min == 0.0)
                  & d.g3_population & d.g3_accumulate
                  & d.attack.isin(["A0", "A1", "A2", "A3", "A4", "A5", "A6"])]
    arm_of = {("S0", "G1"): "S0 no-rule", ("S1", "G1"): "S1 G1", ("S1", "G2"): "S1b G2",
              ("S1", "G3"): "S1c G3", ("S2", "G3"): "S3 G3+full"}
    main_rows = main_rows.assign(
        arm=[arm_of.get((s, r), f"{s}/{r}") for s, r in zip(main_rows.system, main_rows.rule)])
    for metric in ("tpr", "fpr"):
        print(f"\n--- {metric.upper()}  (mean +/- sd over 3 seeds) ---")
        pivot = main_rows.pivot_table(index="attack_name", columns="arm", values=metric,
                                      aggfunc=lambda x: f"{np.mean(x):.3f}+/-{np.std(x, ddof=1):.3f}")
        print(pivot.to_string())

    print("\n--- Paired G3 - G2 per attack (the pre-registered comparison) ---")
    for attack in ("A1", "A2", "A3", "A4", "A5", "A6"):
        def arm_series(rule):
            sel = main_rows[(main_rows.attack == attack) & (main_rows.rule == rule)
                            & (main_rows.system == "S1")]
            return sel.set_index("seed").tpr.sort_index()
        print(fmt(paired(arm_series("G3"), arm_series("G2")), f"  {ATTACK_NAMES[attack]}"))

    # ================================================== adaptive + camouflage
    header("Adaptive (A7) and camouflage (A9): the attacks that beat the rule")
    clean = g3_default(d[(d.attack == "A0") & (d.system == "S1")
                         & (d.disclosure == "E3")]).final_accuracy
    clean_mean, clean_sd = float(clean.mean()), float(clean.std(ddof=1))
    print(f"Clean-run accuracy: {describe(clean.values)}")
    print(f"Noise band: +/-{clean_sd:.3f}\n")
    a7 = g3_default(d[(d.attack == "A7") & (d.system == "S1")])
    for gamma, group in a7.groupby("gamma"):
        damage = clean_mean - group.final_accuracy.mean()
        verdict = "inside noise" if abs(damage) <= clean_sd else "REAL DAMAGE"
        print(f"  A7 gamma={gamma:<5.2f} TPR {group.tpr.mean():.3f}  "
              f"admitted {group.malicious_admitted_fraction.mean():.3f}  "
              f"damage {damage:+.4f}  ({verdict})")
    print()
    for rule, group in d[(d.attack == "A9") & (d.system == "S1")].groupby("rule"):
        damage = clean_mean - group.final_accuracy.mean()
        print(f"  A9 vs {rule}  TPR {describe(group.tpr.values)}  damage {damage:+.4f}")
    a9_g3 = d[(d.attack == "A9") & (d.system == "S1") & (d.rule == "G3")].set_index("seed").tpr
    print()
    print(fmt(paired(a9_g3.sort_index(), g3), "A9 camouflage - plain slow drift (G3)"))

    # ------------------------------------------------------------- two-sided
    header("Two-sided ablation: is the adaptive gap fixable BY THE RULE?")
    for attack, gamma in (("A0", None), ("A7", 0.5), ("A4", None)):
        one = g3_default(d[(d.attack == attack) & (d.system == "S1")
                           & (d.disclosure == "E3") & d.seed.isin([0, 1, 2, 3, 4])])
        two = d[(d.attack == attack) & (d.rule == "G3") & d.g3_two_sided]
        if gamma is not None:
            one, two = one[one.gamma == gamma], two[two.gamma == gamma]
        else:
            one = one[one.beta == 0.9]
        if not len(one) or not len(two):
            continue
        print(f"{ATTACK_NAMES[attack]:<12s} one-sided TPR {one.tpr.mean():.3f} "
              f"FPR {one.fpr.mean():.3f}  |  two-sided TPR {two.tpr.mean():.3f} "
              f"FPR {two.fpr.mean():.3f}")
        print(f"{'':12s} {fmt(paired(two.set_index('seed').tpr.sort_index(), one.set_index('seed').tpr.sort_index()), 'TPR two - one')}")
        print(f"{'':12s} {fmt(paired(two.set_index('seed').fpr.sort_index(), one.set_index('seed').fpr.sort_index()), 'FPR two - one')}")

    # ------------------------------------------------------------ beta sweep
    header("Slow-drift beta sweep -- all three rule generations, 5 seeds")
    sweep = d[(d.attack == "A4") & (d.malicious_fraction == 0.2) & (d.disclosure == "E3")
              & (d.system == "S1") & (d.g3_gap_min == 0.0) & ~d.g3_two_sided
              & d.g3_population & d.g3_accumulate]
    print(sweep.pivot_table(index="beta", columns="rule", values="tpr",
                            aggfunc=lambda x: f"{np.mean(x):.3f}+/-{np.std(x, ddof=1):.3f}"
                            ).to_string())
    print("\nfraction of malicious submissions ADMITTED:")
    print(sweep.pivot_table(index="beta", columns="rule",
                            values="malicious_admitted_fraction", aggfunc="mean"
                            ).round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
