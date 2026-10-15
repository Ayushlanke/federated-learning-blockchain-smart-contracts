"""Tests for Ed25519 identities and domain-separated signing (RS-1, FR-4, FR-6).

The security-relevant tests here are the *negative* ones: cross-context replay,
wrong key, tampered message, and malformed input. `verify` must return False for
all of them and must never raise, because an auditor that crashes on attacker-
supplied bytes is a denial-of-service target.
"""

from __future__ import annotations

import pytest

from bcflsrv.crypto.identity import (
    PUBLIC_KEY_LEN,
    SIGNATURE_LEN,
    Identity,
    SigContext,
    client_id_from_public_key,
    verify,
)

MSG = b"round-7 admitted={c1,c2,c3}"


# --------------------------------------------------------------------------
# 1. Key generation and identity derivation
# --------------------------------------------------------------------------

def test_generate_produces_distinct_identities():
    a, b = Identity.generate(), Identity.generate()
    assert a.public_key != b.public_key
    assert a.id != b.id


def test_from_seed_is_deterministic():
    """Reproducibility requirement: E-3 must replay thousands of sortitions exactly."""
    assert Identity.from_seed(b"alice").public_key == Identity.from_seed(b"alice").public_key
    assert Identity.from_seed(b"alice").id == Identity.from_seed(b"alice").id


def test_different_seeds_give_different_keys():
    assert Identity.from_seed(b"alice").public_key != Identity.from_seed(b"bob").public_key


def test_seed_length_is_unconstrained():
    for seed in (b"", b"x", b"y" * 1000):
        assert len(Identity.from_seed(seed).public_key) == PUBLIC_KEY_LEN


def test_from_seed_rejects_non_bytes():
    with pytest.raises(TypeError):
        Identity.from_seed("a string")  # type: ignore[arg-type]


def test_public_key_and_signature_are_expected_sizes():
    ident = Identity.from_seed(b"alice")
    assert len(ident.public_key) == PUBLIC_KEY_LEN == 32
    assert len(ident.sign(SigContext.SUBMISSION, MSG)) == SIGNATURE_LEN == 64


def test_id_is_stable_and_derived_from_public_key():
    ident = Identity.from_seed(b"alice")
    assert ident.id == client_id_from_public_key(ident.public_key)
    assert len(ident.id) == 32  # 16 bytes hex-encoded


def test_client_id_rejects_wrong_length_key():
    with pytest.raises(ValueError):
        client_id_from_public_key(b"too short")


def test_identity_equality_and_hashing():
    a1, a2, b = Identity.from_seed(b"a"), Identity.from_seed(b"a"), Identity.from_seed(b"b")
    assert a1 == a2 and hash(a1) == hash(a2)
    assert a1 != b
    assert a1 != "not an identity"
    assert len({a1, a2, b}) == 2


def test_repr_does_not_leak_key_material():
    ident = Identity.from_seed(b"alice")
    text = repr(ident)
    assert "Identity" in text
    assert ident.public_key.hex() not in text, "repr must not dump the full key"


# --------------------------------------------------------------------------
# 2. Signing and verification, happy path
# --------------------------------------------------------------------------

@pytest.mark.parametrize("context", list(SigContext))
def test_signature_verifies_in_its_own_context(context):
    ident = Identity.from_seed(b"signer")
    assert verify(ident.public_key, context, MSG, ident.sign(context, MSG))


def test_signing_is_deterministic_for_ed25519():
    """Ed25519 is deterministic; identical inputs must give identical signatures."""
    ident = Identity.from_seed(b"signer")
    assert ident.sign(SigContext.SUBMISSION, MSG) == ident.sign(SigContext.SUBMISSION, MSG)


def test_empty_message_is_signable():
    ident = Identity.from_seed(b"signer")
    assert verify(ident.public_key, SigContext.SUBMISSION, b"", ident.sign(SigContext.SUBMISSION, b""))


# --------------------------------------------------------------------------
# 3. Domain separation -- the security property this module exists for
# --------------------------------------------------------------------------

def test_signature_does_not_verify_in_a_different_context():
    """A submission signature must never be replayable as an attestation."""
    ident = Identity.from_seed(b"signer")
    sig = ident.sign(SigContext.SUBMISSION, MSG)
    assert verify(ident.public_key, SigContext.SUBMISSION, MSG, sig)
    assert not verify(ident.public_key, SigContext.ATTESTATION, MSG, sig)
    assert not verify(ident.public_key, SigContext.ROOT_PUBLICATION, MSG, sig)


def test_every_context_pair_is_separated():
    ident = Identity.from_seed(b"signer")
    for signed_in in SigContext:
        sig = ident.sign(signed_in, MSG)
        for checked_in in SigContext:
            expected = signed_in is checked_in
            assert verify(ident.public_key, checked_in, MSG, sig) is expected


def test_length_prefixing_prevents_context_message_boundary_confusion():
    """Without length prefixes, a shifted context/message split could collide."""
    ident = Identity.from_seed(b"signer")
    sig = ident.sign(SigContext.SUBMISSION, b"AB")
    assert not verify(ident.public_key, SigContext.SUBMISSION, b"A", sig)
    assert not verify(ident.public_key, SigContext.SUBMISSION, b"ABC", sig)


# --------------------------------------------------------------------------
# 4. Negative cases -- verify must fail closed, never raise
# --------------------------------------------------------------------------

def test_wrong_key_fails():
    signer, other = Identity.from_seed(b"signer"), Identity.from_seed(b"other")
    sig = signer.sign(SigContext.SUBMISSION, MSG)
    assert not verify(other.public_key, SigContext.SUBMISSION, MSG, sig)


def test_tampered_message_fails():
    ident = Identity.from_seed(b"signer")
    sig = ident.sign(SigContext.SUBMISSION, MSG)
    assert not verify(ident.public_key, SigContext.SUBMISSION, MSG + b"!", sig)
    assert not verify(ident.public_key, SigContext.SUBMISSION, b"totally different", sig)


def test_tampered_signature_fails():
    ident = Identity.from_seed(b"signer")
    sig = bytearray(ident.sign(SigContext.SUBMISSION, MSG))
    sig[0] ^= 0x01
    assert not verify(ident.public_key, SigContext.SUBMISSION, MSG, bytes(sig))


def test_malformed_inputs_return_false_and_do_not_raise():
    ident = Identity.from_seed(b"signer")
    sig = ident.sign(SigContext.SUBMISSION, MSG)
    good = ident.public_key

    cases = [
        (b"short-key", SigContext.SUBMISSION, MSG, sig),
        (b"\x00" * 31, SigContext.SUBMISSION, MSG, sig),
        (good, SigContext.SUBMISSION, MSG, b"short-sig"),
        (good, SigContext.SUBMISSION, MSG, b"\x00" * 63),
        (good, SigContext.SUBMISSION, MSG, b"\x00" * 65),
        (good, "SUBMISSION", MSG, sig),          # context not an enum
        (None, SigContext.SUBMISSION, MSG, sig),
        (good, SigContext.SUBMISSION, "str msg", sig),
        (good, SigContext.SUBMISSION, MSG, None),
    ]
    for pk, ctx, msg, s in cases:
        assert verify(pk, ctx, msg, s) is False, f"should fail closed: {pk!r} {ctx!r}"


def test_all_zero_public_key_does_not_crash():
    """An attacker-supplied all-zero key is not a valid point; must fail, not raise."""
    ident = Identity.from_seed(b"signer")
    sig = ident.sign(SigContext.SUBMISSION, MSG)
    assert verify(b"\x00" * PUBLIC_KEY_LEN, SigContext.SUBMISSION, MSG, sig) is False


def test_sign_rejects_bad_argument_types():
    ident = Identity.from_seed(b"signer")
    with pytest.raises(TypeError):
        ident.sign("SUBMISSION", MSG)              # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ident.sign(SigContext.SUBMISSION, "text")  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# 5. Threshold-attestation shape (what FR-6 will build on)
# --------------------------------------------------------------------------

def test_multiple_signers_over_the_same_statement_are_independently_verifiable():
    """A committee co-signs one admission-set digest; each signature stands alone."""
    committee = [Identity.from_seed(b"member-%d" % i) for i in range(5)]
    statement = b"round=7|rule=norm-bound|admitted=c1,c2,c3"
    sigs = [(m.public_key, m.sign(SigContext.ATTESTATION, statement)) for m in committee]

    assert all(verify(pk, SigContext.ATTESTATION, statement, s) for pk, s in sigs)

    # A signature over a different admission set must not verify against this one.
    forged = b"round=7|rule=norm-bound|admitted=c1,c2"
    assert not any(verify(pk, SigContext.ATTESTATION, forged, s) for pk, s in sigs)


def test_committee_members_have_distinct_ids():
    committee = [Identity.from_seed(b"member-%d" % i) for i in range(20)]
    assert len({m.id for m in committee}) == 20
