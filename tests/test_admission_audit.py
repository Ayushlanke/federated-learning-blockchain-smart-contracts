"""Tests for admission sets, threshold attestation, and the auditor (FR-6, FR-7).

These are the security tests for AG1. Each attack test corresponds to a row in the
E-2 detection matrix, so a regression here is a regression in the headline result.

The tests also pin down what the auditor *cannot* see -- selective dropping and
equivocation -- because an audit that silently missed those while reporting PASS
would be worse than no audit at all.
"""

from __future__ import annotations

import pytest

from bcflsrv.crypto.identity import Identity, SigContext
from bcflsrv.ledger.transcript import Transcript
from bcflsrv.protocol.admission import (
    AdmissionSet,
    Attestation,
    AttestationError,
    Submission,
    build_attestation,
)
from bcflsrv.protocol.auditor import Auditor, FindingKind, compare_views
from bcflsrv.protocol.round import make_population, run_round

POP_SIZE = 30
COMMITTEE = 7
THRESHOLD = 5
ROOT = bytes.fromhex("ab" * 32)


@pytest.fixture
def world():
    identities, population = make_population(POP_SIZE)
    registry = {cid: ident.public_key for cid, ident in identities.items()}
    auditor = Auditor(registry, population, COMMITTEE, THRESHOLD)
    return identities, population, registry, auditor


def participants(population, n=12):
    return list(population[:n])


# --------------------------------------------------------------------------
# 1. AdmissionSet canonical encoding
# --------------------------------------------------------------------------

def test_digest_is_order_independent():
    """The digest must depend on the SET, not on iteration order."""
    a = AdmissionSet(1, "r", ROOT, ("c", "a", "b"), ())
    b = AdmissionSet(1, "r", ROOT, ("a", "b", "c"), ())
    assert a.digest() == b.digest()


def test_digest_changes_with_membership():
    base = AdmissionSet(1, "r", ROOT, ("a", "b"), ())
    assert base.digest() != AdmissionSet(1, "r", ROOT, ("a", "b", "c"), ()).digest()
    assert base.digest() != AdmissionSet(1, "r", ROOT, ("a",), ("b",)).digest()


def test_digest_binds_round_rule_and_history():
    base = AdmissionSet(1, "r", ROOT, ("a",), ())
    assert base.digest() != AdmissionSet(2, "r", ROOT, ("a",), ()).digest()
    assert base.digest() != AdmissionSet(1, "other", ROOT, ("a",), ()).digest()
    assert base.digest() != AdmissionSet(1, "r", bytes(32), ("a",), ()).digest()


def test_length_prefixing_prevents_id_boundary_confusion():
    """("ab","c") and ("a","bc") are different sets and must not collide."""
    assert (
        AdmissionSet(1, "r", ROOT, ("ab", "c"), ()).digest()
        != AdmissionSet(1, "r", ROOT, ("a", "bc"), ()).digest()
    )


def test_client_cannot_be_both_admitted_and_rejected():
    with pytest.raises(AttestationError):
        AdmissionSet(1, "r", ROOT, ("a", "b"), ("b",))


def test_submission_digest_binds_context():
    base = Submission("c1", 3, ROOT, b"m", b"e")
    assert base.digest() != Submission("c2", 3, ROOT, b"m", b"e").digest()
    assert base.digest() != Submission("c1", 4, ROOT, b"m", b"e").digest()
    assert base.digest() != Submission("c1", 3, bytes(32), b"m", b"e").digest()


# --------------------------------------------------------------------------
# 2. Threshold attestation
# --------------------------------------------------------------------------

def test_valid_attestation_verifies(world):
    identities, population, _, _ = world
    committee = list(population[:COMMITTEE])
    admission = AdmissionSet(1, "r", ROOT, ("a",), ())
    signers = {identities[c].public_key: identities[c] for c in committee}
    att = build_attestation(admission, signers)
    keys = [identities[c].public_key for c in committee]
    assert att.verify(admission, keys, THRESHOLD)


def test_below_threshold_is_rejected(world):
    identities, population, _, _ = world
    committee = list(population[:COMMITTEE])
    admission = AdmissionSet(1, "r", ROOT, ("a",), ())
    too_few = {identities[c].public_key: identities[c] for c in committee[: THRESHOLD - 1]}
    att = build_attestation(admission, too_few)
    keys = [identities[c].public_key for c in committee]
    assert not att.verify(admission, keys, THRESHOLD)


def test_outsider_signatures_do_not_count(world):
    """Signatures from non-committee members must not reach the threshold."""
    identities, population, _, _ = world
    committee = list(population[:COMMITTEE])
    outsiders = list(population[COMMITTEE : COMMITTEE + THRESHOLD])
    admission = AdmissionSet(1, "r", ROOT, ("a",), ())
    att = build_attestation(
        admission, {identities[c].public_key: identities[c] for c in outsiders}
    )
    keys = [identities[c].public_key for c in committee]
    assert not att.verify(admission, keys, THRESHOLD)


def test_attestation_does_not_transfer_to_a_different_admission_set(world):
    identities, population, _, _ = world
    committee = list(population[:COMMITTEE])
    real = AdmissionSet(1, "r", ROOT, ("a", "b"), ())
    forged = AdmissionSet(1, "r", ROOT, ("a", "b", "evil"), ())
    att = build_attestation(real, {identities[c].public_key: identities[c] for c in committee})
    keys = [identities[c].public_key for c in committee]
    assert att.verify(real, keys, THRESHOLD)
    assert not att.verify(forged, keys, THRESHOLD)


def test_duplicate_signer_cannot_inflate_the_count(world):
    """One member signing repeatedly must count once, not many times."""
    identities, population, _, _ = world
    committee = list(population[:COMMITTEE])
    admission = AdmissionSet(1, "r", ROOT, ("a",), ())
    lone = identities[committee[0]]
    sig = lone.sign(SigContext.ATTESTATION, admission.digest())
    att = Attestation(1, admission.digest(), tuple((lone.public_key, sig) for _ in range(THRESHOLD)))
    keys = [identities[c].public_key for c in committee]
    assert not att.verify(admission, keys, THRESHOLD)
    assert att.count_valid(keys, admission.digest()) == 1


def test_signature_from_another_context_does_not_count(world):
    """A SUBMISSION signature must not be reusable as an ATTESTATION."""
    identities, population, _, _ = world
    committee = list(population[:COMMITTEE])
    admission = AdmissionSet(1, "r", ROOT, ("a",), ())
    digest = admission.digest()
    att = Attestation(
        1,
        digest,
        tuple(
            (identities[c].public_key, identities[c].sign(SigContext.SUBMISSION, digest))
            for c in committee
        ),
    )
    keys = [identities[c].public_key for c in committee]
    assert not att.verify(admission, keys, THRESHOLD)


def test_round_mismatch_is_rejected(world):
    identities, population, _, _ = world
    committee = list(population[:COMMITTEE])
    admission = AdmissionSet(1, "r", ROOT, ("a",), ())
    att = build_attestation(admission, {identities[c].public_key: identities[c] for c in committee})
    replayed = Attestation(99, att.admitted_digest, att.signatures)
    keys = [identities[c].public_key for c in committee]
    assert not replayed.verify(admission, keys, THRESHOLD)


def test_verify_rejects_non_positive_threshold(world):
    identities, population, _, _ = world
    admission = AdmissionSet(1, "r", ROOT, ("a",), ())
    att = build_attestation(admission, {identities[population[0]].public_key: identities[population[0]]})
    with pytest.raises(AttestationError):
        att.verify(admission, [identities[population[0]].public_key], 0)


# --------------------------------------------------------------------------
# 3. Auditor: honest run passes
# --------------------------------------------------------------------------

def test_honest_round_audits_clean(world):
    identities, population, _, auditor = world
    t = Transcript()
    rec = run_round(t, 1, identities, participants(population), population, COMMITTEE, THRESHOLD)
    report = auditor.audit(t, {1: (rec.admission, rec.attestation, rec.submissions)})
    assert report.ok, report.summary()
    assert report.rounds_checked == 1


def test_multiple_honest_rounds_audit_clean(world):
    identities, population, _, auditor = world
    t = Transcript()
    rounds = {}
    entropy = b""
    for r in range(5):
        rec = run_round(
            t, r, identities, participants(population), population, COMMITTEE, THRESHOLD,
            seed_entropy=entropy,
        )
        rounds[r] = (rec.admission, rec.attestation, rec.submissions)
        entropy = rec.next_seed_entropy  # D-011: chain seed entropy forward
    report = auditor.audit(t, rounds)
    assert report.ok, report.summary()
    assert report.rounds_checked == 5


def test_report_declares_what_it_did_not_check(world):
    """An audit that hid its blind spots would be worse than no audit."""
    identities, population, _, auditor = world
    t = Transcript()
    rec = run_round(t, 1, identities, participants(population), population, COMMITTEE, THRESHOLD)
    report = auditor.audit(t, {1: (rec.admission, rec.attestation, rec.submissions)})
    blurb = " ".join(report.unchecked).lower()
    assert "selective dropping" in blurb
    assert "equivocation" in blurb


def test_auditor_rejects_impossible_threshold():
    with pytest.raises(ValueError):
        Auditor({}, (), 5, 6)


# --------------------------------------------------------------------------
# 4. Auditor: attacks it MUST catch
# --------------------------------------------------------------------------

def test_detects_admitting_a_client_that_never_submitted(world):
    identities, population, _, auditor = world
    t = Transcript()
    part = participants(population)
    ghost = population[POP_SIZE - 1]
    rec = run_round(
        t, 1, identities, part, population, COMMITTEE, THRESHOLD,
        forge_admitted=list(part) + [ghost],
    )
    report = auditor.audit(t, {1: (rec.admission, rec.attestation, rec.submissions)})
    assert FindingKind.ADMITTED_WITHOUT_SUBMISSION in report.kinds(), report.summary()


def test_detects_insufficient_signatures(world):
    identities, population, _, auditor = world
    t = Transcript()
    part = participants(population)
    prev = t.root
    from bcflsrv.crypto.sortition import select_committee

    committee = select_committee(prev, 1, population, COMMITTEE)
    rec = run_round(
        t, 1, identities, part, population, COMMITTEE, THRESHOLD,
        signers_override=list(committee[: THRESHOLD - 1]),
    )
    report = auditor.audit(t, {1: (rec.admission, rec.attestation, rec.submissions)})
    assert FindingKind.INSUFFICIENT_SIGNATURES in report.kinds(), report.summary()


def test_detects_signatures_from_outside_the_committee(world):
    identities, population, _, auditor = world
    t = Transcript()
    part = participants(population)
    prev = t.root
    from bcflsrv.crypto.sortition import select_committee

    committee = set(select_committee(prev, 1, population, COMMITTEE))
    outsiders = [c for c in population if c not in committee][:COMMITTEE]
    rec = run_round(
        t, 1, identities, part, population, COMMITTEE, THRESHOLD,
        signers_override=outsiders,
    )
    report = auditor.audit(t, {1: (rec.admission, rec.attestation, rec.submissions)})
    kinds = report.kinds()
    assert FindingKind.NON_COMMITTEE_SIGNER in kinds, report.summary()
    assert FindingKind.INSUFFICIENT_SIGNATURES in kinds, report.summary()


def test_detects_substituted_admission_set(world):
    """Keep a valid attestation but swap the decision it supposedly authorises."""
    identities, population, _, auditor = world
    t = Transcript()
    rec = run_round(t, 1, identities, participants(population), population, COMMITTEE, THRESHOLD)
    tampered = AdmissionSet(
        rec.admission.round_id,
        rec.admission.rule_id,
        rec.admission.prev_root,
        rec.admission.admitted[:-1],  # quietly drop one admitted client
        rec.admission.rejected,
    )
    report = auditor.audit(t, {1: (tampered, rec.attestation, rec.submissions)})
    assert FindingKind.ATTESTATION_DIGEST_MISMATCH in report.kinds(), report.summary()


def test_detects_broken_chain(world):
    identities, population, _, auditor = world
    t = Transcript()
    rec = run_round(t, 1, identities, participants(population), population, COMMITTEE, THRESHOLD)
    from bcflsrv.ledger.merkle import merkle_root
    from bcflsrv.ledger.transcript import Entry, EntryKind as EK

    bad = Entry(2, EK.SUBMIT, bytes(32), b"tampered")
    t._entries[2] = bad
    t._leaves[2] = bad.leaf_hash()
    t._root = merkle_root(t._leaves)

    report = auditor.audit(t, {1: (rec.admission, rec.attestation, rec.submissions)})
    assert FindingKind.BROKEN_CHAIN in report.kinds(), report.summary()


# --------------------------------------------------------------------------
# 5. Selective dropping -- only the client can see it
# --------------------------------------------------------------------------

def test_selective_drop_is_invisible_to_the_public_auditor(world):
    """The uncomfortable result: a silently dropped client leaves no trace."""
    identities, population, _, auditor = world
    t = Transcript()
    part = participants(population)
    victim = part[3]
    rec = run_round(
        t, 1, identities, part, population, COMMITTEE, THRESHOLD, drop_clients=[victim]
    )
    recorded = [s for s in rec.submissions if s.client_id != victim]
    report = auditor.audit(t, {1: (rec.admission, rec.attestation, recorded)})
    assert report.ok, (
        "public audit is EXPECTED to pass here -- selective dropping is not "
        "detectable from the transcript alone"
    )


def test_dropped_client_detects_its_own_omission(world):
    identities, population, _, auditor = world
    t = Transcript()
    part = participants(population)
    victim = part[3]
    rec = run_round(
        t, 1, identities, part, population, COMMITTEE, THRESHOLD, drop_clients=[victim]
    )
    victim_sub = next(s for s in rec.submissions if s.client_id == victim)
    assert victim not in rec.submission_seq
    finding = auditor.audit_client_inclusion(t, 0, victim_sub)
    assert finding is not None
    assert finding.kind is FindingKind.CLIENT_SUBMISSION_MISSING


def test_included_client_verifies_its_own_inclusion(world):
    identities, population, _, auditor = world
    t = Transcript()
    part = participants(population)
    rec = run_round(t, 1, identities, part, population, COMMITTEE, THRESHOLD)
    for sub in rec.submissions:
        seq = rec.submission_seq[sub.client_id]
        assert auditor.audit_client_inclusion(t, seq, sub) is None


# --------------------------------------------------------------------------
# 6. Equivocation -- needs at least two views
# --------------------------------------------------------------------------

def test_equivocation_invisible_with_a_single_view():
    assert compare_views([("alice", b"\x01" * 32, 10)]) == []
    assert compare_views([]) == []


def test_equivocation_detected_when_two_views_disagree():
    findings = compare_views(
        [("alice", b"\x01" * 32, 10), ("bob", b"\x02" * 32, 10)]
    )
    assert len(findings) == 1
    assert findings[0].kind is FindingKind.EQUIVOCATION


def test_agreeing_views_produce_no_finding():
    root = b"\x03" * 32
    assert compare_views([("a", root, 10), ("b", root, 10), ("c", root, 10)]) == []


def test_views_at_different_sizes_are_not_compared():
    """Different tree sizes are not evidence of equivocation on their own."""
    assert compare_views([("a", b"\x01" * 32, 10), ("b", b"\x02" * 32, 20)]) == []


# --------------------------------------------------------------------------
# 7. Report rendering -- this text is what E-2 prints, so it must be right
# --------------------------------------------------------------------------

def test_finding_renders_round_and_transcript_scope():
    from bcflsrv.protocol.auditor import Finding

    assert "round 3" in str(Finding(FindingKind.ROUND_MISMATCH, 3, "detail"))
    assert "transcript" in str(Finding(FindingKind.BROKEN_CHAIN, None, "detail"))


def test_summary_reports_pass_and_lists_blind_spots(world):
    identities, population, _, auditor = world
    t = Transcript()
    rec = run_round(t, 1, identities, participants(population), population, COMMITTEE, THRESHOLD)
    text = auditor.audit(t, {1: (rec.admission, rec.attestation, rec.submissions)}).summary()
    assert text.startswith("PASS")
    assert "NOT CHECKED" in text


def test_summary_reports_fail_with_each_finding(world):
    identities, population, _, auditor = world
    t = Transcript()
    part = participants(population)
    rec = run_round(
        t, 1, identities, part, population, COMMITTEE, THRESHOLD,
        forge_admitted=list(part) + [population[POP_SIZE - 1]],
    )
    text = auditor.audit(t, {1: (rec.admission, rec.attestation, rec.submissions)}).summary()
    assert text.startswith("FAIL")
    assert FindingKind.ADMITTED_WITHOUT_SUBMISSION.value in text


def test_considered_covers_admitted_and_rejected():
    a = AdmissionSet(1, "r", ROOT, ("a", "b"), ("c",))
    assert a.considered == frozenset({"a", "b", "c"})


def test_client_inclusion_rejects_wrong_entry_kind(world):
    """Pointing the check at an ADMIT entry must not accidentally succeed."""
    identities, population, _, auditor = world
    t = Transcript()
    part = participants(population)
    rec = run_round(t, 1, identities, part, population, COMMITTEE, THRESHOLD)
    admit_seq = len(part)  # first non-SUBMIT entry
    finding = auditor.audit_client_inclusion(t, admit_seq, rec.submissions[0])
    assert finding is not None and finding.kind is FindingKind.CLIENT_SUBMISSION_MISSING
