"""The disclosure ladder E0-E4 and the admission rules that operate on each rung.

Implements `D-006`. This is the **independent variable of experiment E-4**: each rung
determines how much a committee member learns about a submission, and therefore what
admission rule it is even able to apply.

| Level | Committee sees | Size | Rule it can apply |
|-------|----------------|------|-------------------|
| E0 | commitment only | O(1) | none -- admit all |
| E1 | L2 norm | O(1) | norm bound |
| E2 | norm + cosine to the previous global update | O(1) | norm bound + direction agreement |
| E3 | random-projection sketch, d' << N | O(d') | distance-to-median in projected space |
| E4 | full plaintext update | O(N) | distance-to-median in full space |

E0 and E4 are the two ends that make the ablation meaningful: E0 shows what verifiable
admission is worth when there is nothing to verify, E4 shows the ceiling at zero
privacy.

The rules are deliberately ordinary
-----------------------------------
`LIT` Framing F2 ("SecAgg + Byzantine robustness") was killed as saturated, so no
novelty is claimed for these rules. Norm bounds and distance-to-median are standard.
They exist to make the ladder measurable, not to advance robust aggregation.

Every rule is **deterministic** and carries a stable ``rule_id``. That is what makes
AG1 meaningful: an auditor can only check "the declared rule was applied" if the rule
is a function of recorded inputs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Sequence, Tuple

import numpy as np

__all__ = [
    "DisclosureLevel",
    "Evidence",
    "encode_evidence",
    "AdmissionDecision",
    "apply_rule",
    "rule_id_for",
    "SKETCH_DIM",
]

SKETCH_DIM = 64          # d' for E3

# ---------------------------------------------------------------------------
# Threshold calibration
# ---------------------------------------------------------------------------
# These constants were calibrated on the ATTACK-FREE condition (experiment E4.2,
# Dirichlet alpha=0.5) to hold the false-positive rate near 5%, then FROZEN for every
# attack experiment. Calibrating a detector's false-alarm rate on clean data and then
# measuring detection is standard practice; tuning thresholds after seeing attack
# results would not be.
#
# The first calibration attempt used a FIXED cosine floor of 0.0 and measured a 39%
# false-positive rate on honest clients: under non-IID data an honest update
# legitimately points away from the previous global direction. Every threshold is
# therefore a ROBUST STATISTIC OF THE ROUND (median +/- k*MAD) rather than an
# absolute constant, which is also what makes the rule scale-free across rounds.
NORM_FACTOR = 1.5          # reject if ||u|| > NORM_FACTOR * median(||u||)
COSINE_MAD_FACTOR = 3.0    # reject if cosine < median(cos) - k * MAD(cos)
DISTANCE_FACTOR = 3.0      # reject if distance-to-median > median + k * MAD


class DisclosureLevel(Enum):
    """How much the committee is shown. Values are stable ids used in result tables."""

    E0 = "E0"  # commitment only
    E1 = "E1"  # norm
    E2 = "E2"  # norm + cosine
    E3 = "E3"  # random-projection sketch
    E4 = "E4"  # full plaintext


@dataclass(frozen=True)
class Evidence:
    """What one committee member receives about one submission."""

    level: DisclosureLevel
    commitment: bytes
    norm: float | None = None
    cosine: float | None = None
    vector: np.ndarray | None = None  # sketch (E3) or full update (E4)

    def size_bytes(self) -> int:
        """Bytes disclosed -- the communication cost of this rung."""
        size = len(self.commitment)
        if self.norm is not None:
            size += 4
        if self.cosine is not None:
            size += 4
        if self.vector is not None:
            size += self.vector.size * 4
        return size

    def digest(self) -> bytes:
        """Digest recorded in the transcript, binding what the committee was shown."""
        parts = [self.level.value.encode(), self.commitment]
        if self.norm is not None:
            parts.append(np.float32(self.norm).tobytes())
        if self.cosine is not None:
            parts.append(np.float32(self.cosine).tobytes())
        if self.vector is not None:
            parts.append(self.vector.astype(np.float32).tobytes())
        return hashlib.sha256(b"BCFLSRV/evidence/v1" + b"".join(parts)).digest()


def _projection(dim: int, out_dim: int, seed: int) -> np.ndarray:
    """Seeded Gaussian random projection, shared by clients and committee.

    Both sides must derive the identical matrix or the sketches are incomparable, so
    it comes from a seed recorded in the round context rather than from local
    randomness.
    """
    rng = np.random.default_rng(seed)
    return rng.standard_normal((out_dim, dim)).astype(np.float32) / np.sqrt(out_dim)


def encode_evidence(
    level: DisclosureLevel,
    update: np.ndarray,
    prev_global_update: np.ndarray | None,
    projection_seed: int,
) -> Evidence:
    """Build the evidence a client discloses at ``level``.

    Args:
        level: disclosure rung.
        update: the client's flat update vector.
        prev_global_update: last round's aggregated update, used for the E2 cosine.
            ``None`` in round 0, where the cosine is defined as 0.0.
        projection_seed: seed for the E3 sketch, derived from round context.
    """
    commitment = hashlib.sha256(
        b"BCFLSRV/update-commit/v1" + update.astype(np.float32).tobytes()
    ).digest()

    if level is DisclosureLevel.E0:
        return Evidence(level, commitment)

    norm = float(np.linalg.norm(update))

    if level is DisclosureLevel.E1:
        return Evidence(level, commitment, norm=norm)

    if level is DisclosureLevel.E2:
        cosine = 0.0
        if prev_global_update is not None:
            denominator = norm * float(np.linalg.norm(prev_global_update))
            if denominator > 1e-12:
                cosine = float(np.dot(update, prev_global_update) / denominator)
        return Evidence(level, commitment, norm=norm, cosine=cosine)

    if level is DisclosureLevel.E3:
        sketch = _projection(update.size, SKETCH_DIM, projection_seed) @ update
        return Evidence(level, commitment, norm=norm, vector=sketch.astype(np.float32))

    if level is DisclosureLevel.E4:
        return Evidence(level, commitment, norm=norm, vector=update.astype(np.float32))

    raise ValueError(f"unhandled disclosure level: {level}")


def rule_id_for(level: DisclosureLevel) -> str:
    """Stable identifier recorded in the admission set (AG1 requires a declared rule)."""
    return {
        DisclosureLevel.E0: "admit-all/v1",
        DisclosureLevel.E1: f"norm-bound-{NORM_FACTOR}x-median/v1",
        DisclosureLevel.E2: f"norm-{NORM_FACTOR}x+cosine-median-{COSINE_MAD_FACTOR}mad/v1",
        DisclosureLevel.E3: f"sketch{SKETCH_DIM}-dist-median+{DISTANCE_FACTOR}mad/v1",
        DisclosureLevel.E4: f"full-dist-median+{DISTANCE_FACTOR}mad/v1",
    }[level]


@dataclass(frozen=True)
class AdmissionDecision:
    """Which clients the rule admits, and the thresholds it used.

    Thresholds are returned because the slow-drift attacker in E-5 is assumed to know
    them (worst case for us), and because recording them makes the decision
    reproducible by an auditor.
    """

    admitted: Tuple[str, ...]
    rejected: Tuple[str, ...]
    rule_id: str
    thresholds: Dict[str, float]


def _mad_threshold(values: np.ndarray, factor: float) -> float:
    """median + factor * MAD -- a robust cutoff that a few outliers cannot drag."""
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad <= 1e-12:  # degenerate spread: fall back to a relative margin
        return median * (1.0 + factor * 0.1) + 1e-9
    return median + factor * mad


def apply_rule(
    level: DisclosureLevel,
    evidences: Dict[str, Evidence],
) -> AdmissionDecision:
    """Apply the declared rule for ``level`` to this round's evidence.

    Deterministic given the same inputs -- this is what an auditor re-checks.
    """
    rule_id = rule_id_for(level)
    client_ids = sorted(evidences)
    if not client_ids:
        return AdmissionDecision((), (), rule_id, {})

    if level is DisclosureLevel.E0:
        return AdmissionDecision(tuple(client_ids), (), rule_id, {})

    norms = np.array([evidences[c].norm or 0.0 for c in client_ids])
    norm_threshold = float(np.median(norms)) * NORM_FACTOR
    thresholds: Dict[str, float] = {"norm": norm_threshold}
    rejected = {c for c, n in zip(client_ids, norms) if n > norm_threshold}

    if level is DisclosureLevel.E2:
        cosines = np.array([evidences[c].cosine or 0.0 for c in client_ids])
        cos_median = float(np.median(cosines))
        cos_mad = float(np.median(np.abs(cosines - cos_median)))
        # A sign-flipped update has cosine ~= -cos(honest), a clear low outlier.
        # An honest non-IID client sits inside the spread rather than below it.
        cos_threshold = cos_median - COSINE_MAD_FACTOR * max(cos_mad, 1e-6)
        thresholds["cosine"] = cos_threshold
        rejected |= {
            c for c, v in zip(client_ids, cosines) if v < cos_threshold
        }

    if level in (DisclosureLevel.E3, DisclosureLevel.E4):
        matrix = np.stack([evidences[c].vector for c in client_ids])
        median_vector = np.median(matrix, axis=0)
        distances = np.linalg.norm(matrix - median_vector, axis=1)
        distance_threshold = _mad_threshold(distances, DISTANCE_FACTOR)
        thresholds["distance"] = distance_threshold
        rejected |= {
            c for c, d in zip(client_ids, distances) if d > distance_threshold
        }

    admitted = tuple(c for c in client_ids if c not in rejected)
    return AdmissionDecision(admitted, tuple(sorted(rejected)), rule_id, thresholds)
