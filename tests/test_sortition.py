"""Tests for verifiable committee sortition (FR-5, RC-2) and the E-3 analytic model.

Three groups matter here:

* **Verifiability** -- an auditor must recompute the same committee from the
  transcript, regardless of how it enumerated the population.
* **History-binding** -- changing the past must change every later committee.
* **Statistical correctness** -- the sampler must be unbiased, and the empirical
  corruption rate must match the hypergeometric prediction. If the sampler is
  biased, E-3 would show a protocol "finding" that is really a bug.
"""

from __future__ import annotations

import statistics
from collections import Counter

import pytest

from bcflsrv.crypto.sortition import (
    _PRFStream,
    corruption_probability,
    derive_seed,
    select_committee,
    smallest_safe_committee,
)

ROOT_A = bytes.fromhex("11" * 32)
ROOT_B = bytes.fromhex("22" * 32)
POP = tuple(f"client-{i:03d}" for i in range(50))


# --------------------------------------------------------------------------
# 1. Determinism and verifiability
# --------------------------------------------------------------------------

def test_committee_is_deterministic():
    a = select_committee(ROOT_A, 7, POP, 9)
    b = select_committee(ROOT_A, 7, POP, 9)
    assert a == b


def test_committee_is_independent_of_population_ordering():
    """An auditor iterating clients in a different order must get the same committee."""
    shuffled = tuple(reversed(POP))
    assert select_committee(ROOT_A, 3, POP, 7) == select_committee(ROOT_A, 3, shuffled, 7)


def test_committee_has_correct_size_and_no_duplicates():
    for size in (1, 3, 9, 25, len(POP)):
        c = select_committee(ROOT_A, 1, POP, size)
        assert len(c) == size
        assert len(set(c)) == size
        assert set(c) <= set(POP)


def test_seed_is_deterministic_and_context_bound():
    assert derive_seed(ROOT_A, 5) == derive_seed(ROOT_A, 5)
    assert derive_seed(ROOT_A, 5) != derive_seed(ROOT_A, 6)
    assert derive_seed(ROOT_A, 5) != derive_seed(ROOT_B, 5)


def test_seed_rejects_bad_input():
    with pytest.raises(TypeError):
        derive_seed("not bytes", 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        derive_seed(ROOT_A, -1)


# --------------------------------------------------------------------------
# 2. History-binding -- the property that makes the ledger load-bearing
# --------------------------------------------------------------------------

def test_different_root_gives_different_committee():
    """Rewriting history must change who audits the next round."""
    assert select_committee(ROOT_A, 4, POP, 9) != select_committee(ROOT_B, 4, POP, 9)


def test_different_round_gives_different_committee():
    """Committees rotate; a fixed committee would be a standing target for bribery."""
    committees = {select_committee(ROOT_A, r, POP, 9) for r in range(20)}
    assert len(committees) >= 18, "committees should rotate across rounds"


def test_single_bit_root_change_changes_the_committee():
    flipped = bytearray(ROOT_A)
    flipped[0] ^= 0x01
    assert select_committee(ROOT_A, 1, POP, 9) != select_committee(bytes(flipped), 1, POP, 9)


# --------------------------------------------------------------------------
# 3. Input validation
# --------------------------------------------------------------------------

def test_rejects_oversized_committee():
    with pytest.raises(ValueError):
        select_committee(ROOT_A, 1, POP, len(POP) + 1)


def test_rejects_non_positive_size():
    for bad in (0, -3):
        with pytest.raises(ValueError):
            select_committee(ROOT_A, 1, POP, bad)


def test_rejects_duplicate_population_ids():
    with pytest.raises(ValueError):
        select_committee(ROOT_A, 1, ("a", "b", "a"), 2)


# --------------------------------------------------------------------------
# 4. Statistical correctness of the sampler
# --------------------------------------------------------------------------

def test_prf_below_is_unbiased():
    """Guards against modulo bias, which would silently corrupt E-3 results.

    k = 3 does not divide 2**64, so a naive `word % k` would over-select index 0.
    """
    rng = _PRFStream(b"uniformity-seed")
    k, draws = 3, 60_000
    counts = Counter(rng.below(k) for _ in range(draws))
    expected = draws / k
    for value in range(k):
        deviation = abs(counts[value] - expected) / expected
        assert deviation < 0.03, f"index {value} deviates {deviation:.3%} -- possible bias"


def test_prf_below_edge_cases():
    rng = _PRFStream(b"seed")
    assert rng.below(1) == 0
    for bad in (0, -1):
        with pytest.raises(ValueError):
            rng.below(bad)


def test_membership_is_uniform_across_the_population():
    """Every client should serve on roughly the same number of committees."""
    size, rounds = 9, 4000
    counts = Counter()
    for r in range(rounds):
        counts.update(select_committee(ROOT_A, r, POP, size))

    expected = rounds * size / len(POP)
    assert len(counts) == len(POP), "every client should be selected at least once"
    spread = max(counts.values()) - min(counts.values())
    assert spread < 0.35 * expected, f"selection spread {spread} too wide vs {expected:.0f}"
    assert abs(statistics.mean(counts.values()) - expected) < 1e-6


# --------------------------------------------------------------------------
# 5. The analytic corruption model (E-3)
# --------------------------------------------------------------------------

def test_corruption_probability_boundary_cases():
    assert corruption_probability(50, 0, 9, 5) == 0.0          # no adversaries
    assert corruption_probability(50, 50, 9, 5) == 1.0         # everyone corrupt
    assert corruption_probability(50, 10, 9, 10) == 0.0        # threshold unreachable
    assert corruption_probability(50, 10, 9, 0) == 1.0         # trivial threshold


def test_corruption_probability_is_monotonic_in_corruption():
    probs = [corruption_probability(50, c, 9, 5) for c in range(0, 51, 5)]
    assert probs == sorted(probs), "more adversaries must never reduce forge probability"


def test_corruption_probability_falls_as_committee_grows():
    """The core design lever: bigger committees are harder to capture."""
    p_small = corruption_probability(100, 20, 5, 4)     # 4/5 needed
    p_large = corruption_probability(100, 20, 15, 10)   # 10/15 needed
    assert p_large < p_small


def test_corruption_probability_validates_inputs():
    for args in [(50, 60, 9, 5), (50, -1, 9, 5), (50, 10, 0, 5), (50, 10, 51, 5)]:
        with pytest.raises(ValueError):
            corruption_probability(*args)


def test_empirical_sortition_matches_the_hypergeometric_model():
    """The key E-3 sanity check: sampling must agree with the analytic curve.

    A mismatch here means the sampler is biased. Catching that in a unit test is the
    difference between reporting a protocol result and reporting a bug.
    """
    population, n_corrupt, size, threshold, trials = 50, 15, 9, 5, 6000
    corrupt_set = set(POP[:n_corrupt])

    hits = sum(
        1
        for r in range(trials)
        if len(corrupt_set & set(select_committee(ROOT_A, r, POP, size))) >= threshold
    )
    empirical = hits / trials
    analytic = corruption_probability(population, n_corrupt, size, threshold)

    # ~3 sigma for a binomial proportion at this sample size.
    sigma = (analytic * (1 - analytic) / trials) ** 0.5
    assert abs(empirical - analytic) < max(3 * sigma, 0.01), (
        f"empirical {empirical:.4f} vs analytic {analytic:.4f}"
    )


def test_smallest_safe_committee_finds_a_workable_size():
    size = smallest_safe_committee(population=50, corrupt=10, max_forge_probability=0.01)
    assert size is not None and size % 2 == 1
    # And it really is safe at the 2/3 threshold it assumes.
    threshold = -(-size * 2 // 3)
    assert corruption_probability(50, 10, size, threshold) <= 0.01


def test_smallest_safe_committee_returns_none_when_impossible():
    """A heavily corrupted population admits no safe size -- report it, do not hide it."""
    assert smallest_safe_committee(
        population=50, corrupt=45, max_forge_probability=1e-6
    ) is None


def test_smallest_safe_committee_validates_probability():
    for bad in (0.0, 1.0, -0.5, 2.0):
        with pytest.raises(ValueError):
            smallest_safe_committee(50, 10, bad)


def test_smallest_safe_committee_respects_max_size():
    assert smallest_safe_committee(
        population=50, corrupt=20, max_forge_probability=1e-9, max_size=5
    ) is None


# --------------------------------------------------------------------------
# 6. Grinding mitigation (D-011): seed entropy from prior attestation signatures
# --------------------------------------------------------------------------
# E-3d measured ~192x amplification of forge probability when an aggregator could
# grind the sortition seed by republishing candidate transcripts. Mixing in the
# previous round's SIGNATURES removes most of that freedom, because the aggregator
# cannot forge them. These tests pin the mechanism down.

def test_entropy_changes_the_committee():
    a = select_committee(ROOT_A, 5, POP, 9, entropy=b"")
    b = select_committee(ROOT_A, 5, POP, 9, entropy=b"sig-digest-1")
    c = select_committee(ROOT_A, 5, POP, 9, entropy=b"sig-digest-2")
    assert a != b and b != c and a != c


def test_entropy_is_deterministic():
    args = (ROOT_A, 5, POP, 9)
    assert select_committee(*args, entropy=b"x") == select_committee(*args, entropy=b"x")


def test_seed_length_prefixing_prevents_field_boundary_confusion():
    """Without length prefixes, moving a byte from root into entropy would collide.

    (root = A*31 + B, entropy = b"") and (root = A*31, entropy = b"B") concatenate to
    the same string; the length prefix is what keeps them distinct.
    """
    root_long = b"A" * 31 + b"B"
    assert derive_seed(root_long, 1, b"") != derive_seed(b"A" * 31 + b"\x00", 1, b"B")
    # And entropy length alone must matter.
    assert derive_seed(b"\x01" * 32, 1, b"XY") != derive_seed(b"\x01" * 32, 1, b"X")


def test_seed_rejects_non_bytes_entropy():
    with pytest.raises(TypeError):
        derive_seed(ROOT_A, 1, "not bytes")  # type: ignore[arg-type]


def test_empty_entropy_matches_the_default():
    """Round 0 has no predecessor, so it must behave exactly as before the change."""
    assert select_committee(ROOT_A, 0, POP, 9) == select_committee(ROOT_A, 0, POP, 9, entropy=b"")


def test_attestation_entropy_is_signature_order_independent():
    """Signature ORDER is an aggregator-controlled lever; sorting removes it."""
    from bcflsrv.crypto.identity import Identity, SigContext
    from bcflsrv.protocol.admission import Attestation, attestation_entropy

    members = [Identity.from_seed(b"m%d" % i) for i in range(5)]
    digest = bytes(32)
    sigs = tuple((m.public_key, m.sign(SigContext.ATTESTATION, digest)) for m in members)
    forward = Attestation(1, digest, sigs)
    backward = Attestation(1, digest, tuple(reversed(sigs)))
    assert attestation_entropy(forward) == attestation_entropy(backward)


def test_attestation_entropy_changes_with_signers_and_round():
    from bcflsrv.crypto.identity import Identity, SigContext
    from bcflsrv.protocol.admission import Attestation, attestation_entropy

    members = [Identity.from_seed(b"m%d" % i) for i in range(5)]
    digest = bytes(32)
    sigs = tuple((m.public_key, m.sign(SigContext.ATTESTATION, digest)) for m in members)
    full = Attestation(1, digest, sigs)
    fewer = Attestation(1, digest, sigs[:4])
    later = Attestation(2, digest, sigs)
    assert attestation_entropy(full) != attestation_entropy(fewer)
    assert attestation_entropy(full) != attestation_entropy(later)


def test_attestation_entropy_of_none_is_empty():
    """Round 0 has no predecessor."""
    from bcflsrv.protocol.admission import attestation_entropy

    assert attestation_entropy(None) == b""
