"""Confirmatory experiment for the G3 separation-aware admission rule.

Executes the matrix pre-registered in ``G3_PREREGISTRATION.md`` section 7. Every
hypothesis, threshold, attack and success criterion was fixed and committed BEFORE
this ran.

**The G1 and G2 results are unchanged.** ``results/E4_E5_FINDINGS.md`` and
``results/G2_FINDINGS.md`` are frozen; G3 is a third-generation ablation reported
beside them, never in place of them.

Seed discipline: design used development seeds 100-104 (``scripts/diag_g3.py``); this
runs on held-out confirmatory seeds 0-4.

Usage:
    .venv/Scripts/python.exe scripts/exp_g3.py [--quick] [--workers N]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from bcflsrv.bench.manifest import Manifest  # noqa: E402
from bcflsrv.fl.attacks import AttackConfig, AttackType  # noqa: E402
from bcflsrv.fl.evidence import DisclosureLevel  # noqa: E402
from bcflsrv.fl.experiment import (  # noqa: E402
    RuleGeneration,
    RunConfig,
    RunResult,
    System,
    run_federated,
)
from bcflsrv.fl.model import TrainConfig  # noqa: E402

EXPERIMENT_ID = "G3"
N_CLIENTS, CLIENTS_PER_ROUND, ALPHA = 30, 10, 0.5
LEVEL = DisclosureLevel.E3

_DATASET = None
_SHARDS = None


def _worker_init() -> None:
    global _DATASET, _SHARDS
    import torch

    torch.set_num_threads(2)
    from bcflsrv.fl.data import dirichlet_partition, load_fashion_mnist

    _DATASET = load_fashion_mnist()
    ids = [f"client-{i:03d}" for i in range(N_CLIENTS)]
    _SHARDS = dirichlet_partition(_DATASET.y_train, ids, alpha=ALPHA, seed=0)


# Columns that together identify a configuration uniquely. Used to resume a run
# that was interrupted: a 160-minute experiment must not have to start over.
KEY_COLUMNS = [
    "system", "rule", "warmup", "commit_then_sketch", "disclosure", "attack",
    "beta", "gamma", "malicious_fraction", "seed", "rounds", "n_clients",
    "clients_per_round", "g3_population", "g3_accumulate", "g3_two_sided",
    "g3_gap_min",
]


def _key(row: Dict[str, object]) -> str:
    """Canonical identity of one matrix cell, stable across CSV round-trips."""
    parts = []
    for column in KEY_COLUMNS:
        value = row[column]
        if isinstance(value, bool):
            parts.append("1" if value else "0")
        elif isinstance(value, str) and value in ("True", "False"):
            parts.append("1" if value == "True" else "0")
        else:
            try:
                parts.append(f"{float(value):.6g}")
            except (TypeError, ValueError):
                parts.append(str(value))
    return "|".join(parts)


def _run_one(config: RunConfig) -> Dict[str, object]:
    if _DATASET is None:
        _worker_init()
    return run_federated(_DATASET, _SHARDS, config).as_row()


# The five arms of the comparison (pre-registration section 7).
ARMS = [
    (System.S0_PLAIN, RuleGeneration.G1),      # S0  -- rule unused
    (System.S1_RULE_ONLY, RuleGeneration.G1),  # S1  -- original rule, frozen result
    (System.S1_RULE_ONLY, RuleGeneration.G2),  # S1b -- second generation, frozen result
    (System.S1_RULE_ONLY, RuleGeneration.G3),  # S1c -- third generation, under test
    (System.S2_FULL, RuleGeneration.G3),       # S3  -- G3 + full verifiable mechanism
]

MAIN_ATTACKS = [
    AttackType.NONE, AttackType.SIGN_FLIP, AttackType.LABEL_FLIP,
    AttackType.SCALED, AttackType.NOISE, AttackType.TARGETED, AttackType.SLOW_DRIFT,
]


def build_matrix(quick: bool) -> List[RunConfig]:
    seeds = [0, 1, 2]
    head_seeds = [0, 1, 2] if quick else [0, 1, 2, 3, 4]
    rounds = 8 if quick else 25
    base = dict(
        n_clients=N_CLIENTS, clients_per_round=CLIENTS_PER_ROUND, rounds=rounds,
        train=TrainConfig(max_batches=12), level=LEVEL,
    )
    drift = AttackConfig(attack=AttackType.SLOW_DRIFT, beta=0.9)
    configs: List[RunConfig] = []

    # --- X1: main comparison, 5 arms x 7 attacks -----------------------------
    for system, rule in ARMS:
        for attack in MAIN_ATTACKS:
            frac = 0.0 if attack is AttackType.NONE else 0.2
            for seed in seeds:
                configs.append(RunConfig(
                    system=system, rule=rule,
                    attack=AttackConfig(attack=attack, beta=0.9),
                    malicious_fraction=frac, seed=seed, **base,
                ))

    # --- X2: HEADLINE slow-drift beta sweep, all three rule generations ------
    # G1 and G2 are re-run rather than quoted, so the comparison is like-for-like
    # in one file AND the frozen numbers get an independent reproduction check.
    for rule in (RuleGeneration.G1, RuleGeneration.G2, RuleGeneration.G3):
        for beta in (0.25, 0.5, 0.75, 0.9, 1.1, 1.5):
            for seed in head_seeds:
                configs.append(RunConfig(
                    system=System.S1_RULE_ONLY, rule=rule,
                    attack=AttackConfig(attack=AttackType.SLOW_DRIFT, beta=beta),
                    malicious_fraction=0.2, seed=seed, **base,
                ))

    # --- X3: is the SKETCH the bottleneck? E3 vs full plaintext E4 -----------
    for level in (DisclosureLevel.E3, DisclosureLevel.E4):
        for seed in head_seeds:
            cfg = dict(base); cfg["level"] = level
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=RuleGeneration.G3,
                attack=drift, malicious_fraction=0.2, seed=seed, **cfg,
            ))

    # --- X4: is the SINGLE-ROUND setting the bottleneck? --------------------
    for accumulate in (True, False):
        for seed in head_seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=RuleGeneration.G3,
                g3_accumulate=accumulate, attack=drift,
                malicious_fraction=0.2, seed=seed, **base,
            ))

    # --- X5: does the ledger's cross-client population view earn its place? --
    for population in (True, False):
        for seed in head_seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=RuleGeneration.G3,
                g3_population=population, attack=drift,
                malicious_fraction=0.2, seed=seed, **base,
            ))

    # --- X6: gap gate -- re-test the calibration on held-out seeds (G3-P10) --
    for gap_min in (0.0, 0.35):
        for attack in (AttackType.NONE, AttackType.SLOW_DRIFT):
            frac = 0.0 if attack is AttackType.NONE else 0.2
            for seed in head_seeds:
                configs.append(RunConfig(
                    system=System.S1_RULE_ONLY, rule=RuleGeneration.G3,
                    g3_gap_min=gap_min,
                    attack=AttackConfig(attack=attack, beta=0.9),
                    malicious_fraction=frac, seed=seed, **base,
                ))

    # --- X7: adaptive attacker gamma sweep vs G3 (evasion/damage curve) -----
    for gamma in (0.0, 0.25, 0.5, 0.75, 1.0):
        for seed in head_seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=RuleGeneration.G3,
                attack=AttackConfig(attack=AttackType.ADAPTIVE, beta=0.9, gamma=gamma),
                malicious_fraction=0.2, seed=seed, **base,
            ))

    # --- X8: two-sided ablation -- is the adaptive gap fixable BY THE RULE? --
    for attack, frac in (
        (AttackType.NONE, 0.0),
        (AttackType.ADAPTIVE, 0.2),
        (AttackType.SLOW_DRIFT, 0.2),
    ):
        for seed in head_seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=RuleGeneration.G3, g3_two_sided=True,
                attack=AttackConfig(attack=attack, beta=0.9, gamma=0.5),
                malicious_fraction=frac, seed=seed, **base,
            ))

    # --- X9: A9 camouflage -- can our own defence be beaten? ----------------
    for rule in (RuleGeneration.G1, RuleGeneration.G2, RuleGeneration.G3):
        for seed in head_seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=rule,
                attack=AttackConfig(attack=AttackType.CAMOUFLAGE, beta=0.9),
                malicious_fraction=0.2, seed=seed, **base,
            ))

    # --- X10: does the minority bound hold at its edge? ---------------------
    for frac in (0.1, 0.3):
        for attack in (AttackType.SLOW_DRIFT, AttackType.LABEL_FLIP):
            for seed in seeds:
                configs.append(RunConfig(
                    system=System.S1_RULE_ONLY, rule=RuleGeneration.G3,
                    attack=AttackConfig(attack=attack, beta=0.9),
                    malicious_fraction=frac, seed=seed, **base,
                ))

    return configs


def main() -> int:
    ap = argparse.ArgumentParser(description="G3 confirmatory experiment")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, min(5, (os.cpu_count() or 4) // 2)))
    ap.add_argument("--resume", action="store_true",
                    help="skip configurations already present in the summary CSV")
    args = ap.parse_args()

    configs = build_matrix(args.quick)
    # Several experiments share a control arm, so the matrix names the same
    # configuration more than once. Under deterministic seeding a repeat execution is
    # provably byte-identical, so executing it twice buys nothing. Coverage is
    # unchanged; only redundant executions are dropped.
    seen_keys = set()
    deduped: List[RunConfig] = []
    for c in configs:
        key = _key(RunResult(config=c).as_row())
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(c)
    if len(deduped) != len(configs):
        print(f"matrix names {len(configs)} cells over {len(deduped)} distinct "
              f"configurations; {len(configs) - len(deduped)} are repeated control arms",
              flush=True)
    configs = deduped
    done_rows: List[Dict[str, object]] = []
    if args.resume:
        existing = REPO_ROOT / "results" / "summary" / "g3_runs.csv"
        if existing.exists():
            with existing.open(encoding="utf-8") as fh:
                done_rows = list(csv.DictReader(fh))
            done = {_key(row) for row in done_rows}
            before = len(configs)
            configs = [c for c in configs if _key(RunResult(config=c).as_row()) not in done]
            print(f"resume: {len(done_rows)} runs already recorded, "
                  f"{before - len(configs)} matched, {len(configs)} remaining", flush=True)
            if not configs:
                print("nothing left to run", flush=True)
                return 0
    print(f"G3 confirmatory: {len(configs)} runs, {args.workers} workers, "
          f"rounds={configs[0].rounds}", flush=True)

    started = time.perf_counter()
    rows: List[Dict[str, object]] = list(done_rows)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = REPO_ROOT / "results" / "runs" / f"g3_{stamp}"
    summary_dir = REPO_ROOT / "results" / "summary"
    for directory in (out_dir, summary_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as pool:
        for i, row in enumerate(pool.map(_run_one, configs), 1):
            rows.append(row)
            _ = i
            if i % 15 == 0 or i == len(configs):
                elapsed = time.perf_counter() - started
                print(f"  {i:>3}/{len(configs)}  elapsed {elapsed/60:5.1f}m  "
                      f"eta {(len(configs)-i)*(elapsed/i)/60:5.1f}m", flush=True)
                # Written incrementally: a run this long must survive interruption.
                for directory in (out_dir, summary_dir):
                    with (directory / "g3_runs.csv").open("w", newline="", encoding="utf-8") as fh:
                        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(rows)

    manifest = Manifest(
        experiment_id=EXPERIMENT_ID,
        description="G3 separation-aware admission rule, confirmatory run against pre-registered hypotheses.",
        parameters={
            "n_clients": N_CLIENTS, "clients_per_round": CLIENTS_PER_ROUND,
            "dirichlet_alpha": ALPHA, "rounds": configs[0].rounds,
            "disclosure_level": LEVEL.value, "n_runs": len(configs),
        },
        seeds={"partition_seed": 0, "dev_seeds": "100-104", "confirmatory_seeds": "0-4"},
    )
    for note in (
        "Hypotheses, thresholds and A/B/C criteria were pre-registered in "
        "G3_PREREGISTRATION.md and COMMITTED BEFORE this run. Nothing was adjusted after.",
        "The G1 and G2 results in results/E4_E5_FINDINGS.md and results/G2_FINDINGS.md "
        "are UNCHANGED. G3 is reported beside them, never in place of them.",
        "Design used development seeds 100-104 only; this runs on held-out seeds 0-4.",
        "G3 is NOT claimed as novel. Prior-art check returned KNOWN: Auror, FLAME and "
        "FLDetector-style defences already cluster clients, and Otsu has been applied "
        "to malicious-client detection in FL. Otsu is chosen here for auditor "
        "recomputability, a systems requirement, not for better detection.",
        "G3 introduces no new calibrated constant: the gap gate calibrated to zero, the "
        "warm-up is G2's, and the minority bound is the committee's own f < n/3.",
        "Attacks A4/A7 keep ORACLE knowledge of the threshold and consensus direction. "
        "A9 is a NEW attack designed specifically to defeat G3. None was weakened.",
        "Fashion-MNIST is a controlled environment, not evidence about production FL.",
    ):
        manifest.note(note)
    manifest.finish()
    manifest.save(out_dir)

    print(f"\nTotal {(time.perf_counter()-started)/60:.1f} min -> {out_dir}", flush=True)
    for warning in manifest.warnings():
        print(f"  WARNING: {warning}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
