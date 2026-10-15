"""Aggregate the G3 confirmatory run into the tables the pre-registration asks for.

One section per pre-registered hypothesis, in the order they appear in
``G3_PREREGISTRATION.md`` section 8. Regressions print in the same tables as
improvements; nothing is filtered.

Usage:
    .venv/Scripts/python.exe scripts/analyze_g3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV = REPO_ROOT / "results" / "summary" / "g3_runs.csv"

ATTACK_NAMES = {
    "A0": "no attack", "A1": "sign-flip", "A2": "label-flip", "A3": "scaled",
    "A4": "slow-drift", "A5": "noise", "A6": "targeted", "A7": "adaptive",
    "A8": "null-space", "A9": "camouflage",
}


def arm(row) -> str:
    """The five pre-registered arms, by (system, rule)."""
    key = (row["system"], row["rule"])
    return {
        ("S0", "G1"): "S0 no-rule", ("S1", "G1"): "S1 G1",
        ("S1", "G2"): "S1b G2", ("S1", "G3"): "S1c G3", ("S2", "G3"): "S3 G3+full",
    }.get(key, f'{row["system"]}/{row["rule"]}')


def default_g3(d: pd.DataFrame) -> pd.DataFrame:
    """G3 rows with every ablation knob at its pre-registered default."""
    return d[(d.rule == "G3") & d.g3_population & d.g3_accumulate
             & ~d.g3_two_sided & (d.g3_gap_min == 0.0)]


def show(title: str, table: pd.DataFrame, note: str = "") -> None:
    print(f"\n{'='*78}\n{title}\n{'='*78}")
    print(table.to_string())
    if note:
        print(f"\n{note}")


def main() -> int:
    if not CSV.exists():
        print(f"missing {CSV}", file=sys.stderr)
        return 1
    d = pd.read_csv(CSV)
    config_columns = [
        "system", "rule", "warmup", "commit_then_sketch", "disclosure", "attack",
        "beta", "gamma", "malicious_fraction", "seed", "rounds",
        "g3_population", "g3_accumulate", "g3_two_sided", "g3_gap_min",
    ]
    before = len(d)
    d = d.drop_duplicates(subset=config_columns)
    if before != len(d):
        print(f"deduplicated {before - len(d)} repeated control-arm configs "
              f"({before} rows -> {len(d)} distinct configurations)")
    d["arm"] = d.apply(arm, axis=1)
    d["attack_name"] = d.attack.map(ATTACK_NAMES)
    print(f"G3 confirmatory analysis -- {len(d)} runs\n")

    # ---------------------------------------------------- X1 main comparison
    main_rows = d[(d.beta == 0.9) & (d.malicious_fraction.isin([0.0, 0.2]))
                  & (d.disclosure == "E3") & (d.seed.isin([0, 1, 2]))
                  & ~d.g3_two_sided & (d.g3_gap_min == 0.0)
                  & d.g3_population & d.g3_accumulate
                  & d.attack.isin(["A0", "A1", "A2", "A3", "A5", "A6", "A4"])]
    tpr = main_rows.pivot_table(index="attack_name", columns="arm", values="tpr", aggfunc="mean")
    fpr = main_rows.pivot_table(index="attack_name", columns="arm", values="fpr", aggfunc="mean")
    acc = main_rows.pivot_table(index="attack_name", columns="arm", values="final_accuracy", aggfunc="mean")
    show("X1  MAIN COMPARISON -- detection rate (TPR), 20% malicious, 3 seeds", tpr.round(3))
    show("X1  MAIN COMPARISON -- false-positive rate (FPR)", fpr.round(3))
    show("X1  MAIN COMPARISON -- final accuracy", acc.round(3))

    # -------------------------------------------- G3-P1 / G3-P2 headline read
    if "S1b G2" in tpr.columns and "S1c G3" in tpr.columns:
        delta = (tpr["S1c G3"] - tpr["S1b G2"]).round(3)
        show("G3-P1  TPR gain of G3 over G2, per attack", delta.to_frame("delta TPR"),
             "Pre-registered: slow-drift TPR >= 0.60 (P1); >= 0.20 gain = B, < 0.20 = C.")

    # ------------------------------------------------------- X2 beta sweep
    sweep = d[(d.attack == "A4") & (d.malicious_fraction == 0.2) & (d.disclosure == "E3")
              & (d.system == "S1") & (d.g3_gap_min == 0.0) & ~d.g3_two_sided
              & d.g3_population & d.g3_accumulate & d.seed.isin([0, 1, 2, 3, 4])]
    beta_tpr = sweep.pivot_table(index="beta", columns="rule", values="tpr", aggfunc="mean")
    beta_adm = sweep.pivot_table(index="beta", columns="rule",
                                 values="malicious_admitted_fraction", aggfunc="mean")
    show("X2  HEADLINE -- slow-drift beta sweep, TPR by rule generation (5 seeds)",
         beta_tpr.round(3))
    show("X2  HEADLINE -- fraction of malicious submissions ADMITTED", beta_adm.round(3))

    # ---------------------------------------- X3 disclosure / X4 acc / X5 scope
    drift5 = d[(d.attack == "A4") & (d.beta == 0.9) & (d.rule == "G3")
               & (d.system == "S1") & ~d.g3_two_sided & (d.g3_gap_min == 0.0)
               & (d.malicious_fraction == 0.2) & d.seed.isin([0, 1, 2, 3, 4])]
    disc = drift5[drift5.g3_population & drift5.g3_accumulate].groupby("disclosure").agg(
        tpr=("tpr", "mean"), fpr=("fpr", "mean"), accuracy=("final_accuracy", "mean"),
        evidence_bytes=("evidence_bytes", "mean"), n=("tpr", "size"))
    show("X3  G3-P5 -- is the SKETCH the bottleneck? E3 sketch vs E4 full plaintext",
         disc.round(3),
         "Pre-registered: E4 within 0.05 TPR of E3 => disclosure is NOT the limit.")

    accum = drift5[(drift5.disclosure == "E3") & drift5.g3_population].groupby(
        "g3_accumulate").agg(tpr=("tpr", "mean"), fpr=("fpr", "mean"), n=("tpr", "size"))
    show("X4  G3-P4 -- is the SINGLE-ROUND setting the bottleneck?", accum.round(3),
         "True = cross-round running mean; False = this round's score alone.\n"
         "Pre-registered: accumulation now helps by >= 0.05 TPR. G2-P3 refuted this\n"
         "under the MAD cutoff; this is the proper re-test with the cutoff fixed.")

    scope = drift5[(drift5.disclosure == "E3") & drift5.g3_accumulate].groupby(
        "g3_population").agg(tpr=("tpr", "mean"), fpr=("fpr", "mean"), n=("tpr", "size"))
    show("X5  G3-P3 -- does the ledger's cross-client POPULATION view earn its place?",
         scope.round(3),
         "True = split located over all clients; False = this round's ten only (G2 scope).")

    # ------------------------------------------------------- X6 gap gate
    gate = d[(d.rule == "G3") & (d.system == "S1") & ~d.g3_two_sided
             & d.g3_population & d.g3_accumulate & (d.disclosure == "E3")
             & d.attack.isin(["A0", "A4"])].groupby(
        ["g3_gap_min", "attack_name"]).agg(
        tpr=("tpr", "mean"), fpr=("fpr", "mean"), n=("tpr", "size"))
    show("X6  G3-P10 -- is the gap gate necessary? (calibration re-test, held-out seeds)",
         gate.round(3),
         "Pre-registered: gap_min 0.35 detects strictly worse at no FPR benefit.")

    # ---------------------------------------------- X7 adaptive, with damage
    clean = default_g3(d[(d.attack == "A0") & (d.disclosure == "E3")
                         & (d.system == "S1")]).final_accuracy
    clean_mean, clean_sd = float(clean.mean()), float(clean.std())
    adaptive = default_g3(d[(d.attack == "A7") & (d.system == "S1")]).groupby("gamma").agg(
        tpr=("tpr", "mean"), admitted=("malicious_admitted_fraction", "mean"),
        accuracy=("final_accuracy", "mean"), n=("tpr", "size"))
    adaptive["damage"] = (clean_mean - adaptive.accuracy).round(4)
    show("X7  G3-P7 -- adaptive attacker (A7) vs G3, evasion/damage curve",
         adaptive.round(3),
         f"Clean-run accuracy {clean_mean:.3f} +/- {clean_sd:.3f} (sd over seeds).\n"
         f"Damage within +/-{clean_sd:.3f} is inside the noise band.")

    # ------------------------------------------------------ X8 two-sided
    two = d[(d.rule == "G3") & d.g3_two_sided]
    # Match the two-sided arm exactly: it was run at gamma 0.5 only.
    one = default_g3(d[(d.system == "S1") & (d.disclosure == "E3")
                       & d.attack.isin(["A0", "A4", "A7"]) & (d.gamma == 0.5)
                       & (d.beta == 0.9) & d.seed.isin([0, 1, 2, 3, 4])])
    sided = pd.concat([
        two.assign(variant="two-sided"), one.assign(variant="one-sided"),
    ]).groupby(["attack_name", "variant"]).agg(
        tpr=("tpr", "mean"), fpr=("fpr", "mean"),
        accuracy=("final_accuracy", "mean"), n=("tpr", "size"))
    show("X8  G3-P8 -- is the adaptive gap fixable BY THE RULE? (two-sided ablation)",
         sided.round(3),
         "Pre-registered: two-sided catches A7 but at FPR > 0.15 -- a fix costing more\n"
         "than it is worth, given A7's damage is already within noise.")

    # ------------------------------------------------------ X9 A9 camouflage
    camo = d[(d.attack == "A9") & (d.system == "S1")].groupby("rule").agg(
        tpr=("tpr", "mean"), fpr=("fpr", "mean"),
        admitted=("malicious_admitted_fraction", "mean"),
        accuracy=("final_accuracy", "mean"), n=("tpr", "size"))
    camo["damage"] = (clean_mean - camo.accuracy).round(4)
    g3_drift = float(default_g3(d[(d.attack == "A4") & (d.beta == 0.9) & (d.system == "S1")
                                  & (d.disclosure == "E3")]).tpr.mean())
    show("X9  G3-P9 -- can our own defence be beaten? A9 camouflage", camo.round(3),
         f"G3 vs plain slow-drift for comparison: TPR {g3_drift:.3f}.\n"
         "Pre-registered: A9 drops G3 by >= 0.15 TPR, at a measured cost in damage.")

    # ---------------------------------------------------- X10 minority edge
    frac = default_g3(d[(d.system == "S1") & (d.disclosure == "E3")
                        & d.attack.isin(["A4", "A2"])]).groupby(
        ["attack_name", "malicious_fraction"]).agg(
        tpr=("tpr", "mean"), fpr=("fpr", "mean"), n=("tpr", "size"))
    show("X10  does the minority bound (f < 1/3) hold at its edge?", frac.round(4))

    # ------------------------------------------- G3-P6 machine-precision check
    pairs = []
    for attack in ("A1", "A2", "A4"):
        sel = d[(d.attack == attack) & (d.rule == "G3") & (d.beta == 0.9)
                & (d.disclosure == "E3") & (d.malicious_fraction == 0.2)
                & d.g3_population & d.g3_accumulate & ~d.g3_two_sided
                & (d.g3_gap_min == 0.0) & d.seed.isin([0, 1, 2])]
        s1c = sel[sel.system == "S1"].sort_values("seed")
        s3 = sel[sel.system == "S2"].sort_values("seed")
        if len(s1c) and len(s1c) == len(s3):
            pairs.append({
                "attack": ATTACK_NAMES[attack],
                "S1c accuracy": round(float(s1c.final_accuracy.mean()), 6),
                "S3 accuracy": round(float(s3.final_accuracy.mean()), 6),
                "max abs diff": float(np.abs(s1c.final_accuracy.values - s3.final_accuracy.values).max()),
                "TPR diff": float(np.abs(s1c.tpr.values - s3.tpr.values).max()),
                "transcript bytes": int(s3.transcript_bytes.mean()),
            })
    if pairs:
        show("G3-P6  does the verifiable mechanism change any ML outcome?",
             pd.DataFrame(pairs).set_index("attack"),
             "Pre-registered: S3 identical to S1c to machine precision. Third\n"
             "demonstration, now with a third independent rule generation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
