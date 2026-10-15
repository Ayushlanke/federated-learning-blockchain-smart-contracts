"""Experiment E-1: how does verification cost scale?

Tests sub-claim C2 from EVALUATION_PLAN.md:
    "Verification cost is independent of model size N."

Variable separation -- the thing this experiment must get right
---------------------------------------------------------------
"Verification cost" is not one number. Conflating these would produce a flattering
but wrong result, so each is measured separately and reported separately:

  A. auditor_consistency  -- AG3 check, roots + proof only. Never touches a payload.
  B. auditor_inclusion    -- audit-path check GIVEN a leaf hash. Never touches a payload.
  C. client_end_to_end    -- a client checking its OWN entry: it must hash its own
                             payload (O(N)) and then verify the path (O(log T)).
  D. writer_append        -- the log operator's cost, which includes hashing the payload.

The research claim is about A and B. C is included precisely because it is the one
that *does* depend on N -- omitting it would overstate the result.

Independent variables are swept one at a time:
  E1a: vary payload size N, hold transcript size T fixed.
  E1b: vary transcript size T, hold payload size N fixed.
  E1c: storage and proof size vs T and per-round client count K.

Usage:
    .venv/Scripts/python.exe scripts/exp_e1_verification_cost.py [--quick]
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from bcflsrv.bench.baselines import B0_NO_VERIFICATION_COST_S, FlatSignedLog  # noqa: E402
from bcflsrv.bench.manifest import Manifest  # noqa: E402
from bcflsrv.bench.timing import measure  # noqa: E402
from bcflsrv.ledger.merkle import verify_consistency, verify_inclusion  # noqa: E402
from bcflsrv.ledger.transcript import EntryKind, Transcript  # noqa: E402

SEED = 20260904
EXPERIMENT_ID = "E-1"


def deterministic_payload(size: int, tag: int) -> bytes:
    """Reproducible pseudo-random bytes. Content is irrelevant; only length matters."""
    import hashlib

    out = bytearray()
    counter = 0
    while len(out) < size:
        out += hashlib.sha256(b"E1/%d/%d" % (tag, counter)).digest()
        counter += 1
    return bytes(out[:size])


def build_transcript(n_entries: int, payload_size: int) -> Transcript:
    t = Transcript()
    payload = deterministic_payload(payload_size, 0)
    for _ in range(n_entries):
        t.append(EntryKind.SUBMIT, payload)
    return t


# ---------------------------------------------------------------------------
# E1a -- vary payload size N, transcript size T held fixed
# ---------------------------------------------------------------------------

def run_e1a(payload_sizes, t_fixed: int, repeats: int):
    rows = []
    base = build_transcript(t_fixed, 64)

    for n_bytes in payload_sizes:
        payload = deterministic_payload(n_bytes, 1)
        t = Transcript.from_entries(list(base.entries))
        entry = t.append(EntryKind.SUBMIT, payload)

        seq = entry.seq
        size = t.size
        root = t.root
        proof = t.inclusion_proof(seq)
        leaf = entry.leaf_hash()

        old_size = t_fixed
        old_root = t.root_at(old_size)
        cons_proof = t.consistency_proof(old_size)

        m_incl = measure(lambda: verify_inclusion(leaf, seq, size, proof, root), repeats=repeats)
        m_cons = measure(
            lambda: verify_consistency(old_root, root, old_size, size, cons_proof),
            repeats=repeats,
        )
        # Client end-to-end: re-derive the leaf from its own entry, then verify.
        m_e2e = measure(
            lambda: verify_inclusion(entry.leaf_hash(), seq, size, proof, root),
            repeats=repeats,
        )
        m_append = measure(lambda: Transcript().append(EntryKind.SUBMIT, payload), repeats=repeats)

        rows.append(
            {
                "payload_bytes": n_bytes,
                "transcript_entries": size,
                "auditor_inclusion_us": m_incl.median_us,
                "auditor_inclusion_iqr_us": m_incl.iqr_us,
                "auditor_inclusion_stable": m_incl.is_stable,
                "auditor_consistency_us": m_cons.median_us,
                "auditor_consistency_iqr_us": m_cons.iqr_us,
                "client_end_to_end_us": m_e2e.median_us,
                "client_end_to_end_iqr_us": m_e2e.iqr_us,
                "writer_append_us": m_append.median_us,
                "proof_nodes": len(proof),
                "proof_bytes": len(proof) * 32,
            }
        )
        print(
            f"  N={n_bytes:>9,}B  auditor-incl {m_incl.median_us:8.2f}us  "
            f"auditor-cons {m_cons.median_us:8.2f}us  "
            f"client-e2e {m_e2e.median_us:9.2f}us  append {m_append.median_us:9.2f}us"
        )
    return rows


# ---------------------------------------------------------------------------
# E1b -- vary transcript size T, payload size N held fixed
# ---------------------------------------------------------------------------

def run_e1b(transcript_sizes, payload_size: int, repeats: int, baseline_cap: int):
    rows = []
    for t_size in transcript_sizes:
        t = build_transcript(t_size, payload_size)
        seq = t_size // 2
        entry = t[seq]
        leaf = entry.leaf_hash()
        root = t.root
        proof = t.inclusion_proof(seq)

        old_size = max(1, t_size // 2)
        old_root = t.root_at(old_size)
        cons_proof = t.consistency_proof(old_size)

        m_incl = measure(lambda: verify_inclusion(leaf, seq, t_size, proof, root), repeats=repeats)
        m_cons = measure(
            lambda: verify_consistency(old_root, root, old_size, t_size, cons_proof),
            repeats=repeats,
        )

        # Baseline B1: signed log with no tree. Verification replays every entry.
        b1_us = None
        b1_bytes = None
        if t_size <= baseline_cap:
            flat = FlatSignedLog()
            payload = deterministic_payload(payload_size, 0)
            for _ in range(t_size):
                flat.append(payload)
            head = flat.head
            m_b1 = measure(
                lambda: flat.verify_entry_present(seq, payload, head),
                repeats=max(3, repeats // 3),
            )
            b1_us = m_b1.median_us
            b1_bytes = flat.proof_bytes_for_inclusion()

        rows.append(
            {
                "transcript_entries": t_size,
                "payload_bytes": payload_size,
                "auditor_inclusion_us": m_incl.median_us,
                "auditor_inclusion_iqr_us": m_incl.iqr_us,
                "auditor_consistency_us": m_cons.median_us,
                "auditor_consistency_iqr_us": m_cons.iqr_us,
                "proof_nodes": len(proof),
                "proof_bytes": len(proof) * 32,
                "consistency_proof_nodes": len(cons_proof),
                "baseline_b1_inclusion_us": b1_us,
                "baseline_b1_bytes_transferred": b1_bytes,
                "baseline_b0_us": B0_NO_VERIFICATION_COST_S,
            }
        )
        b1_str = f"{b1_us:10.2f}us" if b1_us is not None else "  (skipped)"
        print(
            f"  T={t_size:>7,}  incl {m_incl.median_us:7.2f}us  "
            f"cons {m_cons.median_us:7.2f}us  proof {len(proof):>2} nodes "
            f"({len(proof)*32:>4}B)   B1 {b1_str}"
        )
    return rows


# ---------------------------------------------------------------------------
# E1c -- storage per round
# ---------------------------------------------------------------------------

def run_e1c(client_counts, payload_sizes):
    """Transcript bytes per round: is it O(K) digests or O(K*N) payloads?

    BC-FL-SRV records a 32-byte DIGEST per submission, never the update itself; the
    masked update goes to the aggregator out of band. NFR-3 predicts O(K).
    """
    rows = []
    for k in client_counts:
        for n_bytes in payload_sizes:
            t = Transcript()
            for i in range(k):
                t.append(EntryKind.SUBMIT, deterministic_payload(32, i))  # digest only
            t.append(EntryKind.ADMIT, deterministic_payload(32, 999))
            t.append(EntryKind.FINALIZE, deterministic_payload(32, 998))
            digest_bytes = len(t.to_jsonl().encode("utf-8"))
            naive_bytes = k * n_bytes  # if the log stored full updates instead
            rows.append(
                {
                    "clients_per_round": k,
                    "update_bytes": n_bytes,
                    "transcript_bytes_per_round": digest_bytes,
                    "naive_full_update_bytes": naive_bytes,
                    "reduction_factor": naive_bytes / digest_bytes if digest_bytes else 0,
                }
            )
    return rows


def write_csv(path: Path, rows) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="E-1: verification cost scaling")
    parser.add_argument("--quick", action="store_true", help="smaller sweep for a fast check")
    parser.add_argument("--repeats", type=int, default=11)
    args = parser.parse_args()

    if args.quick:
        payload_sizes = [64, 4096, 262_144]
        transcript_sizes = [64, 512, 4096]
        t_fixed, baseline_cap = 256, 4096
    else:
        payload_sizes = [64, 1024, 16_384, 262_144, 1_048_576, 4_194_304]
        transcript_sizes = [64, 256, 1024, 4096, 16_384, 65_536]
        t_fixed, baseline_cap = 1024, 16_384

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = REPO_ROOT / "results" / "runs" / f"e1_{stamp}"
    summary_dir = REPO_ROOT / "results" / "summary"

    manifest = Manifest(
        experiment_id=EXPERIMENT_ID,
        description=(
            "Verification cost scaling. Separates auditor-side cost (independent of "
            "payload size) from client end-to-end cost (which hashes its own payload) "
            "and writer append cost."
        ),
        parameters={
            "payload_sizes_bytes": payload_sizes,
            "transcript_sizes_entries": transcript_sizes,
            "t_fixed_for_e1a": t_fixed,
            "baseline_b1_cap_entries": baseline_cap,
            "timing_repeats": args.repeats,
            "quick_mode": args.quick,
        },
        seeds={"payload_seed": SEED},
    )
    manifest.note(
        "Payloads are deterministic SHA-256 streams; only their LENGTH affects timing."
    )
    manifest.note(
        "Baseline B1 (flat signed log) is capped because its verification is O(T) and "
        "becomes impractically slow at large T -- which is itself the finding."
    )
    manifest.note(
        "Timing uses median over repeats with IQR reported. Treat any row where "
        "*_stable is False as noise-affected."
    )

    print(f"E-1 verification cost scaling  (quick={args.quick})")
    print("\n[E1a] vary payload size N, transcript fixed at T =", t_fixed)
    rows_a = run_e1a(payload_sizes, t_fixed, args.repeats)

    print("\n[E1b] vary transcript size T, payload fixed at 1 KiB")
    rows_b = run_e1b(transcript_sizes, 1024, args.repeats, baseline_cap)

    print("\n[E1c] storage per round")
    rows_c = run_e1c([10, 20, 50], [1024, 400_000])
    for r in rows_c[:2]:
        print(
            f"  K={r['clients_per_round']:>3}  transcript "
            f"{r['transcript_bytes_per_round']:>7,}B/round vs naive "
            f"{r['naive_full_update_bytes']:>12,}B  ({r['reduction_factor']:.0f}x smaller)"
        )

    for name, rows in (("e1a_payload_size", rows_a), ("e1b_transcript_size", rows_b),
                       ("e1c_storage", rows_c)):
        write_csv(out_dir / f"{name}.csv", rows)
        write_csv(summary_dir / f"{name}.csv", rows)

    manifest.outputs = [f"{n}.csv" for n in ("e1a_payload_size", "e1b_transcript_size", "e1c_storage")]
    manifest.finish()
    manifest.save(out_dir)

    print(f"\nResults: {out_dir}")
    print(f"Summary CSVs: {summary_dir}")
    print(f"Reproduce with: {manifest.reproduction_command()}")
    for warning in manifest.warnings():
        print(f"  WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
