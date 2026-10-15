"""Client-side attacks A0-A4 for E-4/E-5.

Defined in ``E4_E5_MATRIX.md`` section 3. These are standard, published attacks
implemented inside a local simulator against this project's own models; nothing here
is novel and nothing here leaves the simulation.

The one that matters
--------------------
**A4, slow-drift**, is the falsification test for sub-claim C5. It is modelled on
"A Little Is Enough" (Baruch et al., NeurIPS 2019) `LIT`: rather than submitting an
obviously anomalous update, the attacker scales its malicious direction so the result
sits *just inside* the admission rule's rejection threshold, and repeats every round.
No single round looks anomalous; the damage accumulates.

The attacker is given **oracle knowledge of the threshold**. That is the worst case
for us and the correct assumption for a security evaluation -- a defence that only
works against an attacker who cannot see the rule is not a defence.

**This attacker will not be weakened.** If it succeeds, C5 is false and that is the
project's headline limitation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Sequence

import numpy as np

__all__ = ["AttackType", "AttackConfig", "apply_attack", "flip_labels", "is_data_attack"]


class AttackType(Enum):
    """Values are stable ids used in result tables."""

    NONE = "A0"
    SIGN_FLIP = "A1"
    LABEL_FLIP = "A2"
    SCALED = "A3"
    SLOW_DRIFT = "A4"
    NOISE = "A5"            # random direction, legitimate magnitude
    TARGETED = "A6"         # single-class poisoning
    ADAPTIVE = "A7"         # tuned against the G2 reputation rule
    NULLSPACE = "A8"        # hides in the null space of a PREDICTABLE sketch
    CAMOUFLAGE = "A9"       # destroys the reputation CLUSTER that G3 needs


@dataclass(frozen=True)
class AttackConfig:
    """Attack parameters.

    Attributes:
        attack: which attack.
        beta: **A4 only.** Target position relative to the rejection threshold.
            beta < 1 sits inside the admissible region (evasive); beta > 1 should be
            rejected. Swept over {0.25, 0.5, 0.75, 0.9, 1.1, 1.5} in E5.1.
        scale: **A3 only.** Multiplier applied to the honest update.
        gamma: **A7 only.** Fraction of the malicious direction retained when
            blending with the honest consensus direction. gamma=1 is a pure
            slow-drift attacker; gamma=0 is indistinguishable from honest and does
            no damage. The sweep over gamma IS the evasion/damage trade-off curve.
        target_class: **A6 only.** The class whose labels are poisoned.
        target_to: **A6 only.** The class they are flipped to.
    """

    attack: AttackType = AttackType.NONE
    beta: float = 0.9
    scale: float = 10.0
    gamma: float = 1.0
    target_class: int = 0
    target_to: int = 6


def is_data_attack(attack: AttackType) -> bool:
    """True if the attack corrupts training DATA rather than the resulting update.

    Label flipping produces an update that is a genuine gradient of a genuine (if
    mislabelled) dataset. Its norm is unremarkable, which is exactly why norm-based
    rules struggle with it -- see prediction P3.
    """
    return attack in (
        AttackType.LABEL_FLIP,
        AttackType.SLOW_DRIFT,
        AttackType.CAMOUFLAGE,
        AttackType.TARGETED,
        AttackType.ADAPTIVE,
    )


def flip_labels(y: np.ndarray, n_classes: int = 10) -> np.ndarray:
    """Deterministic label permutation ``y -> (n_classes - 1) - y``.

    Deterministic rather than random so a run is reproducible from its seed alone.
    """
    return (n_classes - 1) - y


def flip_target_class(y: np.ndarray, target: int, to: int) -> np.ndarray:
    """Targeted poisoning: relabel ONE class, leave the rest intact.

    Far subtler than a full permutation. Overall accuracy barely moves, so it is
    measured by per-class accuracy -- a headline number alone would hide it.
    """
    out = y.copy()
    out[y == target] = to
    return out


def nullspace_evasion(
    honest_update: np.ndarray,
    malicious_direction: np.ndarray,
    projection: np.ndarray,
    strength: float = 0.9,
) -> np.ndarray:
    """A8: hide a perturbation in the NULL SPACE of a known sketch matrix.

    `LIT` This attack is published: SketchGuard (2025) observes that when the sketch
    is a fixed, publicly known linear map, an adversary can add an arbitrarily large
    component that the sketch cannot see, because the projection annihilates it.

    Concretely: project the malicious direction onto null(P), so ``P @ evil`` is
    bit-identical to ``P @ honest``. Any rule computed from the sketch alone --
    including G2's direction test -- is structurally blind to it. Keeping the total
    norm under the bound defeats the magnitude test too.

    The published fix is **commit-then-sketch**: draw the projection seed only AFTER
    updates are committed, so the attacker cannot compute null(P) in advance. Our
    transcript supplies exactly that primitive.

    Args:
        honest_update: the update the client would otherwise submit.
        malicious_direction: the direction the attacker wants to inject.
        projection: the sketch matrix the attacker believes will be used.
        strength: perturbation size as a fraction of the honest norm.
    """
    coefficients = np.linalg.lstsq(
        projection @ projection.T, projection @ malicious_direction, rcond=None
    )[0]
    null_component = malicious_direction - projection.T @ coefficients
    norm = float(np.linalg.norm(null_component))
    if norm <= 1e-12:
        return honest_update
    scale = float(np.linalg.norm(honest_update)) * strength
    return (honest_update + null_component / norm * scale).astype(np.float32)


def camouflage_betas(malicious: Sequence[str], beta: float) -> Dict[str, float]:
    """A9: spread the coalition's intensities so their reputations form a CONTINUUM.

    Designed specifically against G3. G3 rejects only when the reputation population
    is genuinely **bimodal** -- when there is an empty gap between an honest mode and
    a malicious mode. The counter is therefore not to attack harder or more subtly,
    but to **refuse to form a cluster**: give each malicious client a different, fixed
    intensity so the coalition's reputations interpolate into the honest distribution
    and no gap exists to find.

    The intensities are **persistent per client**, not redrawn each round. That matters:
    the reputation is a running mean, so freshly random per-round intensities would
    average back to a common value and the cluster would simply re-form. Only a fixed
    per-client spread survives accumulation.

    Intensities are spread over ``[0.2*beta, beta]``, so the mean intensity is 0.6*beta.
    **This is a real cost to the attacker and is reported as one**: camouflage buys
    invisibility by attacking less hard, exactly the evasion/damage trade-off already
    measured for A7.

    Deterministic given the sorted coalition, so a run is reproducible from its seed.
    """
    members = sorted(malicious)
    if not members:
        return {}
    if len(members) == 1:
        return {members[0]: beta}
    span = len(members) - 1
    return {
        client: beta * (0.2 + 0.8 * index / span)
        for index, client in enumerate(members)
    }


def apply_attack(
    honest_update: np.ndarray,
    config: AttackConfig,
    *,
    malicious_update: np.ndarray | None = None,
    norm_threshold: float | None = None,
    consensus_direction: np.ndarray | None = None,
) -> np.ndarray:
    """Transform a client's update according to ``config``.

    Args:
        honest_update: what the client would have submitted if honest.
        config: attack parameters.
        malicious_update: for data attacks (A2, A4), the update produced by training
            on poisoned data. Required for A4.
        norm_threshold: **A4 only.** The rule's current rejection threshold, granted
            to the attacker as oracle knowledge.

    Returns:
        The update actually submitted.
    """
    attack = config.attack

    if attack is AttackType.NONE:
        return honest_update

    if attack is AttackType.SIGN_FLIP:
        # Large norm and a direction opposed to consensus: should be easy to catch.
        return -honest_update

    if attack is AttackType.SCALED:
        # Model-replacement style. Trivially detectable by any norm bound.
        return honest_update * config.scale

    if attack is AttackType.LABEL_FLIP:
        if malicious_update is None:
            raise ValueError("LABEL_FLIP requires malicious_update")
        # Submitted as-is: a legitimate gradient of mislabelled data.
        return malicious_update

    if attack in (AttackType.SLOW_DRIFT, AttackType.CAMOUFLAGE):
        if malicious_update is None:
            raise ValueError("SLOW_DRIFT requires malicious_update")
        if norm_threshold is None or norm_threshold <= 0:
            # No threshold known this round; fall back to plain label-flip.
            return malicious_update

        # Aim at beta * threshold: deliberately inside the admissible region when
        # beta < 1. The DIRECTION stays malicious; only the magnitude is tuned.
        norm = float(np.linalg.norm(malicious_update))
        if norm <= 1e-12:
            return malicious_update
        target = config.beta * norm_threshold
        return (malicious_update / norm * target).astype(np.float32)

    if attack is AttackType.NOISE:
        # Random direction at a legitimate magnitude: passes any norm bound, and is
        # directionally uncorrelated with the honest consensus rather than opposed
        # to it. Included because it separates "abnormal" from "adversarial".
        rng = np.random.default_rng(abs(hash(honest_update.tobytes())) % (2**32))
        noise = rng.standard_normal(honest_update.size).astype(np.float32)
        target = float(np.linalg.norm(honest_update))
        return (noise / np.linalg.norm(noise) * target).astype(np.float32)

    if attack is AttackType.TARGETED:
        if malicious_update is None:
            raise ValueError("TARGETED requires malicious_update")
        return malicious_update

    if attack is AttackType.ADAPTIVE:
        # ADAPTIVE: the attacker knows G2 and blends its malicious direction with the
        # honest CONSENSUS direction, so its median pairwise cosine stays inside the
        # honest range. It is granted ORACLE access to the consensus -- the worst
        # case for the defence.
        #
        # gamma controls the trade-off directly: more malicious content means more
        # damage AND a lower reputation score. Sweeping gamma traces the
        # evasion/damage curve, which is the honest way to evaluate a defence
        # against an adversary that adapts to it.
        if malicious_update is None:
            raise ValueError("ADAPTIVE requires malicious_update")
        mal_norm = float(np.linalg.norm(malicious_update))
        if mal_norm <= 1e-12:
            return malicious_update
        direction = malicious_update / mal_norm

        if consensus_direction is not None:
            cons_norm = float(np.linalg.norm(consensus_direction))
            if cons_norm > 1e-12:
                cons = consensus_direction / cons_norm
                blended = config.gamma * direction + (1.0 - config.gamma) * cons
                blend_norm = float(np.linalg.norm(blended))
                if blend_norm > 1e-12:
                    direction = blended / blend_norm

        target = (config.beta * norm_threshold) if norm_threshold else mal_norm
        return (direction * target).astype(np.float32)

    raise ValueError(f"unhandled attack type: {attack}")


def select_malicious(
    client_ids: Sequence[str], fraction: float, seed: int
) -> frozenset[str]:
    """Choose which clients are malicious, deterministically from ``seed``.

    Fixed for the whole run (static corruption), matching assumption A2 in E-3.
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be in [0, 1], got {fraction}")
    n = int(round(len(client_ids) * fraction))
    if n == 0:
        return frozenset()
    rng = np.random.default_rng(seed)
    chosen = rng.choice(np.array(sorted(client_ids)), size=n, replace=False)
    return frozenset(chosen.tolist())
