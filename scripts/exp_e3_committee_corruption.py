"""Experiment E-3: how does committee corruption break AG1 soundness?

Tests sub-claim **C3** -- "soundness degrades predictably and quantifiably with
committee corruption."

E-2 showed the auditor catches every attack from an adversary *weaker than the
threshold*. E-3 asks the obvious follow-up: how much corruption does it take to get
past it, and can that be predicted rather than guessed?

Four sub-experiments
--------------------
E-3a  Does the real sortition match the hypergeometric model? (validates the model)
E-3b  Forge probability vs committee size and corruption fraction. (the design curve)
E-3c  Rotating vs fixed committee. (does rotation actually help?)
E-3d  Grinding: what if the adversary can *choose* the sortition seed? (the limitation)

ASSUMPTIONS BEHIND EVERY NUMBER -- read before quoting any of them
-------------------------------------------------------------------
The hypergeometric model is exact **only** under all of the following. Where a
sub-experiment violates one, it says so.

  A1  The sortition seed is not adversarially chosen.
      -> DELIBERATELY VIOLATED in E-3d, which is the point of that sub-experiment.
  A2  The corrupt set is fixed before selection (static corruption), and the
      adversary cannot corrupt members *after* seeing the committee.
      -> An adaptive adversary who bribes whoever is selected defeats any committee
         size; not modelled here, and stated as a limitation.
  A3  Selection is uniform without replacement from a fixed eligible population.
      -> This is what makes the count hypergeometric rather than binomial.
  A4  Every corrupt member selected will sign. Honest members never sign a false set.
  A5  The population is fixed: no Sybil identities.
      -> The SoK is explicit that AG1 provides no Sybil resistance without external
         trust anchors. Inflating the corrupt fraction via fake identities is
         strictly easier than any attack modelled here.
  A6  Committee membership is observable, so the adversary knows whom to target.

Under A1-A6 the forge probability is a **cryptographic-soundness-style statement**:
it holds for any adversary within the model. Outside them -- adaptive corruption,
Sybils, seed manipulation -- it is **not** a security guarantee, and is reported as
such.

Usage:
    .venv/Scripts/python.exe scripts/exp_e3_committee_corruption.py [--quick]
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from bcflsrv.bench.manifest import Manifest  # noqa: E402
from bcflsrv.crypto.sortition import (  # noqa: E402
    corruption_probability,
    select_committee,
    smallest_safe_committee,
)

EXPERIMENT_ID = "E-3"
POPULATION_SIZE = 50
ROOT = bytes.fromhex("5e" * 32)
POPULATION = tuple(f"client-{i:03d}" for i in range(POPULATION_SIZE))


def threshold_for(size: int, fraction: float = 2 / 3) -> int:
    """Ceil(size * fraction), clamped -- the supermajority rule used throughout."""
    t = -(-int(round(size * fraction * 1000)) // 1000)
    return max(1, min(size, t))


def corrupt_set(n_corrupt: int) -> frozenset[str]:
    """A fixed corrupt subset (assumption A2: static corruption)."""
    return frozenset(POPULATION[:n_corrupt])


def empirical_forge_rate(
    n_corrupt: int, size: int, threshold: int, trials: int, seed_offset: int = 0
) -> float:
    """Fraction of sortitions in which the corrupt coalition reaches the threshold.

    Uses the REAL select_committee, not an idealised sampler -- the point is to
    validate the implementation, not to re-derive the textbook distribution.
    """
    bad = corrupt_set(n_corrupt)
    hits = 0
    for r in range(trials):
        committee = select_committee(ROOT, seed_offset + r, POPULATION, size)
        if sum(1 for c in committee if c in bad) >= threshold:
            hits += 1
    return hits / trials


# ---------------------------------------------------------------------------
# E-3a -- model validation
# ---------------------------------------------------------------------------

def run_e3a(sizes: Sequence[int], corrupt_counts: Sequence[int], trials: int) -> List[dict]:
    rows = []
    print(f"{'m':>4} {'thr':>4} {'corrupt':>8} {'empirical':>10} {'analytic':>10} "
          f"{'abs diff':>9} {'within 3s':>10}")
    for size in sizes:
        thr = threshold_for(size)
        for n_corrupt in corrupt_counts:
            emp = empirical_forge_rate(n_corrupt, size, thr, trials)
            ana = corruption_probability(POPULATION_SIZE, n_corrupt, size, thr)
            sigma = (ana * (1 - ana) / trials) ** 0.5 if 0 < ana < 1 else 0.0
            ok = abs(emp - ana) <= max(3 * sigma, 1.5 / trials)
            rows.append({
                "committee_size": size, "threshold": thr,
                "corrupt_clients": n_corrupt,
                "corrupt_fraction": n_corrupt / POPULATION_SIZE,
                "empirical_forge_rate": emp, "analytic_forge_rate": ana,
                "abs_difference": abs(emp - ana), "within_3_sigma": ok,
                "trials": trials,
            })
            print(f"{size:>4} {thr:>4} {n_corrupt:>8} {emp:>10.4f} {ana:>10.4f} "
                  f"{abs(emp-ana):>9.4f} {str(ok):>10}")
    return rows


# ---------------------------------------------------------------------------
# E-3b -- the design curve, with the self-attestation baseline
# ---------------------------------------------------------------------------

def run_e3b(sizes: Sequence[int], fractions: Sequence[float]) -> List[dict]:
    """Analytic forge probability across the design space.

    Committee size 1 is baseline **B2 (self-attestation)**: a single attester, so the
    forge probability is exactly the probability that attester is corrupt.
    """
    rows = []
    for size in sizes:
        thr = threshold_for(size)
        for f in fractions:
            n_corrupt = round(f * POPULATION_SIZE)
            p = corruption_probability(POPULATION_SIZE, n_corrupt, size, thr)
            rows.append({
                "committee_size": size, "threshold": thr,
                "corrupt_fraction": n_corrupt / POPULATION_SIZE,
                "corrupt_clients": n_corrupt,
                "forge_probability": p,
                "is_baseline_self_attestation": size == 1,
            })
    return rows


def run_e3b_sizing(fractions: Sequence[float], budgets: Sequence[float]) -> List[dict]:
    """Smallest committee meeting a risk budget -- turns sizing into a choice."""
    rows = []
    for f in fractions:
        n_corrupt = round(f * POPULATION_SIZE)
        for budget in budgets:
            size = smallest_safe_committee(POPULATION_SIZE, n_corrupt, budget)
            rows.append({
                "corrupt_fraction": n_corrupt / POPULATION_SIZE,
                "corrupt_clients": n_corrupt,
                "max_forge_probability": budget,
                "smallest_committee": size if size is not None else "",
                "achievable": size is not None,
            })
    return rows


# ---------------------------------------------------------------------------
# E-3c -- rotating vs fixed committee
# ---------------------------------------------------------------------------

def run_e3c(sizes: Sequence[int], corrupt_counts: Sequence[int],
            rounds: int, trials: int) -> List[dict]:
    """Does rotation help? Two metrics, because they disagree.

    * ``P(at least one forged round)`` -- rotation gives the adversary many
      independent chances, so this gets WORSE with rotation.
    * ``expected fraction of rounds forged`` -- a captured fixed committee owns
      every round, so the worst case is far worse without rotation.

    Reporting only one of these would misrepresent the design.
    """
    rows = []
    for size in sizes:
        thr = threshold_for(size)
        for n_corrupt in corrupt_counts:
            bad = corrupt_set(n_corrupt)
            p_single = corruption_probability(POPULATION_SIZE, n_corrupt, size, thr)

            rot_any = 0
            rot_frac_total = 0.0
            fixed_any = 0
            fixed_frac_total = 0.0
            for t in range(trials):
                # Rotating: an independent draw each round.
                forged = 0
                for r in range(rounds):
                    committee = select_committee(ROOT, t * rounds + r, POPULATION, size)
                    if sum(1 for c in committee if c in bad) >= thr:
                        forged += 1
                rot_any += 1 if forged else 0
                rot_frac_total += forged / rounds

                # Fixed: drawn once, then used for every round.
                committee = select_committee(ROOT, 10_000_000 + t, POPULATION, size)
                captured = sum(1 for c in committee if c in bad) >= thr
                fixed_any += 1 if captured else 0
                fixed_frac_total += 1.0 if captured else 0.0

            rows.append({
                "committee_size": size, "threshold": thr,
                "corrupt_clients": n_corrupt,
                "corrupt_fraction": n_corrupt / POPULATION_SIZE,
                "rounds": rounds,
                "p_forge_single_round": p_single,
                "rotating_p_any_round_forged": rot_any / trials,
                "rotating_mean_fraction_forged": rot_frac_total / trials,
                "fixed_p_any_round_forged": fixed_any / trials,
                "fixed_mean_fraction_forged": fixed_frac_total / trials,
                "trials": trials,
            })
    return rows


# ---------------------------------------------------------------------------
# E-3d -- grinding: violating assumption A1 on purpose
# ---------------------------------------------------------------------------

def run_e3d(sizes: Sequence[int], corrupt_counts: Sequence[int],
            grind_budgets: Sequence[int], trials: int) -> List[dict]:
    """What if the adversary can *search* for a favourable committee?

    Our sortition is recomputable and history-bound but is **not a VRF**: the seed is
    the previous transcript root, and an aggregator with any freedom over what enters
    the transcript (entry ordering, a nonce, timing) can try several candidate roots
    and keep whichever yields the most corrupt committee.

    This models that directly: with G candidate seeds, the adversary takes the best.
    Every such attempt changes the transcript and is therefore *visible* -- but
    visible is not the same as prevented, and if a modest G materially raises the
    forge probability then committee sizes chosen from the E-3b curve are optimistic.
    """
    rows = []
    print(f"{'m':>4} {'corrupt':>8} {'G=1':>9} " +
          " ".join(f"{'G=' + str(g):>9}" for g in grind_budgets[1:]))
    for size in sizes:
        thr = threshold_for(size)
        for n_corrupt in corrupt_counts:
            bad = corrupt_set(n_corrupt)
            per_budget: Dict[int, float] = {}
            for g in grind_budgets:
                hits = 0
                for t in range(trials):
                    base = t * max(grind_budgets) * 2
                    best = 0
                    for attempt in range(g):
                        committee = select_committee(ROOT, base + attempt, POPULATION, size)
                        best = max(best, sum(1 for c in committee if c in bad))
                        if best >= thr:
                            break
                    if best >= thr:
                        hits += 1
                per_budget[g] = hits / trials
            baseline = per_budget[grind_budgets[0]]
            for g, p in per_budget.items():
                rows.append({
                    "committee_size": size, "threshold": thr,
                    "corrupt_clients": n_corrupt,
                    "corrupt_fraction": n_corrupt / POPULATION_SIZE,
                    "grind_attempts": g, "forge_probability": p,
                    "amplification_vs_no_grinding": (p / baseline) if baseline > 0 else None,
                    "trials": trials,
                })
            cells = " ".join(f"{per_budget[g]:>9.4f}" for g in grind_budgets)
            print(f"{size:>4} {n_corrupt:>8} {cells}")
    return rows


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="E-3: committee corruption")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    if args.quick:
        sizes_a = [5, 9]
        corrupt_a = [5, 10, 20]
        trials_a = 3000
        sizes_c, trials_c, rounds_c = [5, 9], 300, 30
        sizes_d, corrupt_d, grind_d, trials_d = [5, 9], [10, 20], [1, 8, 64], 400
    else:
        sizes_a = [3, 5, 7, 9, 11, 15]
        corrupt_a = [5, 10, 15, 20, 25]
        trials_a = 20_000
        sizes_c, trials_c, rounds_c = [5, 9, 15], 1000, 50
        sizes_d, corrupt_d, grind_d, trials_d = [5, 9, 15], [10, 15, 20], [1, 4, 16, 64, 256], 1000

    fractions = [0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    sizes_b = [1, 3, 5, 7, 9, 11, 15, 21]

    print(f"E-3 committee corruption   population={POPULATION_SIZE}  "
          f"threshold rule = ceil(2m/3)   quick={args.quick}\n")

    print("[E-3a] empirical sortition vs hypergeometric model")
    rows_a = run_e3a(sizes_a, corrupt_a, trials_a)
    worst = max(rows_a, key=lambda r: r["abs_difference"])
    n_ok = sum(1 for r in rows_a if r["within_3_sigma"])
    print(f"  -> {n_ok}/{len(rows_a)} cells within 3 sigma; "
          f"largest deviation {worst['abs_difference']:.4f}\n")

    print("[E-3b] forge probability across the design space (analytic)")
    rows_b = run_e3b(sizes_b, fractions)
    rows_b_sizing = run_e3b_sizing(fractions, [0.05, 0.01, 1e-3, 1e-6])
    for f in (0.10, 0.20, 0.30):
        n_c = round(f * POPULATION_SIZE)
        line = "  ".join(
            f"m={m}:{corruption_probability(POPULATION_SIZE, n_c, m, threshold_for(m)):.2e}"
            for m in (1, 5, 9, 15)
        )
        print(f"  corrupt {f:.0%}   {line}")
    print()

    print("[E-3c] rotating vs fixed committee")
    rows_c = run_e3c(sizes_c, [10, 20], rounds_c, trials_c)
    for r in rows_c:
        print(f"  m={r['committee_size']:>2} corrupt={r['corrupt_fraction']:.0%}  "
              f"P(any round forged): rotating {r['rotating_p_any_round_forged']:.3f} "
              f"vs fixed {r['fixed_p_any_round_forged']:.3f}   |  "
              f"mean fraction forged: rotating {r['rotating_mean_fraction_forged']:.3f} "
              f"vs fixed {r['fixed_mean_fraction_forged']:.3f}")
    print()

    print("[E-3d] grinding on the sortition seed (violates assumption A1)")
    rows_d = run_e3d(sizes_d, corrupt_d, grind_d, trials_d)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = REPO_ROOT / "results" / "runs" / f"e3_{stamp}"
    summary_dir = REPO_ROOT / "results" / "summary"
    datasets = {
        "e3a_model_validation": rows_a,
        "e3b_forge_probability": rows_b,
        "e3b_committee_sizing": rows_b_sizing,
        "e3c_rotation": rows_c,
        "e3d_grinding": rows_d,
    }
    for name, rows in datasets.items():
        write_csv(out_dir / f"{name}.csv", rows)
        write_csv(summary_dir / f"{name}.csv", rows)

    manifest = Manifest(
        experiment_id=EXPERIMENT_ID,
        description="Committee corruption: model validation, design curve, rotation, and grinding.",
        parameters={
            "population": POPULATION_SIZE, "threshold_rule": "ceil(2m/3)",
            "sizes_a": sizes_a, "corrupt_a": corrupt_a, "trials_a": trials_a,
            "sizes_b": sizes_b, "fractions_b": fractions,
            "sizes_c": sizes_c, "rounds_c": rounds_c, "trials_c": trials_c,
            "sizes_d": sizes_d, "grind_budgets": grind_d, "trials_d": trials_d,
            "quick": args.quick,
        },
        seeds={"sortition_root_hex_prefix": 0x5E},
    )
    for text in (
        "A1 seed not adversarially chosen -- DELIBERATELY VIOLATED in E-3d.",
        "A2 static corruption: the corrupt set is fixed before selection. An ADAPTIVE "
        "adversary who bribes members after seeing the committee defeats any size.",
        "A3 uniform sampling without replacement -- this is why the count is hypergeometric.",
        "A4 every corrupt member selected signs; honest members never sign a false set.",
        "A5 no Sybil identities. The SoK states AG1 gives no Sybil resistance without "
        "external trust anchors; inflating the corrupt fraction with fake identities is "
        "strictly easier than any attack modelled here.",
        "A6 committee membership is observable to the adversary.",
        "Committee size 1 in E-3b is baseline B2 (self-attestation).",
        f"E-3a used the REAL select_committee implementation, not an idealised sampler; "
        f"{n_ok}/{len(rows_a)} cells fell within 3 sigma.",
    ):
        manifest.note(text)
    manifest.finish()
    manifest.save(out_dir)

    print(f"\nResults: {out_dir}")
    for warning in manifest.warnings():
        print(f"  WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
