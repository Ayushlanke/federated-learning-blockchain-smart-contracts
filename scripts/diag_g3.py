"""EXPLORATORY diagnostic -- is the G2 bottleneck really the cutoff?

**This is not a confirmatory experiment and no result here is reported as evidence
for or against any hypothesis.** Its only jobs are:

1. Test the mechanism claim in ``G2_FINDINGS.md`` s3 -- that the reputation
   population separates but ``median - 3*MAD`` fails to convert that separation into
   rejections -- by measuring the mode gap in MAD units directly.
2. Calibrate the G3 gate **on the attack-free condition only**, to a target stated in
   advance: the gate must fire on no more than 5% of attack-free rounds.

Seed discipline: this runs on **development seeds 100-104**. The confirmatory
experiment runs on **held-out seeds 0-4**. No confirmatory seed is touched here.

Usage:
    .venv/Scripts/python.exe scripts/diag_g3.py [--workers N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from bcflsrv.fl.attacks import AttackConfig, AttackType, select_malicious  # noqa: E402
from bcflsrv.fl.evidence import DisclosureLevel  # noqa: E402
from bcflsrv.fl.experiment import RuleGeneration, RunConfig, System, run_federated  # noqa: E402
from bcflsrv.fl.model import TrainConfig  # noqa: E402
from bcflsrv.fl.separation import otsu_split  # noqa: E402

DEV_SEEDS = [100, 101, 102, 103, 104]
N_CLIENTS, CLIENTS_PER_ROUND, ALPHA = 30, 10, 0.5
MAD_FACTOR = 3.0

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


def _auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """P(a random honest score > a random malicious score). 1.0 = perfect ranking."""
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    wins = (neg[:, None] < pos[None, :]).sum() + 0.5 * (neg[:, None] == pos[None, :]).sum()
    return float(wins / (pos.size * neg.size))


def _run_one(spec) -> List[Dict[str, object]]:
    if _DATASET is None:
        _worker_init()
    label, attack_cfg, frac, seed = spec
    config = RunConfig(
        system=System.S1_RULE_ONLY, rule=RuleGeneration.G2, level=DisclosureLevel.E3,
        attack=attack_cfg, malicious_fraction=frac, seed=seed,
        n_clients=N_CLIENTS, clients_per_round=CLIENTS_PER_ROUND, rounds=25,
        train=TrainConfig(max_batches=12), trace_reputation=True,
    )
    result = run_federated(_DATASET, _SHARDS, config)
    client_ids = [f"client-{i:03d}" for i in range(N_CLIENTS)]
    malicious = set(select_malicious(client_ids, frac, seed))

    rows: List[Dict[str, object]] = []
    for round_id, reputations in result.reputation_trace:
        ids = sorted(reputations)
        if len(ids) < 4:
            continue
        values = np.array([reputations[c] for c in ids], dtype=np.float64)
        bad = np.array([c in malicious for c in ids])

        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        mad_cut = median - MAD_FACTOR * max(mad, 1e-6)

        split = otsu_split(values)
        gap_in_mads = (
            float(values[~bad].mean() - values[bad].mean()) / max(mad, 1e-9)
            if bad.any() and (~bad).any() else float("nan")
        )
        row = {
            "condition": label, "seed": seed, "round": round_id, "n": len(ids),
            "mad": mad, "mad_cut_hits": int((values < mad_cut).sum()),
            "mad_tp": int(((values < mad_cut) & bad).sum()),
            "mad_fp": int(((values < mad_cut) & ~bad).sum()),
            "gap_in_mads": gap_in_mads,
            "auc": _auc(values[~bad], values[bad]) if bad.any() else float("nan"),
            "n_malicious": int(bad.sum()),
        }
        if split is not None:
            low = values < split.threshold
            row.update({
                "eta": split.eta, "gap": split.gap,
                "low_frac": split.low_count / len(ids),
                "otsu_tp": int((low & bad).sum()), "otsu_fp": int((low & ~bad).sum()),
            })
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, min(5, (os.cpu_count() or 4) // 2)))
    args = ap.parse_args()

    specs = []
    for seed in DEV_SEEDS:
        specs.append(("no-attack", AttackConfig(attack=AttackType.NONE), 0.0, seed))
        specs.append(("slow-drift", AttackConfig(attack=AttackType.SLOW_DRIFT, beta=0.9), 0.2, seed))
        specs.append(("adaptive-g0.5", AttackConfig(attack=AttackType.ADAPTIVE, gamma=0.5), 0.2, seed))

    print(f"diagnostic: {len(specs)} runs on DEV seeds {DEV_SEEDS}", flush=True)
    started = time.perf_counter()
    rows: List[Dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as pool:
        for i, batch in enumerate(pool.map(_run_one, specs), 1):
            rows.extend(batch)
            print(f"  {i}/{len(specs)}  {(time.perf_counter()-started)/60:.1f}m", flush=True)

    out = REPO_ROOT / "results" / "summary" / "g3_diagnostic.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\n{len(rows)} round-observations -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
