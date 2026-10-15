"""G3: separation-aware admission. Pre-registered in ``G3_PREREGISTRATION.md``.

**G1 and G2 are untouched.** Their published results in ``results/E4_E5_FINDINGS.md``
and ``results/G2_FINDINGS.md`` stand exactly as measured. G3 is a third-generation
ablation that changes **one component** of G2 and nothing else.

The one component
-----------------
G2's tests 1 (magnitude) and 2 (per-round direction on unit-normalised sketches) are
reused verbatim. Only test 3 -- how an accumulated reputation becomes a rejection --
is replaced.

`RESULT` ``G2_FINDINGS.md`` s3 measured the failure precisely: the reputation
population **separates** (rank AUC 1.000 after three rounds) but the pre-registered
``median(R) - 3*MAD(R)`` cutoff **does not fire**. The signal was there; the decision
rule could not convert it.

`INFERRED` The mechanism: ``median - k*MAD`` is a **dispersion** test, which models the
population as unimodal with tail contamination. Under attack the population is
**bimodal**. Rank separation (AUC) and distance-from-centre in MAD units are different
quantities, and they come apart exactly when the within-cluster spread -- which
non-IID heterogeneity makes large -- is comparable to the between-cluster gap. A
gap-seeking threshold targets the structure that is actually present.

`LIT` **This is not novel and is not claimed to be.** Clustering-based malicious-client
detection is well established: Auror (ACSAC 2016) uses k-means, FLAME (USENIX Sec
2022) uses HDBSCAN, and FLDetector-style defences use k-means with the gap statistic.
Otsu's method has itself been combined with adaptive thresholding for malicious-client
detection in FL. The literature *also* independently names the failure mode diagnosed
above -- static reputation thresholds not adapting to changing reputation
distributions. G3 is a competent application of known robust statistics.

What is defensible is narrower and is a **systems** argument, not an ML one: this
system's premise is that a third party recomputes the admission decision from the
transcript. HDBSCAN and k-means are iterative, initialisation-dependent and awkward to
re-verify bit-exactly; Otsu is closed-form, deterministic and O(n log n), so an
auditor reproduces the identical threshold from the recorded scores. The choice is
driven by AG1 verifiability, not by a claim of better detection.
"""

from __future__ import annotations

from typing import Dict, Mapping, Tuple

import numpy as np

from bcflsrv.fl.evidence import NORM_FACTOR, AdmissionDecision, Evidence
from bcflsrv.fl.reputation import ReputationState, direction_scores
from bcflsrv.fl.separation import otsu_split

__all__ = [
    "G3_WARMUP",
    "G3_GAP_MIN",
    "G3_MINORITY_MAX",
    "apply_g3_rule",
    "g3_rule_id",
]

G3_WARMUP = 3  # identical to G2 and deliberately NOT re-tuned: changing two things
               # at once would make the comparison uninterpretable.

# Minimum empty gap between the two reputation modes, in units of the population
# standard deviation, before the rule is allowed to reject anyone.
#
# CALIBRATION (scripts/diag_g3.py, development seeds 100-104, ATTACK-FREE condition
# only, against the project's standing bar of FPR <= 0.10 in force since E-4):
# **the gap gate turns out to be unnecessary.** With the minority bound below already
# applied, the attack-free false-positive rate is 0.046 at every gap threshold tested
# including zero, so no positive value is needed to meet the bar -- and every positive
# value strictly costs detection. It is therefore set to zero, which removes it as a
# tunable parameter rather than leaving a knob at a flattering setting. G3 introduces
# **no new calibrated constant**. The ablation in G3_PREREGISTRATION.md s7 re-tests
# this on the held-out confirmatory seeds.
G3_GAP_MIN = 0.0

# The rule may only reject the LOW class, and only while it is a minority.
# This introduces no new assumption: it is the corruption bound the committee already
# assumes. A 6-of-9 attestation threshold tolerates 3 faulty members, i.e. f < n/3.
G3_MINORITY_MAX = 1.0 / 3.0


def g3_rule_id(
    warmup: int = G3_WARMUP,
    gap_min: float = G3_GAP_MIN,
    *,
    population: bool = True,
    accumulate: bool = True,
    two_sided: bool = False,
) -> str:
    """Stable declared rule identifier -- AG1 requires the applied rule to be named."""
    scope = "pop" if population else "round"
    memory = "acc" if accumulate else "single"
    sides = "2s" if two_sided else "1s"
    return (
        f"g3-otsu-{scope}-{memory}-{sides}-w{warmup}-gap{gap_min:g}"
        f"-min{G3_MINORITY_MAX:.3f}-norm{NORM_FACTOR}x/v1"
    )


def apply_g3_rule(
    evidences: Mapping[str, Evidence],
    state: ReputationState,
    *,
    warmup: int = G3_WARMUP,
    gap_min: float = G3_GAP_MIN,
    population: bool = True,
    accumulate: bool = True,
    two_sided: bool = False,
    update_state: bool = True,
) -> Tuple[AdmissionDecision, Dict[str, float]]:
    """Apply G3 and return the decision plus this round's direction scores.

    Args:
        evidences: this round's evidence; must carry sketch vectors (E3/E4).
        state: reputation accumulated so far. Mutated when ``update_state``.
        warmup: participations required before the reputation test applies.
        gap_min: the calibrated separability gate.
        population: locate the split using **every** client with enough
            participations (True), or only this round's participants (False, which
            is G2's scope). Ablated separately -- the ledger is what makes the
            population view available to a stateless committee at all.
        accumulate: use the cross-round running mean (True) or this round's score
            alone (False). Ablated separately to isolate whether multi-round memory
            contributes anything once the cutoff is fixed.
        two_sided: also reject an anomalous **high** minority cluster. Off by default.
            The diagnostic found that the adaptive attacker A7 scores *above* honest
            clients (rank AUC 0.083), because blending toward the consensus makes it
            more consensus-like than genuinely heterogeneous honest clients are. No
            low-side cutoff can ever reach it. This flag tests whether that is fixable
            by the rule; it is expected to cost false positives, and A7's measured
            damage is already within noise, so it is evaluated as an ablation rather
            than adopted.
        update_state: set False to evaluate without advancing state (auditing).

    Returns:
        ``(decision, scores)``.
    """
    client_ids = sorted(evidences)
    rule = g3_rule_id(
        warmup, gap_min, population=population, accumulate=accumulate, two_sided=two_sided
    )
    if not client_ids:
        return AdmissionDecision((), (), rule, {}), {}

    # --- Test 1: magnitude. Verbatim from G1/G2. -----------------------------
    norms = np.array([evidences[c].norm or 0.0 for c in client_ids])
    norm_threshold = float(np.median(norms)) * NORM_FACTOR
    rejected = {c for c, n in zip(client_ids, norms) if n > norm_threshold}
    thresholds: Dict[str, float] = {"norm": norm_threshold}

    # --- Test 2: direction on the unit sphere. Verbatim from G2. -------------
    vectors = {c: evidences[c].vector for c in client_ids if evidences[c].vector is not None}
    if len(vectors) < 2:
        admitted = tuple(c for c in client_ids if c not in rejected)
        return AdmissionDecision(admitted, tuple(sorted(rejected)), rule, thresholds), {}

    scores = direction_scores(vectors)
    if update_state:
        state.observe(scores)

    # --- Test 3: SEPARATION-AWARE cutoff. The only thing G3 changes. ---------
    if accumulate:
        candidates = sorted(state.counts) if population else client_ids
        judged = {}
        for c in candidates:
            if state.participations(c) < warmup:
                continue
            value = state.reputation(c)
            if value is not None:
                judged[c] = value
    else:
        # Single-round ablation: no memory at all, just this round's scores.
        judged = dict(scores)

    if len(judged) >= 4:
        ids = sorted(judged)
        values = np.array([judged[c] for c in ids], dtype=np.float64)
        split = otsu_split(values)
        thresholds["reputation_median"] = float(np.median(values))
        if split is not None:
            thresholds["otsu_gap"] = split.gap
            thresholds["otsu_eta"] = split.eta
            thresholds["otsu_threshold"] = split.threshold
            low_fraction = split.low_count / len(ids)
            high_fraction = 1.0 - low_fraction
            # The minority bound is what makes a gap-seeker safe. Asked to split an
            # honest population, Otsu will happily cut it in half; requiring the
            # rejected class to be a minority is what stops that, and it costs nothing
            # in assumptions because the committee already assumes f < n/3.
            if split.gap >= gap_min and low_fraction <= G3_MINORITY_MAX:
                thresholds["reputation"] = split.threshold
                rejected |= {
                    c for c in client_ids
                    if c in judged and judged[c] < split.threshold
                }
            elif two_sided and split.gap >= gap_min and high_fraction <= G3_MINORITY_MAX:
                thresholds["reputation_high"] = split.threshold
                rejected |= {
                    c for c in client_ids
                    if c in judged and judged[c] >= split.threshold
                }

    admitted = tuple(c for c in client_ids if c not in rejected)
    return AdmissionDecision(admitted, tuple(sorted(rejected)), rule, thresholds), scores
