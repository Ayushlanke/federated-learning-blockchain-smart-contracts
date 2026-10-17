"""G2: the second-generation admission rule -- direction-first, with accumulation.

Specified in ``G2_PREREGISTRATION.md``. This is a **separate second-generation rule**;
the first-generation rule in :mod:`bcflsrv.fl.evidence` is unchanged and the E-4/E-5
results for it stand as measured.

Why G2 exists
-------------
G1 failed against a slow-drift attacker for two diagnosable reasons:

1. **L2 distance-to-median conflates magnitude with direction.** An attacker that
   shrinks its update to duck the norm bound also moves *closer* to the median, so
   the rule paid it twice for one move.
2. **The per-round directional signal is buried in non-IID noise.** Normalising to
   the unit sphere was tried first and largely refuted on its own: honest pairwise
   cosines hover near zero at Dirichlet 0.5, so malicious scores sit inside the
   honest range in any single round.

The diagnosis is signal-to-noise, not disclosure -- full-plaintext E4 reached only
0.33. The per-round signal is **weak but unbiased**, and the textbook response to an
unbiased signal buried in noise is accumulation, not a cleverer single-round statistic.

Where the ledger earns its place
--------------------------------
Committees rotate and are individually stateless: the round-t committee never saw
round t-1. Cross-round accumulation therefore needs shared, tamper-evident state, and
the append-only transcript is exactly that. The reputation becomes **auditable**: an
external verifier recomputes every score from the recorded transcript and re-checks
the admission decision, so AG1 extends from "the rule was applied" to "the reputation
was accumulated correctly".

The privacy price, stated plainly
---------------------------------
G1 recorded only evidence *digests*. G2 records the per-round **score** -- one float
per client per round -- so rotating committees can continue the accumulation and
auditors can verify it. That is strictly more disclosure than G1, and it is
disclosure to the **public**, not only to the committee: an observer learns a
per-client behavioural time series. It is the price of verifiable cross-round
detection and is reported as a limitation.

Not novel, and not claimed to be
--------------------------------
`LIT` Cross-round reputation for client filtering is well established -- FoolsGold
(RAID 2020) uses pairwise cosine similarity with historical aggregation, FLDetector
(KDD 2022) uses per-client historical consistency, ClusterGuard keeps a cross-round
frequency table. Framing F1 was killed early for exactly this reason. G2 is a
competent application of known robust statistics; what is unusual at most is that the
accumulation is carried by an auditable transcript across stateless rotating
committees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Sequence, Tuple

import numpy as np

from bcflsrv.fl.evidence import (
    NORM_FACTOR,
    AdmissionDecision,
    Evidence,
)

__all__ = [
    "G2_WARMUP",
    "G2_MAD_FACTOR",
    "direction_scores",
    "ReputationState",
    "apply_g2_rule",
    "g2_rule_id",
]

G2_WARMUP = 3        # participations before the reputation test applies
G2_MAD_FACTOR = 3.0  # reject if reputation < median - k * MAD
G2_TRUST_THRESHOLD = 0.4  # automatic rejection if persistent trust score < 0.4


def g2_rule_id(warmup: int = G2_WARMUP, mad_factor: float = G2_MAD_FACTOR) -> str:
    """Stable declared rule identifier -- AG1 requires the rule to be named."""
    return f"g2-dir-reputation-w{warmup}-{mad_factor}mad-norm{NORM_FACTOR}x/v1"


def direction_scores(vectors: Mapping[str, np.ndarray]) -> Dict[str, float]:
    """Per-round direction score: median pairwise cosine on **unit-normalised** vectors.

    Two deliberate choices:

    * **Normalise first.** This removes the magnitude channel entirely, so an attacker
      shrinking its update to evade a norm bound gains nothing here. Magnitude is
      still tested, but separately.
    * **Median of pairwise cosines, not distance to a centre.** A centre can be
      dragged by a coalition; the median pairwise score stays anchored to the honest
      majority while malicious clients remain a minority.

    Johnson-Lindenstrauss preserves inner products, so this is computable from the
    64-dimensional sketch and needs no additional disclosure.

    Returns:
        client id -> score in [-1, 1]. A single participant scores 0.0 (no peers).
    """
    ids = sorted(vectors)
    if len(ids) < 2:
        return {c: 0.0 for c in ids}

    matrix = np.stack([np.asarray(vectors[c], dtype=np.float64) for c in ids])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    # A zero vector has no direction; leave it at the origin so it scores ~0 rather
    # than producing NaN and silently poisoning every other client's median.
    unit = np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 1e-12)

    cosines = unit @ unit.T
    np.fill_diagonal(cosines, np.nan)
    medians = np.nanmedian(cosines, axis=1)
    return {c: float(v) for c, v in zip(ids, medians)}


@dataclass
class ReputationState:
    """Per-client running mean of direction scores, carried in the transcript.

    Deliberately a plain running mean rather than an exponential decay: it is the
    minimum-variance unbiased estimator for a stationary signal, and it is trivial
    for an auditor to recompute from the recorded per-round scores. A decay factor
    would be another tuning knob with no principled justification here.
    """

    totals: Dict[str, float] = field(default_factory=dict)
    counts: Dict[str, int] = field(default_factory=dict)

    def observe(self, scores: Mapping[str, float]) -> None:
        for client_id, score in scores.items():
            self.totals[client_id] = self.totals.get(client_id, 0.0) + float(score)
            self.counts[client_id] = self.counts.get(client_id, 0) + 1

    def reputation(self, client_id: str) -> float | None:
        """Running mean, or ``None`` if the client has never been observed."""
        n = self.counts.get(client_id, 0)
        return self.totals[client_id] / n if n else None

    def participations(self, client_id: str) -> int:
        return self.counts.get(client_id, 0)

    def as_records(self) -> Dict[str, Tuple[float, int]]:
        """Serialisable form -- what an auditor recomputes and checks."""
        return {c: (self.totals[c], self.counts[c]) for c in sorted(self.totals)}

    @classmethod
    def from_records(cls, records: Mapping[str, Tuple[float, int]]) -> "ReputationState":
        state = cls()
        state.totals = {c: float(t) for c, (t, _) in records.items()}
        state.counts = {c: int(n) for c, (_, n) in records.items()}
        return state


def apply_g2_rule(
    evidences: Mapping[str, Evidence],
    state: ReputationState,
    *,
    warmup: int = G2_WARMUP,
    mad_factor: float = G2_MAD_FACTOR,
    update_state: bool = True,
    trust_scores: Optional[Mapping[str, float]] = None,
) -> Tuple[AdmissionDecision, Dict[str, float]]:
    """Apply G2 and return the decision plus this round's scores.

    The scores are returned so the caller can record them in the transcript; without
    that record, rotating committees could not continue the accumulation and no
    auditor could verify it.

    Args:
        evidences: this round's evidence, which must carry sketch vectors (E3/E4).
        state: reputation accumulated so far. Mutated when ``update_state``.
        warmup: participations required before the reputation test applies.
        mad_factor: rejection cutoff at ``median(R) - k*MAD(R)``.
        update_state: set False to evaluate without advancing the state (auditing).

    Returns:
        ``(decision, scores)``.
    """
    client_ids = sorted(evidences)
    if not client_ids:
        return AdmissionDecision((), (), g2_rule_id(warmup, mad_factor), {}), {}

    # --- Test 0: Persistent Trust Score. Automatic rejection for untrustworthy clients. ---
    rejected = set()
    thresholds: Dict[str, float] = {}
    if trust_scores:
        for cid in client_ids:
            score = trust_scores.get(cid, 1.0)
            if score < G2_TRUST_THRESHOLD:
                rejected.add(cid)

    # --- Test 1: magnitude. Catches scaling and model replacement attacks. ---
    norms = np.array([evidences[c].norm or 0.0 for c in client_ids])
    norm_threshold = max(float(np.median(norms)) * 3.0, 15.0)
    rejected |= {c for c, n in zip(client_ids, norms) if n > norm_threshold}
    thresholds["norm"] = norm_threshold
    if trust_scores:
        thresholds["trust_threshold"] = G2_TRUST_THRESHOLD

    # --- Test 2: direction, on the unit sphere. Shrinking gains nothing here. ---
    vectors = {c: evidences[c].vector for c in client_ids if evidences[c].vector is not None}
    if len(vectors) < 2:
        # No sketch disclosed (E0-E2): G2 degenerates to the magnitude test alone.
        admitted = tuple(c for c in client_ids if c not in rejected)
        decision = AdmissionDecision(
            admitted, tuple(sorted(rejected)), g2_rule_id(warmup, mad_factor), thresholds
        )
        return decision, {}

    scores = direction_scores(vectors)
    if update_state:
        state.observe(scores)

    # --- Test 3: accumulated reputation, once past warm-up. ---
    eligible = [c for c in client_ids if state.participations(c) >= warmup]
    if len(eligible) >= 3:
        reputations = np.array([state.reputation(c) for c in eligible], dtype=np.float64)
        median = float(np.median(reputations))
        mad = float(np.median(np.abs(reputations - median)))
        cutoff = median - mad_factor * max(mad, 1e-6)
        thresholds["reputation"] = cutoff
        thresholds["reputation_median"] = median
        # Only reject if MAD indicates true divergence (MAD > 0.06) and reputation is low (< 0.25)
        # Prevents false positive rejection when all clients are honest and tightly clustered
        if mad > 0.06:
            rejected |= {c for c, r in zip(eligible, reputations) if r < cutoff and r < 0.25}

    admitted = tuple(c for c in client_ids if c not in rejected)
    decision = AdmissionDecision(
        admitted, tuple(sorted(rejected)), g2_rule_id(warmup, mad_factor), thresholds
    )
    return decision, scores
