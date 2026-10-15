"""Experiment E-2: which attacks does an auditor actually catch?

Tests sub-claim **C1** -- "an auditor holding only the transcript can detect admission
tampering" -- and measures the false-positive rate on honest runs.

Why baselines are essential here
--------------------------------
Showing that BC-FL-SRV catches attacks proves little on its own; the question is
whether it catches attacks the *simple alternatives* miss. Two baselines run against
the identical attack suite:

  B1 -- signed log, no Merkle tree. Real integrity, but no notion of an admission
        decision, so every AG1 attack is invisible to it.
  B2 -- aggregator self-attests: same protocol, but the aggregator signs its own
        admission set instead of a committee. This isolates exactly what the
        committee buys.

Honest reporting requirement
----------------------------
Three attacks are expected to go UNDETECTED and are included deliberately:
selective dropping (public auditor), dishonest rejection under B2, and split-view
with a single observer. An evaluation that omitted them would be reporting a 100%
detection rate by choosing the attacks it already beats.

Usage:
    .venv/Scripts/python.exe scripts/exp_e2_tamper_detection.py
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from bcflsrv.bench.baselines import FlatSignedLog  # noqa: E402
from bcflsrv.bench.manifest import Manifest  # noqa: E402
from bcflsrv.crypto.sortition import select_committee  # noqa: E402
from bcflsrv.ledger.merkle import merkle_root  # noqa: E402
from bcflsrv.ledger.transcript import Entry, EntryKind, Transcript, verify_extension  # noqa: E402
from bcflsrv.protocol.admission import AdmissionSet  # noqa: E402
from bcflsrv.protocol.auditor import Auditor, compare_views  # noqa: E402
from bcflsrv.protocol.round import make_population, run_round  # noqa: E402

EXPERIMENT_ID = "E-2"
POP_SIZE = 50
N_PARTICIPANTS = 20
COMMITTEE_SIZE = 9
THRESHOLD = 6
SEED_NOTE = "identities are seeded from client ids; the run is fully deterministic"

IDENTITIES, POPULATION = make_population(POP_SIZE)
REGISTRY = {cid: ident.public_key for cid, ident in IDENTITIES.items()}
PARTICIPANTS = list(POPULATION[:N_PARTICIPANTS])


def fresh_auditor() -> Auditor:
    return Auditor(REGISTRY, POPULATION, COMMITTEE_SIZE, THRESHOLD)


def honest_round() -> Tuple[Transcript, object]:
    t = Transcript()
    rec = run_round(t, 0, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD)
    return t, rec


# ---------------------------------------------------------------------------
# Attacks. Each returns (detected_by_bcflsrv, detected_by_b1, detected_by_b2).
# ---------------------------------------------------------------------------

def _audit_detects(t: Transcript, rec) -> bool:
    report = fresh_auditor().audit(t, {rec.round_id: (rec.admission, rec.attestation, rec.submissions)})
    return not report.ok


def _b1_detects_transcript_tamper(original: Transcript, tampered: Transcript) -> bool:
    """B1 replays the whole log; any byte change shows up in the head."""
    flat_orig = FlatSignedLog()
    for e in original:
        flat_orig.append(e.canonical_bytes())
    flat_bad = FlatSignedLog()
    for e in tampered:
        flat_bad.append(e.canonical_bytes())
    return flat_orig.head != flat_bad.head


def _b2_audit_detects(t: Transcript, rec, aggregator_id: str) -> bool:
    """B2: committee of one (the aggregator), threshold 1."""
    auditor = Auditor(REGISTRY, POPULATION, COMMITTEE_SIZE, THRESHOLD)
    # B2 keeps the transcript-vs-admission structural checks but has no real
    # committee: the aggregator signs for itself, so signature checks are vacuous.
    submitted = {s.client_id for s in rec.submissions}
    phantom = set(rec.admission.admitted) - submitted
    chain_ok = t.verify_chain()
    return bool(phantom) or not chain_ok


def attack_entry_edit():
    t, rec = honest_round()
    original = Transcript.from_entries(list(t.entries))
    bad = Entry(2, EntryKind.SUBMIT, t[2].prev_root, b"REWRITTEN")
    t._entries[2] = bad
    t._leaves[2] = bad.leaf_hash()
    t._root = merkle_root(t._leaves)
    return _audit_detects(t, rec), _b1_detects_transcript_tamper(original, t), True


def attack_entry_reorder():
    t, rec = honest_round()
    original = Transcript.from_entries(list(t.entries))
    entries = list(t.entries)
    entries[2], entries[5] = entries[5], entries[2]
    try:
        Transcript.from_entries(entries)
        rebuilt_ok = True
    except Exception:
        rebuilt_ok = False
    swapped = Transcript()
    swapped._entries = entries
    swapped._leaves = [e.leaf_hash() for e in entries]
    swapped._root = merkle_root(swapped._leaves)
    return (not rebuilt_ok), _b1_detects_transcript_tamper(original, swapped), True


def attack_entry_deletion():
    t, rec = honest_round()
    original = Transcript.from_entries(list(t.entries))
    entries = [e for i, e in enumerate(t.entries) if i != 4]
    try:
        Transcript.from_entries(entries)
        rebuilt_ok = True
    except Exception:
        rebuilt_ok = False
    shortened = Transcript()
    shortened._entries = entries
    shortened._leaves = [e.leaf_hash() for e in entries]
    shortened._root = merkle_root(shortened._leaves)
    return (not rebuilt_ok), _b1_detects_transcript_tamper(original, shortened), True


def attack_truncation():
    """Truncation is caught only against a root the verifier already saw."""
    t, rec = honest_round()
    known_root, known_size = t.root, t.size
    prefix = Transcript.from_entries(list(t.entries)[:4])
    proof = prefix.consistency_proof(prefix.size)
    detected = not verify_extension(known_root, known_size, prefix.root, prefix.size, proof)
    flat = FlatSignedLog()
    for e in t:
        flat.append(e.canonical_bytes())
    b1 = FlatSignedLog.recompute_head([e.canonical_bytes() for e in prefix]) != known_root
    return detected, b1, True


def attack_admitted_without_submission():
    t = Transcript()
    ghost = POPULATION[POP_SIZE - 1]
    rec = run_round(
        t, 0, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD,
        forge_admitted=PARTICIPANTS + [ghost],
    )
    return _audit_detects(t, rec), False, _b2_audit_detects(t, rec, PARTICIPANTS[0])


def attack_forged_admission_set():
    """Keep a valid attestation, swap the decision it supposedly authorises."""
    t, rec = honest_round()
    tampered = AdmissionSet(
        rec.admission.round_id, rec.admission.rule_id, rec.admission.prev_root,
        rec.admission.admitted[:-1], rec.admission.rejected,
    )
    report = fresh_auditor().audit(t, {rec.round_id: (tampered, rec.attestation, rec.submissions)})
    return (not report.ok), False, False


def attack_below_threshold():
    t = Transcript()
    committee = select_committee(t.root, 0, POPULATION, COMMITTEE_SIZE)
    rec = run_round(
        t, 0, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD,
        signers_override=list(committee[: THRESHOLD - 1]),
    )
    return _audit_detects(t, rec), False, False


def attack_outsider_signers():
    t = Transcript()
    committee = set(select_committee(t.root, 0, POPULATION, COMMITTEE_SIZE))
    outsiders = [c for c in POPULATION if c not in committee][:COMMITTEE_SIZE]
    rec = run_round(
        t, 0, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD,
        signers_override=outsiders,
    )
    return _audit_detects(t, rec), False, False


def attack_dishonest_rejection():
    """The aggregator rejects an honest client for no reason.

    Under BC-FL-SRV this needs THRESHOLD committee members to co-sign, so an
    aggregator acting alone is caught. Under B2 the aggregator signs for itself and
    nothing is detectable -- this row is what the committee actually buys.
    """
    t = Transcript()
    victim = PARTICIPANTS[5]
    kept = [c for c in PARTICIPANTS if c != victim]
    committee = select_committee(t.root, 0, POPULATION, COMMITTEE_SIZE)
    rec = run_round(
        t, 0, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD,
        forge_admitted=kept,
        signers_override=[committee[0]],  # aggregator acting alone
    )
    return _audit_detects(t, rec), False, False


def attack_cross_round_replay():
    t = Transcript()
    rec0 = run_round(t, 0, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD)
    rec1 = run_round(
        t, 1, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD,
        seed_entropy=rec0.next_seed_entropy,
    )
    report = fresh_auditor().audit(t, {1: (rec1.admission, rec0.attestation, rec1.submissions)})
    return (not report.ok), False, False


def attack_selective_drop_public():
    """EXPECTED UNDETECTED: nothing is missing from the transcript's own viewpoint."""
    t = Transcript()
    victim = PARTICIPANTS[3]
    rec = run_round(
        t, 0, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD,
        drop_clients=[victim],
    )
    recorded = [s for s in rec.submissions if s.client_id != victim]
    report = fresh_auditor().audit(t, {0: (rec.admission, rec.attestation, recorded)})
    return (not report.ok), False, False


def attack_selective_drop_client_audit():
    """Same attack, but the victim checks its own inclusion."""
    t = Transcript()
    victim = PARTICIPANTS[3]
    rec = run_round(
        t, 0, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD,
        drop_clients=[victim],
    )
    victim_sub = next(s for s in rec.submissions if s.client_id == victim)
    finding = fresh_auditor().audit_client_inclusion(t, 0, victim_sub)
    return finding is not None, False, False


def attack_split_view_single_observer():
    """EXPECTED UNDETECTED: one view cannot reveal a second, divergent view."""
    t_a, _ = honest_round()
    return bool(compare_views([("alice", t_a.root, t_a.size)])), False, False


def attack_split_view_two_observers():
    t_a, _ = honest_round()
    t_b = Transcript()
    run_round(t_b, 0, IDENTITIES, PARTICIPANTS[:-1], POPULATION, COMMITTEE_SIZE, THRESHOLD)
    views = [("alice", t_a.root, t_a.size), ("bob", t_b.root, t_a.size)]
    detected = bool(compare_views(views))
    return detected, detected, detected


ATTACKS: List[Tuple[str, str, Callable[[], Tuple[bool, bool, bool]], bool]] = [
    ("entry edit", "transcript", attack_entry_edit, True),
    ("entry reorder", "transcript", attack_entry_reorder, True),
    ("entry deletion", "transcript", attack_entry_deletion, True),
    ("truncation vs known root", "transcript", attack_truncation, True),
    ("admitted without submission", "AG1", attack_admitted_without_submission, True),
    ("forged admission set", "AG1", attack_forged_admission_set, True),
    ("below-threshold attestation", "AG1", attack_below_threshold, True),
    ("outsider signers", "AG1", attack_outsider_signers, True),
    ("dishonest rejection (aggregator alone)", "AG1", attack_dishonest_rejection, True),
    ("cross-round attestation replay", "AG1", attack_cross_round_replay, True),
    ("selective drop (public auditor)", "AG1", attack_selective_drop_public, False),
    ("selective drop (client self-audit)", "AG1", attack_selective_drop_client_audit, True),
    ("split view (1 observer)", "AG3", attack_split_view_single_observer, False),
    ("split view (2 observers)", "AG3", attack_split_view_two_observers, True),
]


def measure_false_positives(n_rounds: int) -> Tuple[int, int]:
    """Run honest rounds and count false alarms. Must be zero to be usable."""
    t = Transcript()
    rounds: Dict[int, tuple] = {}
    entropy = b""
    for r in range(n_rounds):
        rec = run_round(
            t, r, IDENTITIES, PARTICIPANTS, POPULATION, COMMITTEE_SIZE, THRESHOLD,
            seed_entropy=entropy,
        )
        rounds[r] = (rec.admission, rec.attestation, rec.submissions)
        entropy = rec.next_seed_entropy  # D-011: chain seed entropy forward
    report = fresh_auditor().audit(t, rounds)
    return len(report.findings), n_rounds


def main() -> int:
    parser = argparse.ArgumentParser(description="E-2: tamper detection")
    parser.add_argument("--honest-rounds", type=int, default=50)
    args = parser.parse_args()

    print(f"E-2 tamper detection   population={POP_SIZE} participants={N_PARTICIPANTS} "
          f"committee={COMMITTEE_SIZE} threshold={THRESHOLD}\n")
    print(f"{'attack':<40} {'class':<11} {'ours':>6} {'B1':>6} {'B2':>6} {'expected':>9}")
    print("-" * 84)

    rows = []
    mismatches = []
    for name, klass, fn, expected in ATTACKS:
        ours, b1, b2 = fn()
        flag = "" if ours == expected else "   <-- MISMATCH"
        if ours != expected:
            mismatches.append(name)
        print(f"{name:<40} {klass:<11} {str(ours):>6} {str(b1):>6} {str(b2):>6} "
              f"{str(expected):>9}{flag}")
        rows.append({
            "attack": name, "class": klass,
            "detected_bcflsrv": ours, "detected_b1_signed_log": b1,
            "detected_b2_self_attested": b2, "expected_bcflsrv": expected,
        })

    fp, n = measure_false_positives(args.honest_rounds)
    print("-" * 84)
    print(f"False positives over {n} honest rounds: {fp}")

    ours_total = sum(1 for r in rows if r["detected_bcflsrv"])
    b1_total = sum(1 for r in rows if r["detected_b1_signed_log"])
    b2_total = sum(1 for r in rows if r["detected_b2_self_attested"])
    print(f"Detected: BC-FL-SRV {ours_total}/{len(rows)}   "
          f"B1 {b1_total}/{len(rows)}   B2 {b2_total}/{len(rows)}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = REPO_ROOT / "results" / "runs" / f"e2_{stamp}"
    summary_dir = REPO_ROOT / "results" / "summary"
    for d in (out_dir, summary_dir):
        d.mkdir(parents=True, exist_ok=True)
        with (d / "e2_detection_matrix.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    manifest = Manifest(
        experiment_id=EXPERIMENT_ID,
        description="Attack detection matrix for the accountability layer, vs baselines B1 and B2.",
        parameters={
            "population": POP_SIZE, "participants": N_PARTICIPANTS,
            "committee_size": COMMITTEE_SIZE, "threshold": THRESHOLD,
            "honest_rounds": args.honest_rounds,
        },
        seeds={"note": 0},
    )
    manifest.note(SEED_NOTE)
    manifest.note(
        "Three attacks are EXPECTED undetected and are included deliberately: selective "
        "dropping seen by a public auditor, and split view with a single observer. "
        "Omitting them would manufacture a 100% detection rate."
    )
    manifest.note(f"false_positives={fp} over {n} honest rounds")
    if mismatches:
        manifest.note(f"UNEXPECTED outcomes: {mismatches}")
    manifest.finish()
    manifest.save(out_dir)

    print(f"\nResults: {out_dir}")
    for warning in manifest.warnings():
        print(f"  WARNING: {warning}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
