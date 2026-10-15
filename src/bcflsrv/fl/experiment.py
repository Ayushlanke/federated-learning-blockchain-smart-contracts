"""One federated-learning run, parameterised by system / disclosure / attack.

This is the engine behind every row of ``E4_E5_MATRIX.md``. A single function runs
one configuration end to end and returns metrics; the driver script sweeps it.

The three systems (matrix section 2)
------------------------------------
* **S0** plain FedAvg -- no admission rule, no verification. The floor.
* **S1** admission rule applied by a *trusted* server -- isolates the rule's ML value.
* **S2** full BC-FL-SRV -- same rule, applied by a committee, attested, recorded.

**S1 and S2 are expected to produce identical ML metrics** (prediction P1). They
differ only in overhead, because the mechanism changes whether a decision can be
*verified*, not which decision is made. Running both and showing they match is the
honest way to state what the contribution is and is not.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, List, Sequence, Tuple

import numpy as np
import torch

from bcflsrv.crypto.identity import Identity
from bcflsrv.fl.attacks import (
    AttackConfig,
    AttackType,
    apply_attack,
    camouflage_betas,
    flip_labels,
    flip_target_class,
    is_data_attack,
    select_malicious,
)
from bcflsrv.fl.data import ClientShard, FashionMNIST
from bcflsrv.fl.evidence import (
    DisclosureLevel,
    apply_rule,
    encode_evidence,
    rule_id_for,
)
from bcflsrv.fl.masking import mask_updates, aggregate_masked_mean
from bcflsrv.fl.rule_g3 import G3_GAP_MIN, apply_g3_rule, g3_rule_id
from bcflsrv.fl.reputation import (
    G2_WARMUP,
    ReputationState,
    apply_g2_rule,
    g2_rule_id,
)
from bcflsrv.fl.model import (
    SmallCNN,
    TrainConfig,
    evaluate,
    fedavg,
    get_flat_params,
    local_train,
)
from bcflsrv.ledger.transcript import EntryKind, Transcript
from bcflsrv.protocol.admission import (
    AdmissionSet,
    Submission,
    attestation_entropy,
    build_attestation,
)
from bcflsrv.crypto.sortition import select_committee

__all__ = ["System", "RunConfig", "RunResult", "run_federated"]


class System(Enum):
    S0_PLAIN = "S0"        # plain FedAvg, no rule, no verification
    S1_RULE_ONLY = "S1"    # rule applied by a trusted server
    S2_FULL = "S2"         # rule + committee attestation + transcript


class RuleGeneration(Enum):
    """Which admission rule. G1 results are frozen; G2 is a separate ablation."""

    G1 = "G1"  # original: norm + cosine-to-global / distance-to-median (E-4/E-5)
    G2 = "G2"  # second generation: direction-first with cross-round reputation
    G3 = "G3"  # third generation: G2 with a SEPARATION-AWARE cutoff (rule_g3.py)


@dataclass(frozen=True)
class RunConfig:
    """One cell of the experiment matrix."""

    system: System = System.S1_RULE_ONLY
    level: DisclosureLevel = DisclosureLevel.E2
    attack: AttackConfig = field(default_factory=AttackConfig)
    malicious_fraction: float = 0.2
    n_clients: int = 30
    clients_per_round: int = 10
    rounds: int = 25
    committee_size: int = 9
    threshold: int = 6
    seed: int = 0
    train: TrainConfig = field(default_factory=lambda: TrainConfig(max_batches=12))
    use_masking: bool = True
    rule: RuleGeneration = RuleGeneration.G1
    warmup: int = G2_WARMUP
    # Commit-then-sketch: derive the projection seed from the round's COMMITMENTS
    # rather than from a predictable formula, so an attacker cannot precompute
    # null(P) and hide in it. Set False only to demonstrate the A8 vulnerability.
    commit_then_sketch: bool = True
    # Record the per-round reputation population for offline diagnosis. This is
    # exactly the state the transcript already publishes in the full system, so
    # tracing it discloses nothing extra; it is off by default to keep runs light.
    trace_reputation: bool = False
    # G3 ablation knobs (ignored unless rule is G3).
    g3_population: bool = True   # locate the split over all clients, not just this round
    g3_accumulate: bool = True   # use the cross-round running mean, not a single round
    g3_two_sided: bool = False   # also reject an anomalous HIGH cluster (ablation)
    g3_gap_min: float = G3_GAP_MIN  # calibration found 0 sufficient; ablated anyway

    def label(self) -> str:
        return (
            f"{self.system.value}/{self.rule.value}/{self.level.value}"
            f"/{self.attack.attack.value}/f{self.malicious_fraction}"
            f"/b{self.attack.beta}/g{self.attack.gamma}/s{self.seed}"
        )


@dataclass
class RunResult:
    """Metrics for one run. Field names are the CSV columns."""

    config: RunConfig
    final_accuracy: float = 0.0
    best_accuracy: float = 0.0
    min_class_accuracy: float = 0.0
    accuracy_history: List[float] = field(default_factory=list)
    true_positives: int = 0     # malicious submissions rejected
    false_negatives: int = 0    # malicious submissions admitted
    true_negatives: int = 0     # honest submissions admitted
    false_positives: int = 0    # honest submissions rejected
    malicious_admitted_fraction: float = 0.0
    transcript_bytes: int = 0
    evidence_bytes: int = 0
    wall_clock_s: float = 0.0
    aborted_rounds: int = 0
    # (round_id, {client_id: running-mean reputation}) -- populated only when
    # RunConfig.trace_reputation. Never written to the CSV row.
    reputation_trace: List[Tuple[int, Dict[str, float]]] = field(default_factory=list)

    @property
    def tpr(self) -> float:
        total = self.true_positives + self.false_negatives
        return self.true_positives / total if total else float("nan")

    @property
    def fpr(self) -> float:
        total = self.false_positives + self.true_negatives
        return self.false_positives / total if total else float("nan")

    def as_row(self) -> Dict[str, object]:
        c = self.config
        return {
            "system": c.system.value,
            "rule": c.rule.value,
            "warmup": c.warmup,
            "commit_then_sketch": c.commit_then_sketch,
            "disclosure": c.level.value,
            "attack": c.attack.attack.value,
            "beta": c.attack.beta,
            "gamma": c.attack.gamma,
            "malicious_fraction": c.malicious_fraction,
            "seed": c.seed,
            "rounds": c.rounds,
            "n_clients": c.n_clients,
            "clients_per_round": c.clients_per_round,
            "rule_id": _rule_id_for_config(c),
            "g3_population": c.g3_population,
            "g3_accumulate": c.g3_accumulate,
            "g3_two_sided": c.g3_two_sided,
            "g3_gap_min": c.g3_gap_min,
            "final_accuracy": self.final_accuracy,
            "best_accuracy": self.best_accuracy,
            "min_class_accuracy": self.min_class_accuracy,
            "tpr": self.tpr,
            "fpr": self.fpr,
            "true_positives": self.true_positives,
            "false_negatives": self.false_negatives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "malicious_admitted_fraction": self.malicious_admitted_fraction,
            "transcript_bytes": self.transcript_bytes,
            "evidence_bytes": self.evidence_bytes,
            "wall_clock_s": self.wall_clock_s,
            "aborted_rounds": self.aborted_rounds,
        }


def client_seed_offset(client_id: str) -> int:
    """Deterministic per-client seed offset.

    Python's built-in ``hash()`` on strings is salted per process (PEP 456), so using
    it here made a run's training seeds depend on **which worker process executed
    it**. Two identical configurations dispatched to different workers trained
    differently, which silently violated the project's fixed-seed guarantee. Found
    while analysing the G3 confirmatory run, when S1c and S3 -- which must be
    identical by construction -- disagreed.

    SHA-256 is stable across processes, machines and Python versions, so a run is now
    reproducible from ``(config, seed)`` alone.
    """
    return int.from_bytes(hashlib.sha256(client_id.encode()).digest()[:4], "big")


def _rule_id_for_config(c: RunConfig) -> str:
    """The declared rule identifier recorded alongside every result row."""
    if c.rule is RuleGeneration.G3:
        return g3_rule_id(
            c.warmup, c.g3_gap_min, population=c.g3_population,
            accumulate=c.g3_accumulate, two_sided=c.g3_two_sided,
        )
    if c.rule is RuleGeneration.G2:
        return g2_rule_id(c.warmup)
    return rule_id_for(c.level)


def run_federated(
    dataset: FashionMNIST,
    shards: Sequence[ClientShard],
    config: RunConfig,
) -> RunResult:
    """Execute one full federated run and return its metrics."""
    import time

    started = time.perf_counter()
    torch.manual_seed(config.seed)
    rng = np.random.default_rng(config.seed)

    client_ids = [s.client_id for s in shards]
    shard_by_id = {s.client_id: s for s in shards}
    malicious = select_malicious(client_ids, config.malicious_fraction, config.seed)

    identities = {c: Identity.from_seed(c.encode()) for c in client_ids}
    global_params = get_flat_params(SmallCNN(dataset.n_classes))
    prev_global_update: np.ndarray | None = None

    transcript = Transcript() if config.system is System.S2_FULL else None
    seed_entropy = b""
    result = RunResult(config=config)
    # Cross-round reputation (G2 only). In the full system this state is carried by
    # the transcript so rotating stateless committees can continue it; here it is
    # held in-process, which is equivalent for measurement purposes.
    reputation = ReputationState()

    for round_id in range(config.rounds):
        selected = sorted(
            rng.choice(np.array(client_ids), size=config.clients_per_round, replace=False).tolist()
        )
        # --- local training -------------------------------------------------
        honest: Dict[str, np.ndarray] = {}
        poisoned: Dict[str, np.ndarray] = {}
        for cid in selected:
            shard = shard_by_id[cid]
            x = dataset.x_train[shard.indices]
            y = dataset.y_train[shard.indices]
            train_seed = (
                config.seed * 100_000 + round_id * 100 + client_seed_offset(cid) % 100
            )
            honest[cid] = local_train(global_params, x, y, config.train, train_seed, dataset.n_classes)
            if cid in malicious and is_data_attack(config.attack.attack):
                if config.attack.attack is AttackType.TARGETED:
                    bad_y = flip_target_class(
                        y, config.attack.target_class, config.attack.target_to
                    )
                else:
                    bad_y = flip_labels(y, dataset.n_classes)
                poisoned[cid] = local_train(
                    global_params, x, bad_y, config.train, train_seed, dataset.n_classes,
                )

        # --- attacks (threshold-aware for slow drift) ------------------------
        # The slow-drift attacker is granted ORACLE knowledge of the threshold the
        # rule will use, computed from the honest clients' evidence. This is the
        # worst case for us and is stated as such in the matrix.
        norm_threshold = None
        consensus_direction = None
        if config.attack.attack is AttackType.ADAPTIVE:
            # ORACLE: the adaptive attacker is handed the honest consensus direction
            # and the threshold. Worst case for the defence, by design.
            honest_only = [honest[c] for c in selected if c not in malicious]
            if honest_only:
                consensus_direction = np.mean(np.stack(honest_only), axis=0)
        if config.attack.attack in (
            AttackType.SLOW_DRIFT, AttackType.ADAPTIVE, AttackType.CAMOUFLAGE
        ):
            honest_norms = [
                float(np.linalg.norm(honest[c])) for c in selected if c not in malicious
            ]
            if honest_norms:
                from bcflsrv.fl.evidence import NORM_FACTOR

                norm_threshold = float(np.median(honest_norms)) * NORM_FACTOR

        attacker_projection = None
        if config.attack.attack is AttackType.NULLSPACE:
            # The attacker predicts the seed with the public formula and builds P itself.
            # Under commit-then-sketch this guess is simply wrong.
            from bcflsrv.fl.evidence import SKETCH_DIM, _projection

            guessed = int.from_bytes(
                hashlib.sha256(b"proj/%d/%d" % (config.seed, round_id)).digest()[:4], "big"
            )
            attacker_projection = _projection(global_params.size, SKETCH_DIM, guessed)

        submitted: Dict[str, np.ndarray] = {}
        for cid in selected:
            if cid in malicious and config.attack.attack is AttackType.NULLSPACE:
                from bcflsrv.fl.attacks import nullspace_evasion

                rng_dir = np.random.default_rng(
                    round_id * 31 + client_seed_offset(cid) % 1000
                )
                direction = rng_dir.standard_normal(global_params.size).astype(np.float32)
                submitted[cid] = nullspace_evasion(
                    honest[cid], direction, attacker_projection
                )
            elif cid in malicious:
                attack_config = config.attack
                if attack_config.attack is AttackType.CAMOUFLAGE:
                    # Persistent per-client intensity: the coalition deliberately
                    # spreads out so no reputation cluster forms for G3 to find.
                    attack_config = replace(
                        attack_config, beta=camouflage_betas(malicious, config.attack.beta)[cid]
                    )
                submitted[cid] = apply_attack(
                    honest[cid], attack_config,
                    malicious_update=poisoned.get(cid),
                    norm_threshold=norm_threshold,
                    consensus_direction=consensus_direction,
                )
            else:
                submitted[cid] = honest[cid]

        # --- projection seed: COMMIT-THEN-SKETCH -----------------------------
        # Derived from this round's commitments, so it cannot be known until every
        # client has already fixed its update. This is what defeats the null-space
        # attack (A8); the predictable variant is kept only to demonstrate the flaw.
        predictable_seed = int.from_bytes(
            hashlib.sha256(b"proj/%d/%d" % (config.seed, round_id)).digest()[:4], "big"
        )
        if config.commit_then_sketch:
            commits = b"".join(
                sorted(hashlib.sha256(submitted[c].tobytes()).digest() for c in selected)
            )
            projection_seed = int.from_bytes(
                hashlib.sha256(b"proj-cts/" + commits).digest()[:4], "big"
            )
        else:
            projection_seed = predictable_seed

        # --- admission -------------------------------------------------------
        if config.system is System.S0_PLAIN:
            admitted = tuple(selected)
            rejected: Tuple[str, ...] = ()
            evidence_bytes = 0
        else:
            evidences = {
                cid: encode_evidence(config.level, submitted[cid], prev_global_update, projection_seed)
                for cid in selected
            }
            if config.rule is RuleGeneration.G3:
                decision, _round_scores = apply_g3_rule(
                    evidences, reputation, warmup=config.warmup,
                    gap_min=config.g3_gap_min,
                    population=config.g3_population, accumulate=config.g3_accumulate,
                    two_sided=config.g3_two_sided,
                )
            elif config.rule is RuleGeneration.G2:
                decision, _round_scores = apply_g2_rule(
                    evidences, reputation, warmup=config.warmup
                )
            else:
                decision = apply_rule(config.level, evidences)
            if config.rule in (RuleGeneration.G2, RuleGeneration.G3):
                if config.trace_reputation:
                    result.reputation_trace.append((
                        round_id,
                        {c: r for c in sorted(reputation.counts)
                         if (r := reputation.reputation(c)) is not None},
                    ))
            admitted, rejected = decision.admitted, decision.rejected
            evidence_bytes = sum(e.size_bytes() for e in evidences.values())
        result.evidence_bytes += evidence_bytes

        for cid in selected:
            is_bad = cid in malicious
            was_rejected = cid in rejected
            if is_bad and was_rejected:
                result.true_positives += 1
            elif is_bad and not was_rejected:
                result.false_negatives += 1
            elif not is_bad and was_rejected:
                result.false_positives += 1
            else:
                result.true_negatives += 1

        if not admitted:
            result.aborted_rounds += 1
            continue

        # --- S2 only: attest and record --------------------------------------
        if config.system is System.S2_FULL and transcript is not None:
            prev_root = transcript.root
            for cid in selected:
                submission = Submission(
                    client_id=cid, round_id=round_id, prev_root=prev_root,
                    masked_digest=hashlib.sha256(submitted[cid].tobytes()).digest(),
                    evidence_digest=evidences[cid].digest(),
                )
                transcript.append(EntryKind.SUBMIT, submission.digest())

            admission = AdmissionSet(
                round_id=round_id, rule_id=rule_id_for(config.level),
                prev_root=prev_root, admitted=tuple(admitted), rejected=tuple(rejected),
            )
            committee = select_committee(
                prev_root, round_id, client_ids, config.committee_size, entropy=seed_entropy
            )
            signers = {identities[c].public_key: identities[c] for c in committee}
            attestation = build_attestation(admission, signers)
            seed_entropy = attestation_entropy(attestation)
            transcript.append(EntryKind.ADMIT, admission.digest())
            transcript.append(EntryKind.FINALIZE, hashlib.sha256(b"agg/%d" % round_id).digest())

        # --- aggregation ------------------------------------------------------
        admitted_updates = {c: submitted[c] for c in admitted}
        if config.use_masking and len(admitted_updates) >= 2:
            # Simplified additive masking (NOT production SecAgg -- see masking.py).
            # The aggregator only ever holds masked vectors and their mean.
            masked = mask_updates(admitted_updates, round_id)
            mean_update = aggregate_masked_mean(masked, sorted(admitted_updates))
        else:
            mean_update = fedavg(list(admitted_updates.values()))

        global_params = global_params + mean_update
        prev_global_update = mean_update

        if round_id % 5 == 4 or round_id == config.rounds - 1:
            metrics = evaluate(global_params, dataset.x_test, dataset.y_test, dataset.n_classes)
            result.accuracy_history.append(metrics["accuracy"])
            result.final_accuracy = metrics["accuracy"]
            result.best_accuracy = max(result.best_accuracy, metrics["accuracy"])
            result.min_class_accuracy = metrics["min_class_accuracy"]

    total_malicious_submissions = result.true_positives + result.false_negatives
    result.malicious_admitted_fraction = (
        result.false_negatives / total_malicious_submissions
        if total_malicious_submissions
        else 0.0
    )
    if transcript is not None:
        result.transcript_bytes = len(transcript.to_jsonl().encode("utf-8"))
    result.wall_clock_s = time.perf_counter() - started
    return result
