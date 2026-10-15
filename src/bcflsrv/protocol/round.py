"""Running one FL round against the transcript, honestly or adversarially.

Deliberately minimal. This exists so experiments E-2 and E-6 can produce realistic
transcripts; it is not a general FL framework. The admission *rule* is a pluggable
callable and defaults to admit-everything, because E-2 tests the **accountability**
layer -- whether admission decisions can be forged or hidden -- not whether the rule
itself is any good. Rule quality is E-4 and E-5.

The adversarial variants live here alongside the honest one on purpose: an attack is
only meaningful if it produces a transcript that a naive observer would accept, so
attacker and defender must share the same round machinery.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Sequence, Tuple

from bcflsrv.crypto.identity import Identity, SigContext
from bcflsrv.crypto.sortition import select_committee
from bcflsrv.ledger.transcript import EntryKind, Transcript
from bcflsrv.protocol.admission import (
    AdmissionSet,
    Attestation,
    Submission,
    attestation_entropy,
    build_attestation,
)

__all__ = ["RoundRecord", "run_round", "AdmissionRule", "admit_all"]

# A rule maps (client_id, evidence_digest) -> admit?  Kept trivial for E-2.
AdmissionRule = Callable[[str, bytes], bool]


def admit_all(_client_id: str, _evidence: bytes) -> bool:
    return True


@dataclass
class RoundRecord:
    """Everything an auditor needs about one round."""

    round_id: int
    admission: AdmissionSet
    attestation: Attestation
    submissions: List[Submission] = field(default_factory=list)
    submission_seq: Dict[str, int] = field(default_factory=dict)
    committee: Tuple[str, ...] = ()
    # Entropy this round CONTRIBUTES to the next round's committee seed (D-011).
    next_seed_entropy: bytes = b""


def run_round(
    transcript: Transcript,
    round_id: int,
    identities: Mapping[str, Identity],
    participants: Sequence[str],
    population: Sequence[str],
    committee_size: int,
    threshold: int,
    *,
    rule: AdmissionRule = admit_all,
    drop_clients: Sequence[str] = (),
    forge_admitted: Sequence[str] | None = None,
    signers_override: Sequence[str] | None = None,
    rule_id: str = "admit-all",
    seed_entropy: bytes = b"",
) -> RoundRecord:
    """Execute one round, optionally misbehaving.

    Args:
        transcript: log to append to.
        round_id: this round's identifier.
        identities: client id -> Identity, for every client and committee member.
        participants: clients submitting this round.
        population: full eligible set, for sortition.
        committee_size, threshold: committee parameters.
        rule: admission rule applied to each submission.
        drop_clients: **attack T-1.** These clients submit, but the aggregator never
            records them. The transcript looks internally consistent; only the dropped
            client can tell.
        forge_admitted: **attack.** Replace the admitted list with this one, e.g. to
            include a client that never submitted.
        signers_override: **attack.** Sign with these ids instead of the real
            committee -- used for outsider-signature and below-threshold attacks.

    Returns:
        A :class:`RoundRecord` describing what was actually written.
    """
    prev_root = transcript.root
    committee = select_committee(
        prev_root, round_id, population, committee_size, entropy=seed_entropy
    )

    submissions: List[Submission] = []
    seq_map: Dict[str, int] = {}
    dropped = set(drop_clients)

    for client_id in participants:
        evidence = hashlib.sha256(b"evidence/%s/%d" % (client_id.encode(), round_id)).digest()
        masked = hashlib.sha256(b"masked/%s/%d" % (client_id.encode(), round_id)).digest()
        submission = Submission(
            client_id=client_id,
            round_id=round_id,
            prev_root=prev_root,
            masked_digest=masked,
            evidence_digest=evidence,
        )
        submissions.append(submission)
        if client_id in dropped:
            continue  # attack T-1: silently omitted from the log
        entry = transcript.append(EntryKind.SUBMIT, submission.digest())
        seq_map[client_id] = entry.seq

    recorded = [s for s in submissions if s.client_id not in dropped]
    admitted = tuple(s.client_id for s in recorded if rule(s.client_id, s.evidence_digest))
    rejected = tuple(s.client_id for s in recorded if s.client_id not in admitted)
    if forge_admitted is not None:
        admitted = tuple(forge_admitted)
        rejected = tuple(c for c in rejected if c not in admitted)

    admission = AdmissionSet(
        round_id=round_id,
        rule_id=rule_id,
        prev_root=prev_root,
        admitted=admitted,
        rejected=rejected,
    )

    signer_ids = list(signers_override) if signers_override is not None else list(committee)
    signers = {identities[c].public_key: identities[c] for c in signer_ids if c in identities}
    attestation = build_attestation(admission, signers)

    transcript.append(EntryKind.ADMIT, admission.digest())
    transcript.append(
        EntryKind.FINALIZE,
        hashlib.sha256(b"aggregate/%d" % round_id).digest(),
    )

    return RoundRecord(
        round_id=round_id,
        admission=admission,
        attestation=attestation,
        submissions=submissions,
        submission_seq=seq_map,
        committee=committee,
        next_seed_entropy=attestation_entropy(attestation),
    )


def make_population(n: int, prefix: str = "client") -> Tuple[Dict[str, Identity], Tuple[str, ...]]:
    """Deterministic client population -- reproducible across runs (seeded identities)."""
    ids = tuple(f"{prefix}-{i:03d}" for i in range(n))
    identities = {cid: Identity.from_seed(cid.encode()) for cid in ids}
    return identities, ids
