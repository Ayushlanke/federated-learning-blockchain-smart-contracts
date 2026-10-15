"""Tests for the benchmark infrastructure.

This code does not ship in the system, but it *produces the numbers the project
reports*. A bug in the timing harness or the baseline would silently corrupt every
result, so it is tested to the same standard as the system itself.
"""

from __future__ import annotations

import time

import pytest

from bcflsrv.bench.baselines import B0_NO_VERIFICATION_COST_S, FlatSignedLog
from bcflsrv.bench.manifest import Manifest, capture_environment
from bcflsrv.bench.timing import measure


# --------------------------------------------------------------------------
# 1. Timing harness
# --------------------------------------------------------------------------

def test_measure_returns_a_plausible_duration():
    """A ~1 ms sleep must measure as roughly 1 ms, not 1 us or 1 s."""
    m = measure(lambda: time.sleep(0.001), repeats=3, warmup=0, target_batch_s=0.001)
    assert 0.0005 < m.median_s < 0.02


def test_measure_orders_operations_correctly():
    """The harness must be able to tell a slow operation from a fast one."""
    fast = measure(lambda: sum(range(10)), repeats=5)
    slow = measure(lambda: sum(range(10_000)), repeats=5)
    assert slow.median_s > fast.median_s * 10


def test_measure_reports_dispersion_and_units():
    m = measure(lambda: sum(range(100)), repeats=7)
    assert m.median_us == pytest.approx(m.median_s * 1e6)
    assert m.min_us == pytest.approx(m.min_s * 1e6)
    assert m.iqr_us == pytest.approx(m.iqr_s * 1e6)
    assert m.min_s <= m.median_s
    assert m.iqr_s >= 0
    assert m.relative_iqr >= 0
    assert isinstance(m.is_stable, bool)
    assert len(m.samples_s) == 7


def test_measure_calibrates_inner_loops_for_fast_operations():
    """A trivial operation must be batched, or the timer resolution dominates."""
    m = measure(lambda: None, repeats=3)
    assert m.inner_loops > 1


def test_measure_requires_enough_repeats_to_estimate_spread():
    with pytest.raises(ValueError):
        measure(lambda: None, repeats=2)


def test_measure_as_dict_is_serialisable():
    d = measure(lambda: sum(range(50)), repeats=3).as_dict()
    assert set(d) >= {"median_us", "min_us", "iqr_us", "is_stable", "repeats"}
    assert all(isinstance(v, (int, float, bool)) for v in d.values())


def test_relative_iqr_is_zero_when_median_is_zero():
    """Guard the division; a degenerate measurement must not raise."""
    from bcflsrv.bench.timing import Measurement

    m = Measurement(median_s=0.0, min_s=0.0, iqr_s=0.0, repeats=3, inner_loops=1)
    assert m.relative_iqr == 0.0


def test_gc_is_restored_after_measurement():
    import gc

    was_enabled = gc.isenabled()
    measure(lambda: None, repeats=3)
    assert gc.isenabled() == was_enabled


# --------------------------------------------------------------------------
# 2. Baseline B1 -- must be correct, or the comparison is meaningless
# --------------------------------------------------------------------------

def test_b0_is_free_by_definition():
    assert B0_NO_VERIFICATION_COST_S == 0.0


def test_flat_log_head_changes_with_every_append():
    log = FlatSignedLog()
    heads = [log.head]
    for i in range(5):
        log.append(b"entry-%d" % i)
        heads.append(log.head)
    assert len(set(heads)) == len(heads)
    assert log.size == 5


def test_flat_log_verifies_a_genuine_entry():
    log = FlatSignedLog()
    for i in range(10):
        log.append(b"entry-%d" % i)
    assert log.verify_entry_present(3, b"entry-3", log.head)


def test_flat_log_rejects_wrong_payload_or_index():
    log = FlatSignedLog()
    for i in range(10):
        log.append(b"entry-%d" % i)
    assert not log.verify_entry_present(3, b"entry-4", log.head)
    assert not log.verify_entry_present(99, b"entry-3", log.head)
    assert not log.verify_entry_present(-1, b"entry-3", log.head)


def test_flat_log_rejects_a_wrong_head():
    """B1 really does detect tampering -- it is just expensive. If this failed, the
    comparison would be against a strawman rather than a real alternative."""
    log = FlatSignedLog()
    for i in range(10):
        log.append(b"entry-%d" % i)
    assert not log.verify_entry_present(3, b"entry-3", b"\x00" * 32)


def test_flat_log_is_order_sensitive():
    a, b = FlatSignedLog(), FlatSignedLog()
    a.append(b"x"); a.append(b"y")
    b.append(b"y"); b.append(b"x")
    assert a.head != b.head


def test_flat_log_extension_check():
    log = FlatSignedLog()
    entries = [b"e-%d" % i for i in range(8)]
    for e in entries:
        log.append(e)
    old = entries[:4]
    old_head = FlatSignedLog.recompute_head(old)
    assert log.verify_extension(old, old_head)
    assert not log.verify_extension(old, b"\x00" * 32)
    assert not log.verify_extension([b"different"] * 4, old_head)
    assert not log.verify_extension(entries + [b"too-long"], old_head)


def test_flat_log_transfers_the_whole_log():
    """The cost B1 pays: an auditor must receive every byte."""
    log = FlatSignedLog()
    for _ in range(10):
        log.append(b"x" * 100)
    assert log.proof_bytes_for_inclusion() == 1000


# --------------------------------------------------------------------------
# 3. Manifest -- provenance must be honest
# --------------------------------------------------------------------------

def test_environment_capture_records_what_matters():
    env = capture_environment()
    for key in ("python_version", "platform", "cpu_count_logical", "packages"):
        assert key in env
    assert "numpy" in env["packages"]


def test_manifest_round_trips_to_json(tmp_path):
    import json

    m = Manifest(experiment_id="E-test", description="unit test", parameters={"a": 1},
                 seeds={"s": 42})
    m.note("a note")
    m.finish()
    path = m.save(tmp_path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["experiment_id"] == "E-test"
    assert loaded["parameters"]["a"] == 1
    assert loaded["seeds"]["s"] == 42
    assert "a note" in loaded["notes"]
    assert loaded["duration_s"] is not None


def test_manifest_records_a_reproduction_command():
    m = Manifest(experiment_id="E-test", description="d", command=["python", "x.py", "--flag"])
    assert m.reproduction_command() == "python x.py --flag"


def test_manifest_warns_about_a_dirty_working_tree():
    """A result built from uncommitted code is not reproducible, and must say so."""
    m = Manifest(experiment_id="E-test", description="d")
    m.environment["git_dirty"] = True
    assert any("DIRTY" in w for w in m.warnings())


def test_manifest_warns_when_not_a_repository():
    m = Manifest(experiment_id="E-test", description="d")
    m.environment["git_commit"] = None
    m.environment["git_dirty"] = False
    assert any("no git commit" in w.lower() for w in m.warnings())


def test_manifest_warns_about_missing_packages():
    m = Manifest(experiment_id="E-test", description="d")
    m.environment["git_dirty"] = False
    m.environment["packages"] = {"ghostlib": "not installed"}
    assert any("ghostlib" in w for w in m.warnings())


def test_clean_manifest_has_no_warnings():
    m = Manifest(experiment_id="E-test", description="d")
    m.environment["git_dirty"] = False
    m.environment["git_commit"] = "abc123"
    m.environment["packages"] = {"numpy": "2.3.1"}
    assert m.warnings() == []
