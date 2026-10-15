"""Tests for the G3 separation-aware admission rule and its primitives.

The most important test in this file is :func:`test_g2_rule_is_unchanged_by_g3`:
G2's published results are frozen, so G3 must be provably incapable of altering
G2's behaviour.
"""

from __future__ import annotations

import numpy as np
import pytest

from bcflsrv.fl.attacks import camouflage_betas
from bcflsrv.fl.evidence import DisclosureLevel, Evidence
from bcflsrv.fl.reputation import ReputationState, apply_g2_rule, g2_rule_id
from bcflsrv.fl.rule_g3 import G3_MINORITY_MAX, apply_g3_rule, g3_rule_id
from bcflsrv.fl.separation import otsu_split


# --------------------------------------------------------------- Otsu primitive
def test_otsu_finds_the_boundary_between_two_clusters():
    split = otsu_split([1.0, 1.1, 0.9, 5.0, 5.1, 4.9])
    assert split is not None
    assert 1.1 < split.threshold < 4.9
    assert split.low_count == 3
    assert split.eta == pytest.approx(1.0, abs=0.01)


def test_otsu_gap_separates_clusters_from_a_ramp_but_eta_does_not():
    """The reason the rule gates on ``gap`` and not on Otsu's own criterion."""
    clustered = otsu_split([1, 1, 1, 1, 5, 5, 5, 5])
    ramp = otsu_split([1, 2, 3, 4, 5, 6, 7, 8])
    # eta is high for BOTH -- it rewards any split of a spread-out sample.
    assert clustered.eta > 0.99 and ramp.eta > 0.7
    # gap tells them apart, because only one has an empty region.
    assert clustered.gap > 4 * ramp.gap


def test_otsu_returns_none_when_no_split_is_meaningful():
    assert otsu_split([2.0, 2.0, 2.0, 2.0]) is None
    assert otsu_split([1.0]) is None
    assert otsu_split([]) is None


def test_otsu_is_deterministic_so_an_auditor_can_recompute_it():
    """AG1 needs a third party to reproduce the threshold bit-exactly."""
    values = list(np.random.default_rng(7).normal(size=25))
    first = otsu_split(values)
    for _ in range(5):
        assert otsu_split(list(reversed(values))) == first


# ------------------------------------------------------------------ G3 fixtures
def _evidence(vector: np.ndarray, norm: float | None = None) -> Evidence:
    return Evidence(
        level=DisclosureLevel.E3,
        commitment=b"\x00" * 32,
        norm=float(np.linalg.norm(vector)) if norm is None else norm,
        vector=vector,
    )


def _population(n_honest: int, n_bad: int, *, bad_offset: float = -1.0):
    """A reputation state whose population is cleanly bimodal."""
    state = ReputationState()
    honest = [f"h{i:02d}" for i in range(n_honest)]
    bad = [f"m{i:02d}" for i in range(n_bad)]
    for _ in range(5):
        state.observe({c: 0.5 for c in honest})
        state.observe({c: 0.5 + bad_offset for c in bad})
    return state, honest, bad


# ----------------------------------------------------------------- the G3 rule
def test_g3_rejects_a_cleanly_separated_minority():
    state, honest, bad = _population(20, 5)
    rng = np.random.default_rng(0)
    evidences = {c: _evidence(rng.normal(size=8).astype(np.float32)) for c in honest[:8] + bad}
    decision, _ = apply_g3_rule(evidences, state, update_state=False)
    assert set(bad) <= set(decision.rejected)
    assert not set(honest[:8]) & set(decision.rejected)


def test_g3_refuses_to_reject_a_majority_class():
    """The minority bound is what makes a gap-seeker safe on honest data."""
    state, honest, bad = _population(5, 20)  # the "low" class is now the majority
    rng = np.random.default_rng(0)
    evidences = {c: _evidence(rng.normal(size=8).astype(np.float32)) for c in honest + bad[:8]}
    decision, _ = apply_g3_rule(evidences, state, update_state=False)
    assert "reputation" not in decision.thresholds
    assert not set(bad[:8]) & set(decision.rejected)


def test_g3_minority_bound_matches_the_committee_corruption_bound():
    """No new assumption: a 6-of-9 attestation already tolerates f < n/3."""
    assert G3_MINORITY_MAX == pytest.approx(1.0 / 3.0)


def test_g3_gap_gate_can_suppress_rejection():
    state, honest, bad = _population(20, 5)
    rng = np.random.default_rng(0)
    evidences = {c: _evidence(rng.normal(size=8).astype(np.float32)) for c in honest[:8] + bad}
    decision, _ = apply_g3_rule(evidences, state, gap_min=99.0, update_state=False)
    assert "reputation" not in decision.thresholds


def test_g3_two_sided_rejects_an_anomalously_high_minority():
    """A7 scores ABOVE honest clients, so only a two-sided test could reach it."""
    state, honest, bad = _population(20, 5, bad_offset=+1.0)
    rng = np.random.default_rng(0)
    evidences = {c: _evidence(rng.normal(size=8).astype(np.float32)) for c in honest[:8] + bad}
    one_sided, _ = apply_g3_rule(evidences, state, update_state=False)
    two_sided, _ = apply_g3_rule(evidences, state, two_sided=True, update_state=False)
    assert not set(bad) & set(one_sided.rejected)
    assert set(bad) <= set(two_sided.rejected)


def test_g3_degenerates_to_the_magnitude_test_without_a_sketch():
    state = ReputationState()
    evidences = {
        "a": Evidence(level=DisclosureLevel.E1, commitment=b"\x00" * 32, norm=1.0),
        "b": Evidence(level=DisclosureLevel.E1, commitment=b"\x00" * 32, norm=1.0),
        "c": Evidence(level=DisclosureLevel.E1, commitment=b"\x00" * 32, norm=99.0),
    }
    decision, scores = apply_g3_rule(evidences, state, update_state=False)
    assert decision.rejected == ("c",)
    assert scores == {}


def test_g3_rule_id_declares_every_ablation_setting():
    """AG1 requires the applied rule to be named; ablations must not share an id."""
    ids = {
        g3_rule_id(population=p, accumulate=a, two_sided=t)
        for p in (True, False) for a in (True, False) for t in (True, False)
    }
    assert len(ids) == 8


# ------------------------------------------------- G2 must be frozen, provably
def test_g2_rule_is_unchanged_by_g3():
    """G2's published results are frozen. Its id and behaviour must not drift."""
    assert g2_rule_id() == "g2-dir-reputation-w3-3.0mad-norm1.5x/v1"
    state, honest, bad = _population(20, 5)
    rng = np.random.default_rng(0)
    evidences = {c: _evidence(rng.normal(size=8).astype(np.float32)) for c in honest[:8] + bad}
    decision, _ = apply_g2_rule(evidences, state, update_state=False)
    # G2 evaluates only this round's clients and uses median - 3*MAD.
    assert decision.rule_id == g2_rule_id()
    assert "reputation" in decision.thresholds


# ------------------------------------------------------------- A9 camouflage
def test_camouflage_spreads_intensities_and_is_deterministic():
    members = ["c4", "c1", "c3", "c0", "c2"]
    betas = camouflage_betas(members, 1.0)
    assert betas == camouflage_betas(list(reversed(members)), 1.0)
    values = [betas[c] for c in sorted(members)]
    assert values == sorted(values)          # a continuum, not a cluster
    assert values[0] == pytest.approx(0.2)   # spread over [0.2*beta, beta]
    assert values[-1] == pytest.approx(1.0)


def test_camouflage_costs_the_attacker_intensity():
    """Camouflage buys invisibility by attacking less hard -- reported, not hidden."""
    betas = camouflage_betas([f"c{i}" for i in range(6)], 0.9)
    assert np.mean(list(betas.values())) < 0.9


def test_camouflage_handles_a_single_attacker():
    assert camouflage_betas(["only"], 0.7) == {"only": 0.7}
    assert camouflage_betas([], 0.7) == {}


# --------------------------------------------- seed determinism (found in G3)
def test_client_seed_offset_is_stable_across_processes():
    """Python's hash() is salted per process; training seeds must not depend on it.

    Regression test for the defect found while analysing the first G3 confirmatory
    run: identical configurations dispatched to different worker processes trained
    differently, breaking the fixed-seed guarantee.
    """
    import subprocess
    import sys

    from bcflsrv.fl.experiment import client_seed_offset

    code = (
        "import sys; sys.path.insert(0, 'src');"
        "from bcflsrv.fl.experiment import client_seed_offset;"
        "print(client_seed_offset('client-001'))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert int(out.stdout.strip()) == client_seed_offset("client-001")


def test_client_seed_offset_separates_clients():
    from bcflsrv.fl.experiment import client_seed_offset

    offsets = {client_seed_offset(f"client-{i:03d}") % 100 for i in range(30)}
    assert len(offsets) > 20  # not colliding into a handful of buckets
