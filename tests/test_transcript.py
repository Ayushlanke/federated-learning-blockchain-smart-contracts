"""Tests for the typed, hash-chained transcript (FR-1, FR-2, FR-4).

The interesting tests here are the tampering ones. An append-only log is only
meaningful if rewriting it is *detectable*, so most of this file constructs
tampered transcripts and asserts that verification rejects them.
"""

from __future__ import annotations

import json

import pytest

from bcflsrv.ledger.merkle import EMPTY_ROOT, merkle_root
from bcflsrv.ledger.transcript import (
    Entry,
    EntryKind,
    IntegrityError,
    Transcript,
    TranscriptError,
    verify_extension,
)


def build(n: int = 8) -> Transcript:
    """A transcript shaped like real rounds: submits, then admit, then finalize."""
    t = Transcript()
    kinds = [EntryKind.SUBMIT, EntryKind.ADMIT, EntryKind.AGGREGATE, EntryKind.FINALIZE]
    for i in range(n):
        t.append(kinds[i % len(kinds)], b"payload-%d" % i)
    return t


# --------------------------------------------------------------------------
# 1. Basic append semantics
# --------------------------------------------------------------------------

def test_empty_transcript_has_empty_root():
    t = Transcript()
    assert t.size == 0
    assert t.root == EMPTY_ROOT
    assert t.verify_chain()


def test_append_assigns_sequential_seq_and_chains_prev_root():
    t = Transcript()
    e0 = t.append(EntryKind.SUBMIT, b"a")
    root_after_first = t.root
    e1 = t.append(EntryKind.ADMIT, b"b")

    assert (e0.seq, e1.seq) == (0, 1)
    assert e0.prev_root == EMPTY_ROOT
    assert e1.prev_root == root_after_first, "entry must bind the root that preceded it"


def test_root_changes_on_every_append():
    t = Transcript()
    roots = [t.root]
    for i in range(6):
        t.append(EntryKind.SUBMIT, b"p%d" % i)
        roots.append(t.root)
    assert len(set(roots)) == len(roots), "each append must produce a distinct root"


def test_append_rejects_wrong_types():
    t = Transcript()
    with pytest.raises(TranscriptError):
        t.append("SUBMIT", b"x")                  # type: ignore[arg-type]
    with pytest.raises(TranscriptError):
        t.append(EntryKind.SUBMIT, "not bytes")   # type: ignore[arg-type]


def test_indexing_and_iteration():
    t = build(5)
    assert len(t) == 5
    assert [e.seq for e in t] == [0, 1, 2, 3, 4]
    assert t[3].seq == 3
    with pytest.raises(TranscriptError):
        _ = t[99]


def test_entries_view_is_immutable():
    t = build(3)
    entries = t.entries
    assert isinstance(entries, tuple)
    assert len(entries) == 3


# --------------------------------------------------------------------------
# 2. Canonical encoding must be injective and domain-separated
# --------------------------------------------------------------------------

def test_same_payload_different_kind_gives_different_leaf():
    """A SUBMIT entry must never be reinterpretable as an ADMIT entry."""
    a = Entry(0, EntryKind.SUBMIT, EMPTY_ROOT, b"same")
    b = Entry(0, EntryKind.ADMIT, EMPTY_ROOT, b"same")
    assert a.leaf_hash() != b.leaf_hash()


def test_same_payload_different_seq_gives_different_leaf():
    a = Entry(0, EntryKind.SUBMIT, EMPTY_ROOT, b"same")
    b = Entry(1, EntryKind.SUBMIT, EMPTY_ROOT, b"same")
    assert a.leaf_hash() != b.leaf_hash()


def test_length_prefixing_prevents_payload_boundary_confusion():
    """Without a length prefix, ("ab","c") and ("a","bc") could collide."""
    a = Entry(0, EntryKind.SUBMIT, EMPTY_ROOT, b"ab")
    b = Entry(0, EntryKind.SUBMIT, EMPTY_ROOT, b"abc")
    assert a.canonical_bytes() != b.canonical_bytes()
    assert not b.canonical_bytes().startswith(a.canonical_bytes())


def test_entry_rejects_malformed_construction():
    with pytest.raises(TranscriptError):
        Entry(-1, EntryKind.SUBMIT, EMPTY_ROOT, b"x")
    with pytest.raises(TranscriptError):
        Entry(0, EntryKind.SUBMIT, b"too-short", b"x")


# --------------------------------------------------------------------------
# 3. Proofs delegated to the Merkle layer, wired through entries
# --------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 5, 8, 13])
def test_every_entry_verifies_against_the_current_root(n):
    t = build(n)
    assert all(t.verify_entry(e) for e in t)


def test_inclusion_proof_rejects_out_of_range():
    t = build(4)
    with pytest.raises(TranscriptError):
        t.inclusion_proof(4)
    with pytest.raises(TranscriptError):
        t.inclusion_proof(-1)


def test_root_at_reconstructs_historical_roots():
    t = Transcript()
    snapshots = []
    for i in range(6):
        snapshots.append(t.root)
        t.append(EntryKind.SUBMIT, b"p%d" % i)
    for size, expected in enumerate(snapshots):
        assert t.root_at(size) == expected


def test_consistency_proof_verifies_growth():
    t = build(4)
    old_root, old_size = t.root, t.size
    for i in range(4):
        t.append(EntryKind.SUBMIT, b"more-%d" % i)
    proof = t.consistency_proof(old_size)
    assert verify_extension(old_root, old_size, t.root, t.size, proof)


def test_consistency_proof_rejects_bad_sizes():
    t = build(4)
    with pytest.raises(TranscriptError):
        t.consistency_proof(99)
    with pytest.raises(TranscriptError):
        t.consistency_proof(-1)


def test_root_at_rejects_bad_size():
    t = build(4)
    with pytest.raises(TranscriptError):
        t.root_at(99)


# --------------------------------------------------------------------------
# 4. Tampering must be detected -- the point of the whole module
# --------------------------------------------------------------------------

def test_rebuild_detects_edited_payload():
    t = build(8)
    entries = list(t.entries)
    entries[3] = Entry(3, entries[3].kind, entries[3].prev_root, b"REWRITTEN")
    with pytest.raises(IntegrityError):
        Transcript.from_entries(entries)


def test_rebuild_detects_changed_entry_kind():
    t = build(8)
    entries = list(t.entries)
    victim = entries[2]
    other = (
        EntryKind.FINALIZE if victim.kind is not EntryKind.FINALIZE else EntryKind.SUBMIT
    )
    entries[2] = Entry(victim.seq, other, victim.prev_root, victim.payload)
    with pytest.raises(IntegrityError):
        Transcript.from_entries(entries)


def test_rebuild_detects_deleted_entry():
    t = build(8)
    entries = list(t.entries)
    del entries[4]
    with pytest.raises(IntegrityError):
        Transcript.from_entries(entries)


def test_rebuild_detects_reordered_entries():
    t = build(8)
    entries = list(t.entries)
    entries[2], entries[5] = entries[5], entries[2]
    with pytest.raises(IntegrityError):
        Transcript.from_entries(entries)


def test_rebuild_detects_inserted_entry():
    t = build(6)
    entries = list(t.entries)
    forged = Entry(3, EntryKind.ADMIT, entries[3].prev_root, b"INSERTED")
    entries.insert(3, forged)
    with pytest.raises(IntegrityError):
        Transcript.from_entries(entries)


def test_rebuild_detects_truncation_then_forged_continuation():
    """Rewriting the tail with a plausible-looking continuation must still fail."""
    t = build(8)
    entries = list(t.entries)[:4]
    entries.append(Entry(4, EntryKind.SUBMIT, b"\x00" * 32, b"forged-tail"))
    with pytest.raises(IntegrityError):
        Transcript.from_entries(entries)


def test_honest_truncation_is_accepted_as_a_shorter_valid_log():
    """A prefix of a valid log IS a valid log. Detecting truncation is the job of the
    consistency proof against a previously-seen root, not of the log in isolation."""
    t = build(8)
    prefix = Transcript.from_entries(list(t.entries)[:5])
    assert prefix.size == 5
    assert prefix.verify_chain()
    assert prefix.root == t.root_at(5)
    assert prefix.root != t.root


def test_truncation_is_caught_by_consistency_against_a_known_root():
    """This is how an auditor who saw the longer log catches the shorter one."""
    t = build(8)
    known_root, known_size = t.root, t.size
    prefix = Transcript.from_entries(list(t.entries)[:5])
    proof = prefix.consistency_proof(prefix.size)
    assert not verify_extension(known_root, known_size, prefix.root, prefix.size, proof)


def test_verify_chain_detects_manually_corrupted_state():
    t = build(6)
    bad = Entry(3, EntryKind.SUBMIT, b"\x11" * 32, b"tampered")
    t._entries[3] = bad  # simulate in-memory corruption
    t._leaves[3] = bad.leaf_hash()
    t._root = merkle_root(t._leaves)
    assert not t.verify_chain()


def test_verify_entry_rejects_foreign_entry():
    t = build(5)
    other = build(5)
    alien = Entry(2, EntryKind.SUBMIT, other[2].prev_root, b"not-in-this-log")
    assert not t.verify_entry(alien)
    assert not t.verify_entry(Entry(99, EntryKind.SUBMIT, EMPTY_ROOT, b"x"))


# --------------------------------------------------------------------------
# 5. Persistence round-trips, and rejects tampered files
# --------------------------------------------------------------------------

def test_jsonl_round_trip_preserves_root():
    t = build(9)
    restored = Transcript.from_jsonl(t.to_jsonl())
    assert restored.size == t.size
    assert restored.root == t.root
    assert [e.payload for e in restored] == [e.payload for e in t]


def test_save_and_load_round_trip(tmp_path):
    t = build(7)
    path = tmp_path / "transcript.jsonl"
    t.save(path)
    assert Transcript.load(path).root == t.root


def test_jsonl_is_one_entry_per_line_and_stable():
    t = build(4)
    lines = t.to_jsonl().strip().splitlines()
    assert len(lines) == 4
    assert t.to_jsonl() == t.to_jsonl(), "serialisation must be deterministic"
    assert [json.loads(x)["seq"] for x in lines] == [0, 1, 2, 3]


def test_loading_a_tampered_file_raises(tmp_path):
    t = build(6)
    path = tmp_path / "t.jsonl"
    t.save(path)

    lines = path.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[2])
    obj["payload"] = "VEFNUEVSRUQ="  # base64("TAMPERED")
    lines[2] = json.dumps(obj, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(IntegrityError):
        Transcript.load(path)


def test_malformed_json_entry_raises_transcript_error():
    for bad in ('{"seq": 0}', '{"seq":0,"kind":"NOPE","prev_root":"00","payload":""}'):
        with pytest.raises(TranscriptError):
            Transcript.from_jsonl(bad)


def test_blank_lines_are_ignored():
    t = build(3)
    assert Transcript.from_jsonl("\n" + t.to_jsonl() + "\n\n").root == t.root


def test_repr_is_informative():
    assert "size=3" in repr(build(3))


def test_u64_range_guard_rejects_oversized_field():
    """Fixed-width encoding must fail loudly rather than silently truncate."""
    huge = Entry(2**64, EntryKind.SUBMIT, EMPTY_ROOT, b"x")
    with pytest.raises(TranscriptError):
        huge.canonical_bytes()
