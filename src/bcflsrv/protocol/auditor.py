"""The external auditor: verifies AG1 and AG3 from the transcript alone (FR-7, RC-6).

This is the party the whole design exists to serve. It holds **no secrets**, was not
present during training, and is not trusted by anyone -- it simply reads the published
transcript and reports what it can and cannot confirm.

The three-way split that matters
--------------------------------
Not every attack is detectable by the same observer, and pretending otherwise would
overstate the system. Attacks fall into three classes:

1. **Detectable from the transcript alone** -- forged or under-signed attestations,
   signatures from non-committee members, a committee that does not match sortition,
   admitting a client that never submitted, cross-round replay, and any edit,
   reorder or deletion of history. :class:`Auditor` catches these.

2. **Detectable only by the affected client** -- *selective dropping*. If the
   aggregator simply never records a client's submission, nothing is missing from the
   transcript's own point of view; only the client knows it submitted. This is why
   :meth:`Auditor.audit_client_inclusion` exists as a separate entry point, and why
   threat T-7 (an inclusion query discloses participation) is unavoidable rather than
   an oversight.

3. **Not detectable with a single view** -- *split-view / equivocation*. A transcript
   can be internally perfect and still be one of two divergent histories shown to
   different parties. Catching that requires comparing roots across observers, which
   is what :func:`compare_views` does and what experiment E-6 measures with the
   auditor population set to zero.

An auditor that reported "all clear" for class 2 and 3 attacks would be lying by
omission, so :class:`AuditReport` states explicitly what was *not* checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Sequence, Tuple

from bcflsrv.crypto.sortition import select_committee
from bcflsrv.ledger.merkle import verify_inclusion
from bcflsrv.ledger.transcript import EntryKind, Transcript, verify_extension
from bcflsrv.protocol.admission import (
    AdmissionSet,
    Attestation,
    Submission,
    attestation_entropy,
)

__all__ = ["Finding", "FindingKind", "AuditReport", "Auditor", "compare_views"]


class FindingKind(Enum):
    """Why an audit failed. Values are stable identifiers used in E-2 result tables."""

    BROKEN_CHAIN = "broken_chain"
    ADMITTED_WITHOUT_SUBMISSION = "admitted_without_submission"
    ATTESTATION_DIGEST_MISMATCH = "attestation_digest_mismatch"
    INSUFFICIENT_SIGNATURES = "insufficient_signatures"
    NON_COMMITTEE_SIGNER = "non_committee_signer"
    WRONG_COMMITTEE = "wrong_committee"
    ROUND_MISMATCH = "round_mismatch"
    STALE_PREV_ROOT = "stale_prev_root"
    MISSING_ATTESTATION = "missing_attestation"
    CLIENT_SUBMISSION_MISSING = "client_submission_missing"
    EQUIVOCATION = "equivocation"


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    round_id: int | None
    detail: str

    def __str__(self) -> str:
        where = f"round {self.round_id}" if self.round_id is not None else "transcript"
        return f"[{self.kind.value}] {where}: {self.detail}"


@dataclass
class AuditReport:
    """Result of an audit. ``ok`` means *nothing detectable was found*, not *safe*."""

    findings: List[Finding] = field(default_factory=list)
    rounds_checked: int = 0
    unchecked: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def kinds(self) -> set[FindingKind]:
        return {f.kind for f in self.findings}

    def summary(self) -> str:
        head = (
            f"PASS ({self.rounds_checked} rounds)"
            if self.ok
            else f"FAIL ({len(self.findings)} finding(s) over {self.rounds_checked} rounds)"
        )
        lines = [head] + [f"  {f}" for f in self.findings]
        if self.unchecked:
            lines.append("  NOT CHECKED by this auditor:")
            lines += [f"    - {u}" for u in self.unchecked]
        return "\n".join(lines)


class Auditor:
    """Verifies AG1 and AG3 given only a transcript and public parameters."""

    def __init__(
        self,
        registry: Mapping[str, bytes],
        population: Sequence[str],
        committee_size: int,
        threshold: int,
    ) -> None:
        """
        Args:
            registry: client id -> public key. Public information.
            population: eligible client ids, used to recompute sortition.
            committee_size: expected committee size.
            threshold: signatures required to authorise an admission set.
        """
        if threshold <= 0 or threshold > committee_size:
            raise ValueError(
                f"threshold must be in [1, {committee_size}], got {threshold}"
            )
        self.registry = dict(registry)
        self.population = tuple(population)
        self.committee_size = committee_size
        self.threshold = threshold

    def audit(
        self,
        transcript: Transcript,
        rounds: Mapping[int, Tuple[AdmissionSet, Attestation, Sequence[Submission]]],
    ) -> AuditReport:
        """Audit every round recorded in ``transcript``.

        Args:
            transcript: the published log.
            rounds: decoded round data -- round id -> (admission, attestation,
                submissions recorded in that round).
        """
        report = AuditReport()
        report.unchecked = [
            "selective dropping (a submission never recorded) -- only the affected "
            "client can detect this; see audit_client_inclusion()",
            "split-view / equivocation -- undetectable from one view; see compare_views()",
            "semantic correctness of the admission rule -- a colluding committee at or "
            "above threshold can attest an incorrect decision (quantified by E-3)",
        ]

        # AG3: is the log internally append-only and correctly chained?
        if not transcript.verify_chain():
            report.findings.append(
                Finding(FindingKind.BROKEN_CHAIN, None, "hash chain does not verify")
            )

        # Seed entropy chains forward: round t's committee depends on round t-1's
        # signatures (D-011 grinding mitigation), so rounds must be audited in order.
        entropy = b""
        for round_id in sorted(rounds):
            admission, attestation, submissions = rounds[round_id]
            report.rounds_checked += 1
            self._audit_round(
                report, round_id, admission, attestation, submissions, entropy
            )
            entropy = attestation_entropy(attestation)

        return report

    def _audit_round(
        self,
        report: AuditReport,
        round_id: int,
        admission: AdmissionSet,
        attestation: Attestation,
        submissions: Sequence[Submission],
        seed_entropy: bytes = b"",
    ) -> None:
        add = report.findings.append

        # AG1(a): the committee must be the one sortition actually produces.
        expected = select_committee(
            admission.prev_root,
            round_id,
            self.population,
            self.committee_size,
            entropy=seed_entropy,
        )
        expected_keys = [self.registry[c] for c in expected if c in self.registry]

        # AG1(b): every attested client must actually have submitted.
        submitted = {s.client_id for s in submissions}
        phantom = sorted(set(admission.admitted) - submitted)
        if phantom:
            add(
                Finding(
                    FindingKind.ADMITTED_WITHOUT_SUBMISSION,
                    round_id,
                    f"admitted with no recorded submission: {phantom}",
                )
            )

        # AG1(c): the attestation must bind THIS decision, in THIS round.
        if attestation.admitted_digest != admission.digest():
            add(
                Finding(
                    FindingKind.ATTESTATION_DIGEST_MISMATCH,
                    round_id,
                    "attestation digest does not match the recorded admission set",
                )
            )
        if attestation.round_id != round_id:
            add(
                Finding(
                    FindingKind.ROUND_MISMATCH,
                    round_id,
                    f"attestation claims round {attestation.round_id}",
                )
            )

        # AG1(d): signers must be committee members, and there must be enough of them.
        outsiders = attestation.signer_keys() - frozenset(expected_keys)
        if outsiders:
            add(
                Finding(
                    FindingKind.NON_COMMITTEE_SIGNER,
                    round_id,
                    f"{len(outsiders)} signature(s) from outside the round committee",
                )
            )

        valid = attestation.count_valid(expected_keys, admission.digest())
        if valid < self.threshold:
            add(
                Finding(
                    FindingKind.INSUFFICIENT_SIGNATURES,
                    round_id,
                    f"{valid} valid committee signature(s), need {self.threshold}",
                )
            )

    def audit_client_inclusion(
        self,
        transcript: Transcript,
        seq: int,
        submission: Submission,
    ) -> Finding | None:
        """A client checks its OWN submission is recorded (detects selective dropping).

        Returns a finding if the submission is absent or altered, else ``None``.

        **Threat T-7:** performing this check reveals to whoever answers it that this
        client participated in this round -- information secure aggregation is meant
        to hide. The leak is inherent to asking the question, not an implementation
        flaw, and is measured rather than hidden.
        """
        if not 0 <= seq < transcript.size:
            return Finding(
                FindingKind.CLIENT_SUBMISSION_MISSING,
                submission.round_id,
                f"no transcript entry at seq {seq} for client {submission.client_id}",
            )
        entry = transcript[seq]
        if entry.kind is not EntryKind.SUBMIT or entry.payload != submission.digest():
            return Finding(
                FindingKind.CLIENT_SUBMISSION_MISSING,
                submission.round_id,
                f"entry {seq} does not record client {submission.client_id}'s submission",
            )
        proof = transcript.inclusion_proof(seq)
        if not verify_inclusion(
            entry.leaf_hash(), seq, transcript.size, proof, transcript.root
        ):
            return Finding(
                FindingKind.CLIENT_SUBMISSION_MISSING,
                submission.round_id,
                f"inclusion proof failed for client {submission.client_id}",
            )
        return None


def compare_views(views: Sequence[Tuple[str, bytes, int]]) -> List[Finding]:
    """Detect equivocation by comparing roots that different observers were shown.

    Args:
        views: (observer name, root, tree size) as reported by each observer.

    Returns:
        A finding per conflicting pair at the same tree size. **An empty list with
        fewer than two views means nothing was checked, not that nothing is wrong** --
        which is precisely the point experiment E-6 makes.
    """
    findings: List[Finding] = []
    by_size: Dict[int, List[Tuple[str, bytes]]] = {}
    for name, root, size in views:
        by_size.setdefault(size, []).append((name, root))

    for size, observers in sorted(by_size.items()):
        roots = {root for _, root in observers}
        if len(roots) > 1:
            names = ", ".join(n for n, _ in observers)
            findings.append(
                Finding(
                    FindingKind.EQUIVOCATION,
                    None,
                    f"observers [{names}] hold {len(roots)} different roots at "
                    f"tree size {size} -- the log equivocated",
                )
            )
    return findings
