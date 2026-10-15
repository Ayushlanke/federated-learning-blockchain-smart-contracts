"""Simplified additive masking -- what the aggregator is prevented from seeing.

TERMINOLOGY, BINDING (`D-010`, `E4_E5_MATRIX.md` section 9)
-----------------------------------------------------------
This is **simplified additive masking with no dropout recovery**. It is *not*
production secure aggregation and must never be described as such.

What it does implement:
  * pairwise masks from a shared seed, cancelling exactly in the sum
  * the aggregator observes only masked vectors and their sum

What it does NOT implement, and what we therefore do not claim:
  * Diffie-Hellman key agreement (seeds are handed out by the simulation)
  * Shamir secret sharing of seeds
  * **dropout recovery** -- if a client vanishes mid-round its mask never cancels,
    and the round is aborted rather than repaired
  * defences against a malicious server (e.g. the model-inconsistency attack of
    Pasquini et al., CCS 2022 `LIT`)

Why it is built at all
----------------------
It is the premise of the entire design. If the aggregator could simply look at every
update, there would be no reason for a committee or an evidence ladder. Implementing
it -- minimally -- turns that premise from an assumption into a **tested property**.

It does **not** affect any E-4/E-5 metric: masking changes what the *aggregator*
sees, while the admission rule operates on what the *committee* sees. The experiments
would produce identical numbers without it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

__all__ = [
    "MaskingError",
    "MASK_SCALE",
    "pairwise_mask",
    "mask_updates",
    "aggregate_masked",
    "aggregate_masked_mean",
]

_MASK_DOMAIN = b"BCFLSRV/mask/v1"

# Mask magnitude relative to a typical update coordinate.
#
# WHY THIS CONSTANT EXISTS. A unit-scale Gaussian mask does NOT hide a unit-scale
# update: with k other participants the masked vector has variance 1 + k, so its
# correlation with the true update is 1/sqrt(1+k) -- measured at 0.58 for k=4 by
# test_masked_vector_hides_the_update. Real secure aggregation avoids this entirely
# by masking with uniform values over a large modular field, which hides
# information-theoretically. This construction does not do that, so it compensates
# with scale: masks are MASK_SCALE times larger than typical update coordinates,
# driving the correlation down to roughly 1/(MASK_SCALE * sqrt(k)).
#
# The cost is floating-point precision. Masks cancel exactly in real arithmetic, but
# in float32 the sum loses roughly log10(MASK_SCALE) significant digits. 100 keeps
# the reconstruction error near 1e-4 relative, which is far below the scale at which
# any admission rule operates. This trade-off is measured, not assumed --
# see test_masked_sum_precision_is_acceptable.
#
# This is STATISTICAL hiding with a precision cost, not the information-theoretic
# hiding of production SecAgg. The distinction is stated wherever results are reported.
MASK_SCALE = 100.0


class MaskingError(Exception):
    """Masking precondition violated (e.g. a participant dropped out)."""


def _seed_for_pair(a: str, b: str, round_id: int) -> int:
    """Deterministic shared seed for an unordered client pair.

    Sorting the ids means both sides derive the same seed without negotiating an
    order, and the round id keeps masks from repeating across rounds -- reuse would
    let an observer cancel them by subtracting two rounds.
    """
    lo, hi = sorted((a, b))
    digest = hashlib.sha256(
        _MASK_DOMAIN + round_id.to_bytes(8, "big") + lo.encode() + b"|" + hi.encode()
    ).digest()
    return int.from_bytes(digest[:8], "big")


def pairwise_mask(a: str, b: str, round_id: int, dim: int) -> np.ndarray:
    """Mask that client ``a`` adds and client ``b`` subtracts (antisymmetric).

    Because the pair seed is symmetric but the sign is decided by id order, the two
    masks are exact negatives and cancel when both clients are present.
    """
    if a == b:
        raise MaskingError("a client cannot pair with itself")
    rng = np.random.default_rng(_seed_for_pair(a, b, round_id))
    mask = (rng.standard_normal(dim) * MASK_SCALE).astype(np.float32)
    return mask if a < b else -mask


def mask_updates(
    updates: Dict[str, np.ndarray], round_id: int
) -> Dict[str, np.ndarray]:
    """Mask every update. The aggregator sees only these.

    Each client adds one mask per other participant. All masks cancel in the sum, so
    the aggregate is exact while no individual masked vector reveals its update.
    """
    client_ids = sorted(updates)
    if len(client_ids) < 2:
        raise MaskingError("masking requires at least two participants")
    dims = {u.size for u in updates.values()}
    if len(dims) != 1:
        raise MaskingError(f"updates have inconsistent dimensions: {dims}")
    dim = dims.pop()

    masked: Dict[str, np.ndarray] = {}
    for me in client_ids:
        acc = updates[me].astype(np.float32).copy()
        for other in client_ids:
            if other != me:
                acc += pairwise_mask(me, other, round_id, dim)
        masked[me] = acc
    return masked


def aggregate_masked(
    masked: Dict[str, np.ndarray], expected_participants: Sequence[str]
) -> np.ndarray:
    """Sum masked updates. Masks cancel only if EVERY participant is present.

    Raises:
        MaskingError: if a participant is missing. Without dropout recovery the sum
            would silently contain uncancelled mask noise, so this fails loudly
            rather than returning a corrupted aggregate. Aborting the round is the
            documented behaviour (``PROJECT_MASTER_SPEC.md`` section 9).
    """
    expected = set(expected_participants)
    present = set(masked)
    if present != expected:
        missing = sorted(expected - present)
        extra = sorted(present - expected)
        raise MaskingError(
            f"mask cancellation requires exactly the expected participants; "
            f"missing={missing} unexpected={extra}"
        )
    return np.stack([masked[c] for c in sorted(masked)]).sum(axis=0)


def aggregate_masked_mean(
    masked: Dict[str, np.ndarray], expected_participants: Sequence[str]
) -> np.ndarray:
    """Mean of the underlying updates, computed from masked inputs alone."""
    total = aggregate_masked(masked, expected_participants)
    return (total / len(expected_participants)).astype(np.float32)
