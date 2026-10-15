"""Baseline systems for comparison (EVALUATION_PLAN.md section 2).

A measurement of our own implementation alone says nothing. These baselines answer
the two questions an interviewer or examiner will reasonably ask:

* **B0 -- no verification.** What does accountability cost relative to doing nothing?
* **B1 -- signed log, no Merkle tree.** "Why not just sign the log?" A plain signed
  log genuinely provides integrity: alter any entry and the chain hash changes. What
  it cannot provide is *succinct* verification. To check that entry *i* is present, or
  that a new head extends an old one, a verifier must re-hash **every** entry -- O(T)
  work and O(T) bytes transferred. The Merkle tree replaces that with O(log T).

B1 is deliberately implemented well rather than as a strawman: it uses the same
SHA-256 and the same canonical entry encoding. The difference measured is therefore
attributable to the *data structure*, not to an unfair implementation.
"""

from __future__ import annotations

import hashlib
from typing import List, Sequence

__all__ = ["FlatSignedLog", "B0_NO_VERIFICATION_COST_S"]

# B0: a system with no verification does no verification work. Stated explicitly so
# it appears in tables as a real reference point rather than an unstated assumption.
B0_NO_VERIFICATION_COST_S = 0.0

_DOMAIN = b"BCFLSRV/flatlog/v1"


class FlatSignedLog:
    """Baseline B1: append-only log whose only integrity mechanism is a chain hash.

    ``head = H(... H(H(seed || e0) || e1) ... || e_{n-1})``

    This is what you get from "just sign the log": tampering is detectable, but only
    by someone willing to replay the whole log.
    """

    __slots__ = ("_entries", "_head")

    def __init__(self) -> None:
        self._entries: List[bytes] = []
        self._head: bytes = hashlib.sha256(_DOMAIN).digest()

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def head(self) -> bytes:
        return self._head

    def append(self, payload: bytes) -> None:
        self._entries.append(bytes(payload))
        self._head = hashlib.sha256(self._head + bytes(payload)).digest()

    @staticmethod
    def recompute_head(entries: Sequence[bytes]) -> bytes:
        """Replay the whole log. **This is the O(T) cost the baseline pays.**"""
        head = hashlib.sha256(_DOMAIN).digest()
        for payload in entries:
            head = hashlib.sha256(head + payload).digest()
        return head

    def verify_entry_present(self, index: int, payload: bytes, expected_head: bytes) -> bool:
        """Verify entry ``index`` equals ``payload`` in a log with ``expected_head``.

        There is no shortcut: the verifier must hold every entry and re-hash all of
        them. Contrast :meth:`bcflsrv.ledger.transcript.Transcript.inclusion_proof`,
        where the verifier holds one leaf and ~log2(T) sibling hashes.
        """
        if not 0 <= index < len(self._entries):
            return False
        if self._entries[index] != bytes(payload):
            return False
        return self.recompute_head(self._entries) == expected_head

    def verify_extension(self, old_entries: Sequence[bytes], old_head: bytes) -> bool:
        """Verify this log extends an earlier one -- also O(T), and needs every byte."""
        if len(old_entries) > len(self._entries):
            return False
        if self.recompute_head(old_entries) != old_head:
            return False
        return list(self._entries[: len(old_entries)]) == [bytes(e) for e in old_entries]

    def proof_bytes_for_inclusion(self) -> int:
        """Bytes a verifier must receive: the entire log."""
        return sum(len(e) for e in self._entries)
