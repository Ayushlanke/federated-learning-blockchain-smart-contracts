"""Admission sets and threshold committee attestations (FR-6, RC-4, RC-5).

This is the AG1 half of the system: a record of *which clients were admitted and
under which rule*, signed by enough committee members that a single corrupt party
cannot forge it.

Design choices worth defending
------------------------------
**Binary canonical encoding, not JSON, for the signed digest.** JSON canonicalisation
is deceptively hard -- key order, unicode escaping, number formatting, and whitespace
all vary between implementations, and two encoders disagreeing means two parties
computing different digests for the same logical statement. Everything that gets
hashed or signed here uses explicit length-prefixed binary. JSON is used only for
human-readable storage, never as the basis of a signature.

**Sorted client lists.** ``admitted`` and ``rejected`` are sorted before encoding, so
the digest depends on the *set*, not on the order the aggregator happened to iterate.
Without this an honest aggregator could produce a digest that an honest auditor fails
to reproduce.

**Rejections are recorded explicitly.** A client that is dropped silently is
indistinguishable from a client that never submitted. Recording rejections turns an
invisible omission into a visible, attributable decision -- which is the entire point
of AG1.

Guarantee boundary
------------------
A valid attestation proves that ``threshold`` committee members **signed** this
admission set. It does **not** prove the set is *correct*: a colluding committee at or
above the threshold can sign anything. Soundness is probabilistic in committee
corruption, and quantifying that is experiment E-3, not something this module can
provide.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Final, Sequence, Tuple

from bcflsrv.crypto.identity import SigContext, verify

__all__ = [
    "AdmissionSet",
    "Attestation",
    "AttestationError",
    "Submission",
    "attestation_entropy",
]

_ADMISSION_DOMAIN: Final = b"BCFLSRV/admission/v1"
_SUBMISSION_DOMAIN: Final = b"BCFLSRV/submission/v1"


class AttestationError(Exception):
    """Malformed attestation input."""


def _lp(data: bytes) -> bytes:
    """Length-prefixed field: 8-byte big-endian length, then the bytes."""
    return len(data).to_bytes(8, "big") + data


def _lp_str_list(items: Sequence[str]) -> bytes:
    encoded = [s.encode("utf-8") for s in sorted(items)]
    return len(encoded).to_bytes(8, "big") + b"".join(_lp(e) for e in encoded)


@dataclass(frozen=True)
class Submission:
    """One client's round submission, as recorded in the transcript.

    The transcript stores a *digest* of the masked update, never the update itself.
    That is what keeps transcript growth O(K) rather than O(K*N) -- see NFR-3 and the
    E-1c measurement.
    """

    client_id: str
    round_id: int
    prev_root: bytes
    masked_digest: bytes
    evidence_digest: bytes

    def canonical_bytes(self) -> bytes:
        """Bytes the client signs. Binds identity, round, and history (FR-4).

        Including ``prev_root`` is what makes replay across rounds fail: a submission
        signed against one history cannot be re-presented under another.
        """
        return b"".join(
            (
                _SUBMISSION_DOMAIN,
                _lp(self.client_id.encode("utf-8")),
                self.round_id.to_bytes(8, "big"),
                _lp(self.prev_root),
                _lp(self.masked_digest),
                _lp(self.evidence_digest),
            )
        )

    def digest(self) -> bytes:
        return hashlib.sha256(self.canonical_bytes()).digest()


@dataclass(frozen=True)
class AdmissionSet:
    """The committee's decision for one round: who was admitted, who was rejected."""

    round_id: int
    rule_id: str
    prev_root: bytes
    admitted: Tuple[str, ...]
    rejected: Tuple[str, ...]

    def __post_init__(self) -> None:
        overlap = set(self.admitted) & set(self.rejected)
        if overlap:
            raise AttestationError(
                f"client(s) both admitted and rejected: {sorted(overlap)}"
            )

    @property
    def considered(self) -> frozenset[str]:
        """Every client this decision accounts for."""
        return frozenset(self.admitted) | frozenset(self.rejected)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                _ADMISSION_DOMAIN,
                self.round_id.to_bytes(8, "big"),
                _lp(self.rule_id.encode("utf-8")),
                _lp(self.prev_root),
                _lp_str_list(self.admitted),
                _lp_str_list(self.rejected),
            )
        )

    def digest(self) -> bytes:
        """The value committee members actually sign."""
        return hashlib.sha256(self.canonical_bytes()).digest()


@dataclass(frozen=True)
class Attestation:
    """Threshold signatures from committee members over an admission-set digest."""

    round_id: int
    admitted_digest: bytes
    signatures: Tuple[Tuple[bytes, bytes], ...]  # (public_key, signature)

    def signer_keys(self) -> frozenset[bytes]:
        return frozenset(pk for pk, _ in self.signatures)

    def verify(
        self,
        admission: AdmissionSet,
        committee_keys: Sequence[bytes],
        threshold: int,
    ) -> bool:
        """Check this attestation authorises ``admission``.

        Every condition below must hold. Each corresponds to an attack in E-2:

        * digest matches the admission set        -- forged/substituted decision
        * round matches                           -- cross-round replay
        * signers are committee members           -- outsider signatures
        * no duplicate signers                    -- one member counted many times
        * signatures verify in ATTESTATION context -- signature reuse from another role
        * enough valid signatures                 -- below-threshold attestation
        """
        if threshold <= 0:
            raise AttestationError(f"threshold must be positive, got {threshold}")
        if self.admitted_digest != admission.digest():
            return False
        if self.round_id != admission.round_id:
            return False

        allowed = frozenset(bytes(k) for k in committee_keys)
        seen: set[bytes] = set()
        valid = 0
        for pubkey, signature in self.signatures:
            key = bytes(pubkey)
            if key not in allowed or key in seen:
                continue  # outsider, or a duplicate trying to inflate the count
            seen.add(key)
            if verify(key, SigContext.ATTESTATION, self.admitted_digest, signature):
                valid += 1
        return valid >= threshold

    def count_valid(
        self, committee_keys: Sequence[bytes], expected_digest: bytes
    ) -> int:
        """Number of distinct valid committee signatures -- for diagnostics."""
        allowed = frozenset(bytes(k) for k in committee_keys)
        seen: set[bytes] = set()
        valid = 0
        for pubkey, signature in self.signatures:
            key = bytes(pubkey)
            if key not in allowed or key in seen:
                continue
            seen.add(key)
            if verify(key, SigContext.ATTESTATION, expected_digest, signature):
                valid += 1
        return valid


def attestation_entropy(attestation: "Attestation | None") -> bytes:
    """Seed entropy contributed by an attestation -- the grinding mitigation.

    Digest over the round id and the attestation's signatures in sorted order. The
    aggregator cannot forge signatures, so it cannot steer this value without the
    committee's cooperation; see :func:`bcflsrv.crypto.sortition.derive_seed` and the
    E-3d measurement that motivated it.

    Sorting matters: signature order is an aggregator-controlled degree of freedom,
    and leaving it unsorted would hand back part of the grinding lever this is meant
    to remove.

    Returns ``b""`` for the first round, which has no predecessor.
    """
    if attestation is None:
        return b""
    parts = sorted(sig for _, sig in attestation.signatures)
    return hashlib.sha256(
        b"BCFLSRV/seed-entropy/v1"
        + attestation.round_id.to_bytes(8, "big")
        + b"".join(_lp(bytes(s)) for s in parts)
    ).digest()


def build_attestation(
    admission: AdmissionSet,
    signers: Dict[bytes, "object"],
) -> Attestation:
    """Collect signatures from committee members over ``admission``.

    Args:
        admission: the decision being attested.
        signers: mapping of public key -> :class:`~bcflsrv.crypto.identity.Identity`.
    """
    digest = admission.digest()
    sigs = tuple(
        (pubkey, identity.sign(SigContext.ATTESTATION, digest))  # type: ignore[attr-defined]
        for pubkey, identity in signers.items()
    )
    return Attestation(
        round_id=admission.round_id, admitted_digest=digest, signatures=sigs
    )
