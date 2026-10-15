"""Confirmatory experiment for the G2 second-generation admission rule.

Executes the matrix pre-registered in ``G2_PREREGISTRATION.md``. Hypotheses,
thresholds, attacks and success criteria were fixed BEFORE this ran.

**The G1 results in ``results/E4_E5_FINDINGS.md`` are unchanged.** G2 is a separate
second-generation ablation, not a replacement.

Four systems (pre-registration section 7.1):
    S0   no admission rule (plain FedAvg)
    S1   G1, original rule, trusted server
    S1b  G2, improved rule, trusted server
    S3   G2 + full committee-backed verifiable mechanism

Usage:
    .venv/Scripts/python.exe scripts/exp_g2.py [--quick] [--workers N]
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
    System,
    run_federated,
)
from bcflsrv.fl.model import TrainConfig  # noqa: E402

EXPERIMENT_ID = "G2"
N_CLIENTS, CLIENTS_PER_ROUND, ALPHA = 30, 10, 0.5
LEVEL = DisclosureLevel.E3  # G2 needs the sketch; G1 is evaluated on the same rung

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


def _run_one(config: RunConfig) -> Dict[str, object]:
    if _DATASET is None:
        _worker_init()
    return run_federated(_DATASET, _SHARDS, config).as_row()


# (label, system, rule) -- the four systems the comparison requires
SYSTEMS = [
    ("S0", System.S0_PLAIN, RuleGeneration.G1),      # rule unused when S0
    ("S1", System.S1_RULE_ONLY, RuleGeneration.G1),
    ("S1b", System.S1_RULE_ONLY, RuleGeneration.G2),
    ("S3", System.S2_FULL, RuleGeneration.G2),
]

MAIN_ATTACKS = [
    AttackType.NONE, AttackType.SIGN_FLIP, AttackType.LABEL_FLIP,
    AttackType.SCALED, AttackType.NOISE, AttackType.TARGETED, AttackType.SLOW_DRIFT,
]


def build_matrix(quick: bool) -> List[RunConfig]:
    seeds = [0, 1, 2] if quick else [0, 1, 2]
    head_seeds = [0, 1, 2] if quick else [0, 1, 2, 3, 4]
    rounds = 8 if quick else 25
    base = dict(
        n_clients=N_CLIENTS, clients_per_round=CLIENTS_PER_ROUND, rounds=rounds,
        train=TrainConfig(max_batches=12), level=LEVEL,
    )
    configs: List[RunConfig] = []

    # --- Main comparison: 4 systems x 7 attacks, 20% malicious ---
    for _, system, rule in SYSTEMS:
        for attack in MAIN_ATTACKS:
            frac = 0.0 if attack is AttackType.NONE else 0.2
            for seed in seeds:
                configs.append(RunConfig(
                    system=system, rule=rule,
                    attack=AttackConfig(attack=attack, beta=0.9),
                    malicious_fraction=frac, seed=seed, **base,
                ))

    # --- Malicious-fraction sweep on the two hardest attacks ---
    for _, system, rule in SYSTEMS:
        for attack in (AttackType.SLOW_DRIFT, AttackType.LABEL_FLIP):
            for frac in (0.1, 0.3):
                for seed in seeds:
                    configs.append(RunConfig(
                        system=system, rule=rule,
                        attack=AttackConfig(attack=attack, beta=0.9),
                        malicious_fraction=frac, seed=seed, **base,
                    ))

    # --- HEADLINE: slow-drift beta sweep, G1 vs G2 ---
    for rule in (RuleGeneration.G1, RuleGeneration.G2):
        for beta in (0.25, 0.5, 0.75, 0.9, 1.1, 1.5):
            for seed in head_seeds:
                configs.append(RunConfig(
                    system=System.S1_RULE_ONLY, rule=rule,
                    attack=AttackConfig(attack=AttackType.SLOW_DRIFT, beta=beta),
                    malicious_fraction=0.2, seed=seed, **base,
                ))

    # --- HEADLINE: adaptive attacker gamma sweep vs G2 (evasion/damage curve) ---
    for gamma in (0.0, 0.25, 0.5, 0.75, 1.0):
        for seed in head_seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=RuleGeneration.G2,
                attack=AttackConfig(attack=AttackType.ADAPTIVE, beta=0.9, gamma=gamma),
                malicious_fraction=0.2, seed=seed, **base,
            ))

    # --- A8 null-space: does commit-then-sketch actually help? ---
    for cts in (False, True):
        for seed in seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=RuleGeneration.G2,
                commit_then_sketch=cts,
                attack=AttackConfig(attack=AttackType.NULLSPACE),
                malicious_fraction=0.2, seed=seed, **base,
            ))

    # --- Warm-up ablation: is accumulation really what does the work? (G2-P3) ---
    for warmup in (1, 2, 3, 5):
        for seed in seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, rule=RuleGeneration.G2, warmup=warmup,
                attack=AttackConfig(attack=AttackType.SLOW_DRIFT, beta=0.9),
                malicious_fraction=0.2, seed=seed, **base,
            ))

    return configs


def main() -> int:
    ap = argparse.ArgumentParser(description="G2 confirmatory experiment")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, min(3, (os.cpu_count() or 4) // 3)))
    args = ap.parse_args()

    configs = build_matrix(args.quick)
    print(f"G2 confirmatory: {len(configs)} runs, {args.workers} workers, "
          f"rounds={configs[0].rounds}", flush=True)

    started = time.perf_counter()
    rows: List[Dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as pool:
        for i, row in enumerate(pool.map(_run_one, configs), 1):
            rows.append(row)
            if i % 15 == 0 or i == len(configs):
                elapsed = time.perf_counter() - started
                print(f"  {i:>3}/{len(configs)}  elapsed {elapsed/60:5.1f}m  "
                      f"eta {(len(configs)-i)*(elapsed/i)/60:5.1f}m", flush=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = REPO_ROOT / "results" / "runs" / f"g2_{stamp}"
    summary_dir = REPO_ROOT / "results" / "summary"
    for directory in (out_dir, summary_dir):
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "g2_runs.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    manifest = Manifest(
        experiment_id=EXPERIMENT_ID,
        description="G2 second-generation admission rule, confirmatory run against pre-registered hypotheses.",
        parameters={
            "n_clients": N_CLIENTS, "clients_per_round": CLIENTS_PER_ROUND,
            "dirichlet_alpha": ALPHA, "rounds": configs[0].rounds,
            "disclosure_level": LEVEL.value, "n_runs": len(configs),
        },
        seeds={"partition_seed": 0},
    )
    for note in (
        "Hypotheses and success criteria were pre-registered in G2_PREREGISTRATION.md "
        "BEFORE this run. No threshold, attacker or seed was adjusted afterwards.",
        "The G1 results in results/E4_E5_FINDINGS.md are UNCHANGED by this experiment.",
        "G2 is NOT claimed as a novel defence -- a prior-art check returned "
        "KNOWN-IN-PARTS. What is distinctive is that the reputation is carried by an "
        "auditable transcript across stateless rotating committees.",
        "Attack A7 has ORACLE access to the honest consensus direction and to the "
        "threshold. Attack A8 is a published null-space evasion. Neither was weakened.",
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
