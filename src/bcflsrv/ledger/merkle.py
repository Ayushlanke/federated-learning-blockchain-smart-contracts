"""RFC 6962 Merkle tree hashing, inclusion proofs and consistency proofs.

BC-FL-SRV requirement coverage: FR-1, FR-2, FR-3 (see PROJECT_MASTER_SPEC.md).

Why RFC 6962 and not a hand-rolled tree
---------------------------------------
RD-001 rests on AG3 (non-equivocation), which the PoPETs 2026 SoK defines via an
append-only transcript. Certificate Transparency is the deployed system for exactly
that problem, and RFC 6962 specifies both proof types we need with unambiguous test
vectors. Reusing a specified construction keeps the contribution where it belongs --
the committee/admission protocol -- rather than in bespoke crypto, per directive
Section 15 ("design no new cryptography").

What this module provides, and what it does NOT
-----------------------------------------------
Provides: tamper-EVIDENCE. Given a root obtained through a trustworthy channel, a
verifier can check that a leaf is present and that one tree is an append-only
extension of another.

Does NOT provide: tamper-PREVENTION, and does NOT by itself stop equivocation. A
logger holding the only copy of the root can still show different roots to different
parties (split view). Detecting that requires comparing views across parties -- the
gossip layer, which in Certificate Transparency was specified but never widely
deployed. BC-FL-SRV therefore treats "an auditor compares views" as an explicit
assumption (A-5) that is switched OFF in experiment E-6, not as a free guarantee.

Domain separation follows RFC 6962: leaves are hashed with a 0x00 prefix and internal
nodes with 0x01, so no leaf hash can ever be confused with an internal node hash.
"""

from __future__ import annotations

import hashlib
from typing import List, Sequence

__all__ = [
    "LEAF_PREFIX",
    "NODE_PREFIX",
    "EMPTY_ROOT",
    "hash_leaf",
    "hash_children",
    "merkle_root",
    "IncrementalMerkle",
    "inclusion_proof",
    "verify_inclusion",
    "consistency_proof",
    "verify_consistency",
]

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"

# Hash of the empty tree, per RFC 6962: MTH({}) = SHA-256().
EMPTY_ROOT = hashlib.sha256(b"").digest()


def hash_leaf(data: bytes) -> bytes:
    """MTH({d}) = SHA-256(0x00 || d)."""
    return hashlib.sha256(LEAF_PREFIX + data).digest()


def hash_children(left: bytes, right: bytes) -> bytes:
    """Internal node hash = SHA-256(0x01 || left || right)."""
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def _largest_power_of_two_below(n: int) -> int:
    """Largest k such that k < n and k is a power of two (RFC 6962 'k')."""
    if n < 2:
        raise ValueError("n must be >= 2")
    return 1 << ((n - 1).bit_length() - 1)


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    """Merkle Tree Hash over already-hashed leaves.

    ``leaves`` are leaf *hashes* (output of :func:`hash_leaf`), not raw payloads.
    """
    n = len(leaves)
    if n == 0:
        return EMPTY_ROOT
    if n == 1:
        return leaves[0]
    k = _largest_power_of_two_below(n)
    return hash_children(merkle_root(leaves[:k]), merkle_root(leaves[k:]))


class IncrementalMerkle:
    """Maintains the Merkle root in O(log n) per append instead of O(n).

    Why this exists
    ---------------
    :func:`merkle_root` rebuilds the whole tree from scratch, which is O(n). Calling it
    on every append makes building an n-entry log O(n^2) -- at n = 10^5 that is on the
    order of 10^10 hash operations and simply will not run. Experiment E-1 needs
    transcripts spanning 10^2 to 10^5 entries to say anything convincing about
    logarithmic scaling, so an incremental root is a prerequisite for the experiment
    rather than an optimisation for its own sake.

    How it works
    ------------
    RFC 6962 splits a tree of size n at ``k``, the largest power of two below n. The
    left child is therefore always a *perfect* subtree. Any tree decomposes uniquely
    into perfect subtrees of strictly decreasing size -- exactly the set bits of n in
    binary. This class keeps those subtree roots and merges them like a binary counter
    on each append, then folds them right-to-left to produce the root.

    Correctness discipline
    ----------------------
    :func:`merkle_root` is retained as the reference implementation and used as a test
    oracle: a property test asserts the two agree for every size in a wide range. The
    fast path is never trusted on its own.
    """

    __slots__ = ("_stack", "_size")

    def __init__(self) -> None:
        # (subtree_root, subtree_size), sizes strictly decreasing left to right.
        self._stack: List[tuple[bytes, int]] = []
        self._size = 0

    @property
    def size(self) -> int:
        return self._size

    def append(self, leaf_hash: bytes) -> None:
        """Add one already-hashed leaf."""
        self._stack.append((leaf_hash, 1))
        # Merge equal-sized neighbours, carrying like a binary increment.
        while len(self._stack) >= 2 and self._stack[-1][1] == self._stack[-2][1]:
            right_root, right_size = self._stack.pop()
            left_root, left_size = self._stack.pop()
            self._stack.append((hash_children(left_root, right_root), left_size + right_size))
        self._size += 1

    @property
    def root(self) -> bytes:
        """Current Merkle Tree Hash."""
        if not self._stack:
            return EMPTY_ROOT
        root, _ = self._stack[-1]
        for left_root, _ in reversed(self._stack[:-1]):
            root = hash_children(left_root, root)
        return root


def inclusion_proof(leaves: Sequence[bytes], index: int) -> List[bytes]:
    """Audit path proving ``leaves[index]`` is in the tree of size ``len(leaves)``."""
    n = len(leaves)
    if not 0 <= index < n:
        raise IndexError(f"index {index} out of range for tree of size {n}")
    if n == 1:
        return []
    k = _largest_power_of_two_below(n)
    if index < k:
        return inclusion_proof(leaves[:k], index) + [merkle_root(leaves[k:])]
    return inclusion_proof(leaves[k:], index - k) + [merkle_root(leaves[:k])]


def verify_inclusion(
    leaf_hash: bytes,
    index: int,
    tree_size: int,
    proof: Sequence[bytes],
    root: bytes,
) -> bool:
    """Recompute the root from ``leaf_hash`` and ``proof`` and compare.

    This is the *auditor's* view: it never touches the full log, only the leaf, its
    position, the claimed tree size, and the audit path. That is what makes the
    transcript checkable by a party that does not hold it.
    """
    if tree_size <= 0 or not 0 <= index < tree_size:
        return False

    fn, sn = index, tree_size - 1
    r = leaf_hash
    for sibling in proof:
        if sn == 0:
            return False  # proof longer than the tree size can justify
        if fn & 1 or fn == sn:
            r = hash_children(sibling, r)
            while fn != 0 and not (fn & 1):
                fn >>= 1
                sn >>= 1
        else:
            r = hash_children(r, sibling)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root


def consistency_proof(leaves: Sequence[bytes], first: int, second: int) -> List[bytes]:
    """Proof that the tree of size ``second`` append-only extends size ``first``."""
    n = len(leaves)
    if not 0 <= first <= second <= n:
        raise ValueError(f"require 0 <= first <= second <= {n}, got {first}, {second}")
    if first == 0 or first == second:
        return []
    return _subproof(leaves[:second], first, True)


def _subproof(leaves: Sequence[bytes], m: int, is_root: bool) -> List[bytes]:
    n = len(leaves)
    if m == n:
        return [] if is_root else [merkle_root(leaves)]
    k = _largest_power_of_two_below(n)
    if m <= k:
        return _subproof(leaves[:k], m, is_root) + [merkle_root(leaves[k:])]
    return _subproof(leaves[k:], m - k, False) + [merkle_root(leaves[:k])]


def verify_consistency(
    old_root: bytes,
    new_root: bytes,
    first: int,
    second: int,
    proof: Sequence[bytes],
) -> bool:
    """Verify an append-only extension from size ``first`` to size ``second``.

    Returns False for any reordering, deletion, or in-place edit of history. This is
    the property that makes the transcript append-only in a *checkable* sense rather
    than merely by convention.
    """
    if first < 0 or first > second:
        return False
    if first == second:
        return len(proof) == 0 and old_root == new_root
    if first == 0:
        return len(proof) == 0

    node, last_node = first - 1, second - 1
    while node & 1:
        node >>= 1
        last_node >>= 1

    p = list(proof)
    if node:
        if not p:
            return False
        fr = sr = p.pop(0)
    else:
        # `first` is a power of two: the old root is itself the starting node.
        fr = sr = old_root

    while node:
        if node & 1:
            if not p:
                return False
            nxt = p.pop(0)
            fr = hash_children(nxt, fr)
            sr = hash_children(nxt, sr)
        elif node < last_node:
            if not p:
                return False
            sr = hash_children(sr, p.pop(0))
        node >>= 1
        last_node >>= 1

    while last_node:
        if not p:
            return False
        sr = hash_children(sr, p.pop(0))
        last_node >>= 1

    return not p and fr == old_root and sr == new_root
