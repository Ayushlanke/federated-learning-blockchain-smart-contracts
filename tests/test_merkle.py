"""Tests for the RFC 6962 Merkle transcript primitives (FR-1, FR-2, FR-3).

Testing strategy
----------------
Two kinds of test, and the distinction matters for what may be claimed later.

1. **Definitional conformance.** The small cases (empty / 1 leaf / 2 leaves) are
   checked against the RFC 6962 definitions written out by hand. These confirm the
   implementation computes what the specification says, not merely what it computes.

2. **Adversarial properties.** Every mutation an append-only log is supposed to
   forbid -- edit, delete, reorder, truncate, forge a proof -- is asserted to make
   verification FAIL. A proof system tested only on honest inputs has not been
   tested at all; these are the tests that give FR-1/2/3 meaning.

HONEST LIMITATION: these tests establish internal consistency and conformance to the
RFC's recursive definition. They do NOT cross-check against an independent RFC 6962
implementation (e.g. a live CT log's published roots). Until that is done, "matches
RFC 6962" is VERIFIED-BY-DEFINITION, not VERIFIED-BY-INTEROP. Tracked as tech debt.
"""

from __future__ import annotations

import hashlib

import pytest

from bcflsrv.ledger.merkle import (
    EMPTY_ROOT,
    consistency_proof,
    hash_children,
    hash_leaf,
    inclusion_proof,
    merkle_root,
    verify_consistency,
    verify_inclusion,
)

MAX_N = 33  # exercises sizes either side of the powers of two 1, 2, 4, 8, 16, 32


def leaves(n: int) -> list[bytes]:
    return [hash_leaf(b"entry-%d" % i) for i in range(n)]


# --------------------------------------------------------------------------
# 1. Definitional conformance
# --------------------------------------------------------------------------

def test_empty_tree_root_is_sha256_of_empty_string():
    assert merkle_root([]) == hashlib.sha256(b"").digest()
    assert EMPTY_ROOT == hashlib.sha256(b"").digest()


def test_single_leaf_root_is_the_leaf_hash():
    assert merkle_root([hash_leaf(b"a")]) == hash_leaf(b"a")


def test_two_leaf_root_matches_hand_computed_definition():
    la, lb = hash_leaf(b"a"), hash_leaf(b"b")
    assert merkle_root([la, lb]) == hashlib.sha256(b"\x01" + la + lb).digest()


def test_leaf_and_node_hashing_are_domain_separated():
    """A leaf hash must never collide with an internal node hash by construction."""
    assert hash_leaf(b"") == hashlib.sha256(b"\x00").digest()
    assert hash_children(b"", b"") == hashlib.sha256(b"\x01").digest()
    assert hash_leaf(b"") != hash_children(b"", b"")


def test_root_is_order_sensitive():
    a, b = hash_leaf(b"a"), hash_leaf(b"b")
    assert merkle_root([a, b]) != merkle_root([b, a])


# --------------------------------------------------------------------------
# 2. Inclusion proofs (FR-2)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("n", range(1, MAX_N))
def test_inclusion_proof_verifies_for_every_leaf(n):
    ls = leaves(n)
    root = merkle_root(ls)
    for i in range(n):
        proof = inclusion_proof(ls, i)
        assert verify_inclusion(ls[i], i, n, proof, root), f"failed at n={n}, i={i}"


@pytest.mark.parametrize("n", range(1, MAX_N))
def test_inclusion_proof_size_is_logarithmic(n):
    """FR-2 requires O(log n) proofs -- the property that lets an auditor check
    inclusion without holding the transcript."""
    ls = leaves(n)
    bound = max(1, n - 1).bit_length()
    for i in range(n):
        assert len(inclusion_proof(ls, i)) <= bound


def test_inclusion_fails_when_the_leaf_is_altered():
    ls = leaves(8)
    root = merkle_root(ls)
    proof = inclusion_proof(ls, 3)
    assert not verify_inclusion(hash_leaf(b"forged"), 3, 8, proof, root)


def test_inclusion_fails_at_the_wrong_index():
    ls = leaves(8)
    root = merkle_root(ls)
    proof = inclusion_proof(ls, 3)
    assert not verify_inclusion(ls[3], 4, 8, proof, root)


def test_inclusion_fails_against_a_different_root():
    ls = leaves(8)
    proof = inclusion_proof(ls, 3)
    assert not verify_inclusion(ls[3], 3, 8, proof, merkle_root(leaves(9)))


def test_inclusion_fails_when_a_proof_node_is_tampered():
    ls = leaves(16)
    root = merkle_root(ls)
    proof = inclusion_proof(ls, 5)
    tampered = list(proof)
    tampered[0] = hashlib.sha256(b"evil").digest()
    assert not verify_inclusion(ls[5], 5, 16, tampered, root)


def test_inclusion_fails_on_truncated_or_padded_proof():
    ls = leaves(16)
    root = merkle_root(ls)
    proof = inclusion_proof(ls, 5)
    assert not verify_inclusion(ls[5], 5, 16, proof[:-1], root)
    assert not verify_inclusion(ls[5], 5, 16, list(proof) + [EMPTY_ROOT], root)


def test_inclusion_rejects_out_of_range_and_empty_tree():
    ls = leaves(4)
    root = merkle_root(ls)
    assert not verify_inclusion(ls[0], 4, 4, inclusion_proof(ls, 0), root)
    assert not verify_inclusion(ls[0], -1, 4, [], root)
    assert not verify_inclusion(ls[0], 0, 0, [], EMPTY_ROOT)


def test_inclusion_proof_raises_on_bad_index():
    with pytest.raises(IndexError):
        inclusion_proof(leaves(4), 9)


# --------------------------------------------------------------------------
# 3. Consistency proofs (FR-1, FR-3) -- the append-only property
# --------------------------------------------------------------------------

@pytest.mark.parametrize("n", range(1, 25))
def test_consistency_holds_for_every_prefix(n):
    ls = leaves(n)
    new_root = merkle_root(ls)
    for m in range(n + 1):
        old_root = merkle_root(ls[:m])
        proof = consistency_proof(ls, m, n)
        assert verify_consistency(old_root, new_root, m, n, proof), f"n={n}, m={m}"


def test_consistency_of_a_tree_with_itself_needs_no_proof():
    ls = leaves(7)
    r = merkle_root(ls)
    assert verify_consistency(r, r, 7, 7, [])
    assert not verify_consistency(r, merkle_root(leaves(8)), 7, 7, [])


def test_consistency_fails_when_history_is_edited_in_place():
    """The core FR-1 guarantee: you cannot rewrite the past and still look append-only."""
    original = leaves(16)
    old_root = merkle_root(original[:8])
    edited = list(original)
    edited[3] = hash_leaf(b"rewritten-history")
    proof = consistency_proof(edited, 8, 16)
    assert not verify_consistency(old_root, merkle_root(edited), 8, 16, proof)


def test_consistency_fails_when_an_entry_is_deleted():
    original = leaves(16)
    old_root = merkle_root(original[:8])
    shortened = original[:3] + original[4:]  # drop index 3
    proof = consistency_proof(shortened, 8, len(shortened))
    assert not verify_consistency(
        old_root, merkle_root(shortened), 8, len(shortened), proof
    )


def test_consistency_fails_when_entries_are_reordered():
    original = leaves(16)
    old_root = merkle_root(original[:8])
    swapped = list(original)
    swapped[2], swapped[5] = swapped[5], swapped[2]
    proof = consistency_proof(swapped, 8, 16)
    assert not verify_consistency(old_root, merkle_root(swapped), 8, 16, proof)


def test_consistency_fails_on_tampered_proof_node():
    ls = leaves(16)
    proof = list(consistency_proof(ls, 5, 16))
    proof[0] = hashlib.sha256(b"evil").digest()
    assert not verify_consistency(merkle_root(ls[:5]), merkle_root(ls), 5, 16, proof)


def test_consistency_rejects_shrinking_tree():
    ls = leaves(16)
    assert not verify_consistency(merkle_root(ls), merkle_root(ls[:8]), 16, 8, [])


def test_consistency_from_empty_tree_needs_no_proof():
    ls = leaves(9)
    assert verify_consistency(EMPTY_ROOT, merkle_root(ls), 0, 9, [])


def test_consistency_proof_raises_on_invalid_range():
    with pytest.raises(ValueError):
        consistency_proof(leaves(4), 3, 9)


# --------------------------------------------------------------------------
# 4. Cross-check: the two proof systems must agree on the same tree
# --------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 13, 21])
def test_root_from_inclusion_proof_matches_directly_computed_root(n):
    """Independent recomputation: verify_inclusion rebuilds the root bottom-up while
    merkle_root builds it top-down. Agreement for every leaf is a strong internal
    consistency check on both code paths."""
    ls = leaves(n)
    root = merkle_root(ls)
    assert all(
        verify_inclusion(ls[i], i, n, inclusion_proof(ls, i), root) for i in range(n)
    )


# --------------------------------------------------------------------------
# 5. Verifier robustness: a truncated proof must FAIL, never crash
# --------------------------------------------------------------------------
# These exercise the proof-exhaustion guards. An attacker controls the proof
# bytes, so every path where the verifier runs out of nodes must return False
# rather than raise (a crash in an auditor is a denial-of-service on audit) or,
# worse, fall through to an accept.

@pytest.mark.parametrize("n", [8, 16, 21, 32])
def test_truncated_consistency_proof_always_fails_cleanly(n):
    ls = leaves(n)
    new_root = merkle_root(ls)
    for m in range(1, n):
        full = consistency_proof(ls, m, n)
        old_root = merkle_root(ls[:m])
        for k in range(len(full)):
            assert verify_consistency(old_root, new_root, m, n, full[:k]) is False, (
                f"truncated proof accepted at n={n}, m={m}, k={k}"
            )


@pytest.mark.parametrize("n", [8, 16, 21])
def test_padded_consistency_proof_fails(n):
    """Extra trailing nodes must not be silently ignored."""
    ls = leaves(n)
    for m in (1, 3, n - 1):
        full = consistency_proof(ls, m, n)
        padded = list(full) + [hashlib.sha256(b"extra").digest()]
        assert not verify_consistency(merkle_root(ls[:m]), merkle_root(ls), m, n, padded)


def test_negative_first_is_rejected():
    ls = leaves(8)
    assert not verify_consistency(EMPTY_ROOT, merkle_root(ls), -1, 8, [])


def test_largest_power_of_two_below_guards_its_invariant():
    """Internal invariant: the helper is undefined for n < 2 and must say so."""
    from bcflsrv.ledger.merkle import _largest_power_of_two_below as lp2

    assert lp2(2) == 1 and lp2(3) == 2 and lp2(5) == 4 and lp2(8) == 4
    for bad in (1, 0, -3):
        with pytest.raises(ValueError):
            lp2(bad)


# --------------------------------------------------------------------------
# 6. IncrementalMerkle must agree with the reference implementation
# --------------------------------------------------------------------------
# merkle_root() is the straightforward transcription of RFC 6962 and is treated as
# ground truth. IncrementalMerkle is the O(log n)-per-append fast path that makes
# experiment E-1 runnable. The fast path is never trusted on its own: these tests
# assert the two agree, so an optimisation bug cannot silently corrupt every result
# downstream.

def test_incremental_matches_reference_for_every_size():
    from bcflsrv.ledger.merkle import IncrementalMerkle

    tree = IncrementalMerkle()
    ls = []
    assert tree.root == merkle_root([]), "empty tree must match"
    for i in range(1, 130):
        leaf = hash_leaf(b"entry-%d" % i)
        ls.append(leaf)
        tree.append(leaf)
        assert tree.size == i
        assert tree.root == merkle_root(ls), f"diverged at size {i}"


@pytest.mark.parametrize("n", [1, 2, 3, 4, 7, 8, 9, 255, 256, 257, 1000])
def test_incremental_matches_reference_at_power_of_two_boundaries(n):
    """Sizes either side of a power of two exercise the carry logic hardest."""
    from bcflsrv.ledger.merkle import IncrementalMerkle

    ls = leaves(n)
    tree = IncrementalMerkle()
    for leaf in ls:
        tree.append(leaf)
    assert tree.root == merkle_root(ls)
