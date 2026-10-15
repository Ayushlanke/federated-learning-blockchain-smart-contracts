"""Verifiable committee sortition, and the analytic corruption model for E-3.

BC-FL-SRV requirement coverage: FR-5 (committee derived from the prior transcript
root), RC-2 (sortition with configurable size), and the analytic half of experiment
E-3 (soundness vs committee corruption).

Why the seed is the previous transcript root
--------------------------------------------
The committee for round ``t`` is derived from the Merkle root as it stood at the end
of round ``t-1``. Three properties follow, and all three are load-bearing:

1. **Recomputable.** Any auditor holding the transcript derives the same committee.
   Committee membership therefore needs no separate trusted announcement -- it is a
   function of published history.
2. **History-binding.** Rewriting any past entry changes the root, which changes every
   subsequent committee. An adversary cannot quietly revise history and keep the
   committees that history produced.
3. **Grinding-resistant, to a point.** The aggregator cannot freely search for a
   favourable committee without changing the transcript, which is itself detectable.

**Honest limitation.** This is *not* a VRF and provides no unpredictability against a
party who can choose what goes into the transcript. An aggregator that controls entry
ordering retains some influence over the next root and therefore some grinding power.
Measuring that is exactly what the grinding attack in experiment E-3 is for; the claim
here is recomputability and history-binding, not unpredictability.

Why unbiased sampling matters
-----------------------------
``hash(x) % n`` is biased whenever ``n`` does not divide the hash range: low indices
get selected slightly more often. That bias would show up in E-3 as a mismatch between
empirical and analytic corruption probability, and would be easy to misread as a
finding about the protocol rather than a bug in the sampler. Rejection sampling is used
instead, and a statistical uniformity test guards it.
"""

from __future__ import annotations

import hashlib
from math import comb
from typing import Final, List, Sequence, Tuple

__all__ = [
    "derive_seed",
    "select_committee",
    "corruption_probability",
    "smallest_safe_committee",
]

_SEED_DOMAIN: Final = b"BCFLSRV/sortition/v1"
_STREAM_DOMAIN: Final = b"BCFLSRV/sortition-stream/v1"
_WORD_BYTES: Final = 8
_WORD_MAX: Final = 1 << (8 * _WORD_BYTES)


def derive_seed(prev_root: bytes, round_id: int, entropy: bytes = b"") -> bytes:
    """Committee seed for ``round_id``, bound to prior history and prior signatures.

    Args:
        prev_root: transcript root at the end of the previous round.
        round_id: the round this committee serves.
        entropy: **grinding mitigation.** Additional seed material the aggregator
            cannot choose -- in BC-FL-SRV this is a digest of the *previous round's
            committee attestation signatures*.

    Why ``entropy`` exists
    ----------------------
    Experiment E-3d found that ``prev_root`` alone is a weak seed. The aggregator has
    freedom over what enters the transcript (entry ordering above all), so it can try
    many candidate histories offline and publish only the one yielding the most
    corrupt committee. Measured amplification at 20% corruption was ~192x with only
    256 attempts against a committee of 9.

    Mixing in the previous round's *signatures* removes most of that freedom: the
    aggregator cannot forge them, so to vary the seed it must get the previous
    committee to sign a different admission set. If that committee was honest, there
    is exactly one signature set and the grinding budget collapses to one attempt.

    **This does not make the sortition a VRF.** An aggregator that has already
    compromised a round can grind the next one, and dropping clients still perturbs
    the seed (at the cost of being detectable by those clients). The residual
    weakness is stated in E3_FINDINGS.md rather than papered over.
    """
    if not isinstance(prev_root, (bytes, bytearray)):
        raise TypeError(f"prev_root must be bytes, got {type(prev_root)!r}")
    if not isinstance(entropy, (bytes, bytearray)):
        raise TypeError(f"entropy must be bytes, got {type(entropy)!r}")
    if round_id < 0:
        raise ValueError(f"round_id must be non-negative, got {round_id}")
    return hashlib.sha256(
        _SEED_DOMAIN
        + round_id.to_bytes(8, "big")
        + len(prev_root).to_bytes(8, "big")
        + bytes(prev_root)
        + len(entropy).to_bytes(8, "big")
        + bytes(entropy)
    ).digest()


class _PRFStream:
    """Deterministic byte stream: SHA-256 in counter mode over a seed.

    Used instead of :mod:`random` so results are reproducible across Python versions
    and platforms -- a requirement for the reproducibility contract in
    EVALUATION_PLAN.md section 6.
    """

    __slots__ = ("_seed", "_counter", "_buffer")

    def __init__(self, seed: bytes) -> None:
        self._seed = bytes(seed)
        self._counter = 0
        self._buffer = b""

    def _refill(self) -> None:
        self._buffer += hashlib.sha256(
            _STREAM_DOMAIN + self._seed + self._counter.to_bytes(8, "big")
        ).digest()
        self._counter += 1

    def _word(self) -> int:
        while len(self._buffer) < _WORD_BYTES:
            self._refill()
        chunk, self._buffer = self._buffer[:_WORD_BYTES], self._buffer[_WORD_BYTES:]
        return int.from_bytes(chunk, "big")

    def below(self, k: int) -> int:
        """Uniform integer in ``[0, k)`` via rejection sampling -- no modulo bias."""
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        if k == 1:
            return 0
        limit = _WORD_MAX - (_WORD_MAX % k)  # largest multiple of k that fits
        while True:
            value = self._word()
            if value < limit:
                return value % k


def select_committee(
    prev_root: bytes,
    round_id: int,
    population: Sequence[str],
    size: int,
    entropy: bytes = b"",
) -> Tuple[str, ...]:
    """Select ``size`` distinct members, deterministically and verifiably.

    The population is sorted internally, so the result does not depend on the order in
    which the caller happened to enumerate clients. Without this an auditor could
    reconstruct a *different* committee from the same transcript purely because it
    iterated a set in a different order -- which would break verifiability in a way
    that is maddening to debug.

    Args:
        prev_root: Merkle root at the end of the previous round.
        round_id: Round this committee serves.
        population: Eligible client identifiers. Duplicates are rejected.
        size: Committee size.

    Returns:
        The committee, in selection order (which is itself deterministic).

    Raises:
        ValueError: on duplicate ids, non-positive size, or size > population.
    """
    pool: List[str] = sorted(population)
    n = len(pool)
    if len(set(pool)) != n:
        raise ValueError("population contains duplicate identifiers")
    if size <= 0:
        raise ValueError(f"committee size must be positive, got {size}")
    if size > n:
        raise ValueError(f"committee size {size} exceeds population {n}")

    rng = _PRFStream(derive_seed(prev_root, round_id, entropy))
    # Partial Fisher-Yates: correct and unbiased given an unbiased `below`.
    for i in range(size):
        j = i + rng.below(n - i)
        pool[i], pool[j] = pool[j], pool[i]
    return tuple(pool[:size])


def corruption_probability(
    population: int,
    corrupt: int,
    committee_size: int,
    threshold: int,
) -> float:
    """P(a corrupt coalition holds >= ``threshold`` committee seats).

    Sortition draws ``committee_size`` members without replacement from a population
    containing ``corrupt`` adversaries, so seat count is **hypergeometric**. This is
    the analytic curve that experiment E-3 checks its empirical sampling against; a
    mismatch means the sampler is biased, not that the protocol is unsound.

    Returns:
        Probability in [0, 1]. Returns 0.0 when the threshold is unreachable.
    """
    if not 0 <= corrupt <= population:
        raise ValueError(f"corrupt must be in [0, {population}], got {corrupt}")
    if not 0 < committee_size <= population:
        raise ValueError(
            f"committee_size must be in (0, {population}], got {committee_size}"
        )
    if threshold <= 0:
        return 1.0
    if threshold > min(committee_size, corrupt):
        return 0.0

    total = comb(population, committee_size)
    hi = min(committee_size, corrupt)
    favourable = sum(
        comb(corrupt, k) * comb(population - corrupt, committee_size - k)
        for k in range(threshold, hi + 1)
    )
    return favourable / total


def smallest_safe_committee(
    population: int,
    corrupt: int,
    max_forge_probability: float,
    threshold_fraction: float = 2 / 3,
    max_size: int | None = None,
) -> int | None:
    """Smallest odd committee size whose forge probability stays under the bound.

    This is the practical output of E-3: rather than guessing a committee size, a
    deployment can *choose* one for a stated corruption assumption and risk budget.

    Returns:
        The committee size, or ``None`` if no size within the population achieves it
        -- which is itself a meaningful result and must be reported, not hidden.
    """
    if not 0 < max_forge_probability < 1:
        raise ValueError("max_forge_probability must be in (0, 1)")
    ceiling = min(max_size or population, population)
    for size in range(3, ceiling + 1, 2):
        threshold = -(-int(size * threshold_fraction * 1000) // 1000)  # ceil, no float drift
        threshold = max(1, min(size, threshold))
        if corruption_probability(population, corrupt, size, threshold) <= max_forge_probability:
            return size
    return None
