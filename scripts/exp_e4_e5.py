"""Experiments E-4 and E-5: does the mechanism provide useful security in FL?

Executes the matrix in ``E4_E5_MATRIX.md``. E-1/E-2/E-3 established properties of the
*record*; these establish whether the *rule* being recorded is worth recording.

Sub-claims under test:
  **C4** -- more disclosure to the committee buys more detection power (E-4)
  **C5** -- verifiable admission stops a slow-drift attacker (E-5)

C5 is pre-registered as **predicted FALSE**. The attacker is given oracle knowledge of
the rule's threshold and will not be weakened.

Runs are deduplicated across matrix rows: one set of configurations serves several
tables. Multiple seeds per cell; results are reported mean +/- std.

Usage:
    .venv/Scripts/python.exe scripts/exp_e4_e5.py [--quick] [--workers N]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from bcflsrv.bench.manifest import Manifest  # noqa: E402
from bcflsrv.fl.attacks import AttackConfig, AttackType  # noqa: E402
from bcflsrv.fl.evidence import DisclosureLevel  # noqa: E402
from bcflsrv.fl.experiment import RunConfig, RunResult, System, run_federated  # noqa: E402
from bcflsrv.fl.model import TrainConfig  # noqa: E402

EXPERIMENT_ID = "E-4/E-5"
N_CLIENTS = 30
CLIENTS_PER_ROUND = 10
ALPHA = 0.5

_DATASET = None
_SHARDS = None


def _worker_init(rounds: int) -> None:
    """Load the dataset once per worker process (spawn-safe on Windows)."""
    global _DATASET, _SHARDS
    import torch

    torch.set_num_threads(2)  # several runs share the machine
    from bcflsrv.fl.data import dirichlet_partition, load_fashion_mnist

    _DATASET = load_fashion_mnist()
    ids = [f"client-{i:03d}" for i in range(N_CLIENTS)]
    _SHARDS = dirichlet_partition(_DATASET.y_train, ids, alpha=ALPHA, seed=0)


def _run_one(config: RunConfig) -> Dict[str, object]:
    if _DATASET is None or _SHARDS is None:
        _worker_init(config.rounds)
    return run_federated(_DATASET, _SHARDS, config).as_row()


def build_matrix(quick: bool) -> List[RunConfig]:
    """The deduplicated configuration set covering every matrix row."""
    seeds = [0, 1, 2] if quick else [0, 1, 2, 3, 4]
    sweep_seeds = seeds[:3]
    rounds = 8 if quick else 25
    train = TrainConfig(max_batches=12)
    base = dict(
        n_clients=N_CLIENTS, clients_per_round=CLIENTS_PER_ROUND,
        rounds=rounds, train=train,
    )
    configs: List[RunConfig] = []

    # --- E4.1 + E4.2: disclosure ladder x attacks (incl. no-attack FPR floor) ---
    for level in DisclosureLevel:
        for attack in (AttackType.NONE, AttackType.SIGN_FLIP,
                       AttackType.LABEL_FLIP, AttackType.SCALED):
            frac = 0.0 if attack is AttackType.NONE else 0.2
            for seed in sweep_seeds:
                configs.append(RunConfig(
                    system=System.S1_RULE_ONLY, level=level,
                    attack=AttackConfig(attack=attack),
                    malicious_fraction=frac, seed=seed, **base,
                ))

    # --- E4.3: S0 / S2 at E2 -- S1 already covered above (the S1 == S2 check) ---
    for system in (System.S0_PLAIN, System.S2_FULL):
        for attack in (AttackType.NONE, AttackType.SIGN_FLIP,
                       AttackType.LABEL_FLIP, AttackType.SCALED):
            frac = 0.0 if attack is AttackType.NONE else 0.2
            for seed in sweep_seeds:
                configs.append(RunConfig(
                    system=system, level=DisclosureLevel.E2,
                    attack=AttackConfig(attack=attack),
                    malicious_fraction=frac, seed=seed, **base,
                ))

    # --- E5.1 + E5.4: the falsification curve, beta sweep at E2 ---
    for beta in (0.25, 0.5, 0.75, 0.9, 1.1, 1.5):
        for seed in seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, level=DisclosureLevel.E2,
                attack=AttackConfig(attack=AttackType.SLOW_DRIFT, beta=beta),
                malicious_fraction=0.2, seed=seed, **base,
            ))

    # --- E5.2: damage vs malicious fraction ---
    for system in (System.S0_PLAIN, System.S1_RULE_ONLY):
        for beta in (0.5, 0.9):
            for frac in (0.1, 0.2, 0.3):
                for seed in sweep_seeds:
                    configs.append(RunConfig(
                        system=system, level=DisclosureLevel.E2,
                        attack=AttackConfig(attack=AttackType.SLOW_DRIFT, beta=beta),
                        malicious_fraction=frac, seed=seed, **base,
                    ))

    # --- E5.3: can ANY disclosure level catch slow drift? ---
    for level in (DisclosureLevel.E1, DisclosureLevel.E3, DisclosureLevel.E4):
        for seed in sweep_seeds:
            configs.append(RunConfig(
                system=System.S1_RULE_ONLY, level=level,
                attack=AttackConfig(attack=AttackType.SLOW_DRIFT, beta=0.9),
                malicious_fraction=0.2, seed=seed, **base,
            ))

    return configs


def main() -> int:
    parser = argparse.ArgumentParser(description="E-4/E-5")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 4) // 3)))
    args = parser.parse_args()

    configs = build_matrix(args.quick)
    print(f"E-4/E-5: {len(configs)} runs, {args.workers} workers, "
          f"rounds={configs[0].rounds}, quick={args.quick}", flush=True)

    started = time.perf_counter()
    rows: List[Dict[str, object]] = []
    with ProcessPoolExecutor(
        max_workers=args.workers, initializer=_worker_init, initargs=(configs[0].rounds,)
    ) as pool:
        for i, row in enumerate(pool.map(_run_one, configs), 1):
            rows.append(row)
            if i % 10 == 0 or i == len(configs):
                elapsed = time.perf_counter() - started
                rate = elapsed / i
                print(f"  {i:>3}/{len(configs)}  elapsed {elapsed/60:5.1f}m  "
                      f"eta {(len(configs)-i)*rate/60:5.1f}m", flush=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = REPO_ROOT / "results" / "runs" / f"e4e5_{stamp}"
    summary_dir = REPO_ROOT / "results" / "summary"
    for directory in (out_dir, summary_dir):
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "e4e5_runs.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    manifest = Manifest(
        experiment_id=EXPERIMENT_ID,
        description="E-4 disclosure ladder and E-5 slow-drift falsification on Fashion-MNIST.",
        parameters={
            "n_clients": N_CLIENTS, "clients_per_round": CLIENTS_PER_ROUND,
            "dirichlet_alpha": ALPHA, "rounds": configs[0].rounds,
            "n_runs": len(configs), "quick": args.quick, "workers": args.workers,
        },
        seeds={"partition_seed": 0},
    )
    for note in (
        "Fashion-MNIST is a CONTROLLED EXPERIMENTAL ENVIRONMENT. Nothing here is "
        "evidence about production federated learning.",
        "Masking is SIMPLIFIED ADDITIVE MASKING with no dropout recovery -- not "
        "production secure aggregation. It provides statistical, not information-"
        "theoretic, hiding.",
        "Admission thresholds were calibrated on the ATTACK-FREE condition to ~5% "
        "false positives and then frozen for all attack runs.",
        "The slow-drift attacker is given ORACLE knowledge of the rule's threshold. "
        "It was not weakened at any point.",
        "S1 and S2 are expected to produce identical ML metrics (prediction P1); they "
        "differ only in overhead.",
    ):
        manifest.note(note)
    manifest.finish()
    manifest.save(out_dir)

    print(f"\nTotal {(time.perf_counter()-started)/60:.1f} min -> {out_dir}")
    for warning in manifest.warnings():
        print(f"  WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
