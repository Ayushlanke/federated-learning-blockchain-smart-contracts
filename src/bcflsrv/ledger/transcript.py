"""The append-only transcript: typed, hash-chained entries over an RFC 6962 tree.

BC-FL-SRV requirement coverage: FR-1 (append-only + chaining), FR-2/FR-3 (proofs,
delegated to :mod:`bcflsrv.ledger.merkle`), FR-4 (context binding).

What this adds on top of the raw Merkle tree
--------------------------------------------
:mod:`merkle` proves *"this leaf is in this tree"* and *"this tree extends that one"*.
It has no opinion about what a leaf means. This module supplies that meaning:

* **Typed entries.** A round produces SUBMIT, ADMIT, AGGREGATE and FINALIZE entries.
  Each kind gets its own domain tag, so a SUBMIT entry can never be reinterpreted as
  an ADMIT entry even if an attacker controls the payload bytes.
* **Hash chaining.** Every entry commits to ``prev_root`` -- the Merkle root as it
  stood *before* that entry was appended. The Merkle tree already makes rewritten
  history detectable via consistency proofs; chaining additionally binds each entry
  to the exact history it was written against, which is what lets committee sortition
  (FR-5) and replay rejection (FR-4) be derived from the transcript itself.
* **Canonical, injective encoding.** Every field is fixed-width or length-prefixed,
  so no two distinct entries can serialise to the same bytes. Without this the Merkle
  tree would be proving statements about an ambiguous string.

Guarantee boundary -- read this before claiming anything
--------------------------------------------------------
This gives **tamper-evidence relative to a root the verifier already trusts.** It does
NOT prevent tampering, and it does NOT by itself stop equivocation: a writer holding
the only copy can still show root A to one party and root B to another. Catching that
requires two parties to compare roots. BC-FL-SRV treats that comparison as an explicit
assumption (A-5), and tests the system with it switched off in experiment E-6.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

from bcflsrv.ledger.merkle import (
    EMPTY_ROOT,
    IncrementalMerkle,
    consistency_proof,
    hash_leaf,
    inclusion_proof,
    merkle_root,
    verify_consistency,
    verify_inclusion,
)

__all__ = [
    "EntryKind",
    "Entry",
    "Transcript",
    "TranscriptError",
    "IntegrityError",
    "verify_extension",
]

# Version tag inside every leaf. If the encoding ever changes, old and new leaves
# cannot collide, and a verifier reading an unexpected version fails closed.
_ENCODING_VERSION = 1
_DOMAIN = b"BCFLSRV/transcript/v1"

_ROOT_LEN = 32  # SHA-256


class TranscriptError(Exception):
    """Invalid use of the transcript API (programmer error or malformed input)."""


class IntegrityError(TranscriptError):
    """A verification check failed -- treat as evidence of tampering."""


class EntryKind(Enum):
    """The four events an FL round produces.

    Values double as domain-separation tags. They are stable on-disk identifiers and
    must never be renumbered: doing so would silently invalidate stored transcripts.
    """

    SUBMIT = 1
    ADMIT = 2
    AGGREGATE = 3
    FINALIZE = 4


def _u64(value: int) -> bytes:
    if not 0 <= value < 2**64:
        raise TranscriptError(f"value out of range for u64: {value}")
    return value.to_bytes(8, "big")


@dataclass(frozen=True)
class Entry:
    """One transcript entry, immutable once appended.

    Attributes:
        seq: Zero-based position in the log; also the Merkle leaf index.
        kind: Which round event this is.
        prev_root: Merkle root *before* this entry was appended. For the first entry
            this is the empty-tree root.
        payload: Opaque application bytes. This module never interprets them; the
            protocol layers above define their meaning.
    """

    seq: int
    kind: EntryKind
    prev_root: bytes
    payload: bytes

    def __post_init__(self) -> None:
        if self.seq < 0:
            raise TranscriptError(f"seq must be non-negative, got {self.seq}")
        if len(self.prev_root) != _ROOT_LEN:
            raise TranscriptError(
                f"prev_root must be {_ROOT_LEN} bytes, got {len(self.prev_root)}"
            )

    def canonical_bytes(self) -> bytes:
        """Injective serialisation -- the exact bytes committed to the Merkle tree.

        Fixed-width integers and a length-prefixed payload mean distinct entries can
        never produce identical bytes, so a proof about this leaf is a proof about
        this entry and nothing else.
        """
        return b"".join(
            (
                _DOMAIN,
                _u64(_ENCODING_VERSION),
                _u64(self.kind.value),
                _u64(self.seq),
                self.prev_root,
                _u64(len(self.payload)),
                self.payload,
            )
        )

    def leaf_hash(self) -> bytes:
        """RFC 6962 leaf hash of this entry."""
        return hash_leaf(self.canonical_bytes())

    def to_json(self) -> dict:
        return {
            "seq": self.seq,
            "kind": self.kind.name,
            "prev_root": self.prev_root.hex(),
            "payload": base64.b64encode(self.payload).decode("ascii"),
        }

    @classmethod
    def from_json(cls, obj: dict) -> "Entry":
        try:
            return cls(
                seq=int(obj["seq"]),
                kind=EntryKind[obj["kind"]],
                prev_root=bytes.fromhex(obj["prev_root"]),
                payload=base64.b64decode(obj["payload"], validate=True),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise TranscriptError(f"malformed transcript entry: {exc}") from exc


class Transcript:
    """An append-only, hash-chained log of typed entries.

    Example:
        >>> t = Transcript()
        >>> _ = t.append(EntryKind.SUBMIT, b"client-1 commitment")
        >>> _ = t.append(EntryKind.ADMIT, b"admitted={1}")
        >>> t.size
        2
        >>> t.verify_chain()
        True
    """

    def __init__(self) -> None:
        self._entries: List[Entry] = []
        self._leaves: List[bytes] = []
        # Incremental tree head: O(log n) per append. merkle_root() remains the
        # reference implementation and is asserted equivalent by test oracle.
        self._tree = IncrementalMerkle()
        self._root: bytes = EMPTY_ROOT

    # -- basic state ------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def root(self) -> bytes:
        """Current Merkle root, recomputed on each append."""
        return self._root

    @property
    def entries(self) -> Sequence[Entry]:
        """Read-only view of the log."""
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[Entry]:
        return iter(self._entries)

    def __getitem__(self, seq: int) -> Entry:
        try:
            return self._entries[seq]
        except IndexError as exc:
            raise TranscriptError(f"no entry at seq {seq}") from exc

    # -- writing ----------------------------------------------------------

    def append(self, kind: EntryKind, payload: bytes) -> Entry:
        """Append an entry bound to the current root; returns the new entry."""
        if not isinstance(kind, EntryKind):
            raise TranscriptError(f"kind must be an EntryKind, got {type(kind)!r}")
        if not isinstance(payload, (bytes, bytearray)):
            raise TranscriptError(f"payload must be bytes, got {type(payload)!r}")

        entry = Entry(
            seq=len(self._entries),
            kind=kind,
            prev_root=self._root,
            payload=bytes(payload),
        )
        leaf = entry.leaf_hash()
        self._entries.append(entry)
        self._leaves.append(leaf)
        self._tree.append(leaf)
        self._root = self._tree.root
        return entry

    # -- proofs (the auditor-facing surface) ------------------------------

    def inclusion_proof(self, seq: int) -> List[bytes]:
        """Audit path proving entry ``seq`` is in the current tree.

        Note (threat T-7): *requesting* a proof for a specific entry reveals which
        entry the requester cares about. Under secure aggregation that can disclose a
        participation pattern. Callers exposing this over a network must consider
        batching or blinding; this raw API does not do it for them.
        """
        if not 0 <= seq < self.size:
            raise TranscriptError(f"no entry at seq {seq} (size {self.size})")
        return inclusion_proof(self._leaves, seq)

    def consistency_proof(self, old_size: int) -> List[bytes]:
        """Proof that the current tree append-only extends the tree of ``old_size``."""
        if not 0 <= old_size <= self.size:
            raise TranscriptError(f"old_size must be in [0, {self.size}], got {old_size}")
        return consistency_proof(self._leaves, old_size, self.size)

    def root_at(self, size: int) -> bytes:
        """The root this log had when it held ``size`` entries."""
        if not 0 <= size <= self.size:
            raise TranscriptError(f"size must be in [0, {self.size}], got {size}")
        return merkle_root(self._leaves[:size])

    # -- verification -----------------------------------------------------

    def verify_chain(self) -> bool:
        """Check that every entry commits to the root that preceded it.

        This is the chaining check, independent of the Merkle proofs. Both must hold:
        the tree catches rewritten history, and the chain catches an entry claiming to
        have been written against a history it was not.
        """
        running = EMPTY_ROOT
        for i, entry in enumerate(self._entries):
            if entry.seq != i or entry.prev_root != running:
                return False
            running = merkle_root(self._leaves[: i + 1])
        return running == self._root

    def verify_entry(self, entry: Entry) -> bool:
        """Verify an entry against this transcript's current root, via its proof."""
        if not 0 <= entry.seq < self.size:
            return False
        return verify_inclusion(
            entry.leaf_hash(),
            entry.seq,
            self.size,
            self.inclusion_proof(entry.seq),
            self._root,
        )

    # -- persistence ------------------------------------------------------

    def to_jsonl(self) -> str:
        """Serialise to JSON Lines -- one entry per line, in order."""
        return "".join(json.dumps(e.to_json(), sort_keys=True) + "\n" for e in self)

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.to_jsonl(), encoding="utf-8")

    @classmethod
    def from_entries(cls, entries: Iterable[Entry]) -> "Transcript":
        """Rebuild from entries, re-deriving every root.

        Roots are recomputed rather than trusted, and the chain is checked, so a
        tampered file is rejected here instead of silently becoming the truth.
        """
        t = cls()
        for i, entry in enumerate(entries):
            if entry.seq != i:
                raise IntegrityError(
                    f"entry out of order: expected seq {i}, got {entry.seq}"
                )
            if entry.prev_root != t._root:
                raise IntegrityError(
                    f"broken hash chain at seq {i}: entry claims prev_root "
                    f"{entry.prev_root.hex()[:16]}..., actual {t._root.hex()[:16]}..."
                )
            leaf = entry.leaf_hash()
            t._entries.append(entry)
            t._leaves.append(leaf)
            t._tree.append(leaf)
            t._root = t._tree.root
        return t

    @classmethod
    def from_jsonl(cls, text: str) -> "Transcript":
        entries = [
            Entry.from_json(json.loads(line))
            for line in text.splitlines()
            if line.strip()
        ]
        return cls.from_entries(entries)

    @classmethod
    def load(cls, path: Path | str) -> "Transcript":
        return cls.from_jsonl(Path(path).read_text(encoding="utf-8"))

    def __repr__(self) -> str:
        return f"<Transcript size={self.size} root={self._root.hex()[:16]}...>"


def verify_extension(
    old_root: bytes,
    old_size: int,
    new_root: bytes,
    new_size: int,
    proof: Sequence[bytes],
) -> bool:
    """Auditor-side check that ``new_root`` append-only extends ``old_root``.

    Takes only roots, sizes and a proof -- no transcript. This is the function an
    external auditor actually runs, and the reason AG3 is checkable by a party that
    never holds the log.
    """
    return verify_consistency(old_root, new_root, old_size, new_size, proof)
