"""Ed25519 identities, domain-separated signing, and verification.

BC-FL-SRV requirement coverage: RS-1 (identity and key lifecycle), and the signature
half of FR-4 (context binding) and FR-6 (threshold attestation).

Design notes
------------
**No custom cryptography.** Ed25519 comes from the ``cryptography`` library. Directive
Section 15 forbids inventing primitives, and there is nothing to gain here: the
research contribution is the admission protocol, not the signature scheme.

**Domain-separated signing contexts.** A raw signature says "this key signed these
bytes" and nothing more. If a client submission and a committee attestation were both
signed as bare messages, a signature captured in one role could potentially be
replayed in the other. Every signature here is therefore computed over
``DOMAIN || context || len(message) || message``, so a signature produced as a
SUBMISSION can never verify as an ATTESTATION even on identical bytes.

**Deterministic identities.** :meth:`Identity.from_seed` derives a keypair from a seed.
This is essential for reproducibility: experiment E-3 samples committees over
thousands of sortitions and must be re-runnable exactly from a recorded seed.

Guarantee boundary
------------------
A signature proves **origin and integrity of a statement**. It says nothing about
whether the statement is *true*. A committee member can honestly sign an admission
set it dishonestly computed. Detecting that is the job of the threshold (soundness
while corruption stays below it), not of the signature -- see the trust model in
PROJECT_MASTER_SPEC.md section 4.5.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

__all__ = [
    "SigContext",
    "Identity",
    "verify",
    "client_id_from_public_key",
    "PUBLIC_KEY_LEN",
    "SIGNATURE_LEN",
]

_DOMAIN: Final = b"BCFLSRV/sig/v1"
PUBLIC_KEY_LEN: Final = 32
SIGNATURE_LEN: Final = 64
_ID_LEN: Final = 16  # bytes of the public-key digest used as a short identifier


class SigContext(Enum):
    """What role a signature was produced in.

    Values are stable on-disk domain tags -- never renumber them, and never reuse a
    retired value, or old signatures could be reinterpreted in a new role.
    """

    SUBMISSION = b"submission"
    ATTESTATION = b"attestation"
    ROOT_PUBLICATION = b"root-publication"


def _preimage(context: SigContext, message: bytes) -> bytes:
    """Bytes actually signed: domain, context, length-prefixed message.

    Length-prefixing matters: without it, (context=A, msg="xy") and
    (context=A+"x", msg="y") could produce the same preimage.
    """
    ctx = context.value
    return b"".join(
        (
            _DOMAIN,
            len(ctx).to_bytes(2, "big"),
            ctx,
            len(message).to_bytes(8, "big"),
            message,
        )
    )


def client_id_from_public_key(public_key: bytes) -> str:
    """Short, stable, human-readable identifier derived from a public key.

    Used as a transcript-facing identifier. It is a *label*, not a credential --
    possession of the id proves nothing; only a signature does.
    """
    if len(public_key) != PUBLIC_KEY_LEN:
        raise ValueError(
            f"public key must be {PUBLIC_KEY_LEN} bytes, got {len(public_key)}"
        )
    return hashlib.sha256(public_key).digest()[:_ID_LEN].hex()


class Identity:
    """An Ed25519 keypair with a stable derived identifier.

    Example:
        >>> alice = Identity.from_seed(b"alice")
        >>> sig = alice.sign(SigContext.SUBMISSION, b"round-1 update")
        >>> verify(alice.public_key, SigContext.SUBMISSION, b"round-1 update", sig)
        True
        >>> verify(alice.public_key, SigContext.ATTESTATION, b"round-1 update", sig)
        False
    """

    __slots__ = ("_private", "_public_bytes", "_id")

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._private = private_key
        self._public_bytes = private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        self._id = client_id_from_public_key(self._public_bytes)

    # -- construction -----------------------------------------------------

    @classmethod
    def generate(cls) -> "Identity":
        """A fresh random identity. Use :meth:`from_seed` when reproducibility matters."""
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_seed(cls, seed: bytes) -> "Identity":
        """Deterministically derive an identity from a seed.

        The seed is hashed to 32 bytes, so any length works and the mapping is
        stable across runs and platforms. **Test and experiment use only** -- a
        real deployment would use fresh entropy, since anyone who learns the seed
        holds the private key.
        """
        if not isinstance(seed, (bytes, bytearray)):
            raise TypeError(f"seed must be bytes, got {type(seed)!r}")
        material = hashlib.sha256(b"BCFLSRV/keyseed/v1" + bytes(seed)).digest()
        return cls(Ed25519PrivateKey.from_private_bytes(material))

    # -- properties -------------------------------------------------------

    @property
    def public_key(self) -> bytes:
        """Raw 32-byte Ed25519 public key."""
        return self._public_bytes

    @property
    def id(self) -> str:
        """Short hex identifier derived from the public key."""
        return self._id

    # -- signing ----------------------------------------------------------

    def sign(self, context: SigContext, message: bytes) -> bytes:
        """Sign ``message`` in ``context``. Returns a 64-byte signature."""
        if not isinstance(context, SigContext):
            raise TypeError(f"context must be a SigContext, got {type(context)!r}")
        if not isinstance(message, (bytes, bytearray)):
            raise TypeError(f"message must be bytes, got {type(message)!r}")
        return self._private.sign(_preimage(context, bytes(message)))

    def __repr__(self) -> str:
        return f"<Identity id={self._id[:12]}...>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Identity) and other._public_bytes == self._public_bytes

    def __hash__(self) -> int:
        return hash(self._public_bytes)


def verify(
    public_key: bytes,
    context: SigContext,
    message: bytes,
    signature: bytes,
) -> bool:
    """Verify a signature. Returns False on any failure -- never raises.

    An attacker controls the signature bytes and often the public-key bytes, so this
    fails closed on malformed input as well as on a bad signature. A verifier that
    raises is a denial-of-service vector for whoever is auditing.
    """
    if not isinstance(context, SigContext):
        return False
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != PUBLIC_KEY_LEN:
        return False
    if not isinstance(signature, (bytes, bytearray)) or len(signature) != SIGNATURE_LEN:
        return False
    if not isinstance(message, (bytes, bytearray)):
        return False

    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes(public_key))
        pub.verify(bytes(signature), _preimage(context, bytes(message)))
        return True
    except (InvalidSignature, ValueError):
        return False
