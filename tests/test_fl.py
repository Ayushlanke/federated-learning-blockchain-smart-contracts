"""Tests for the federated-learning layer (E-4/E-5 machinery).

Dataset-dependent tests are marked ``slow`` and skipped if Fashion-MNIST has not been
downloaded, so the suite stays runnable offline.
"""

from __future__ import annotations

import numpy as np
import pytest

from bcflsrv.fl.attacks import (
    AttackConfig,
    AttackType,
    apply_attack,
    flip_labels,
    is_data_attack,
    select_malicious,
)
from bcflsrv.fl.data import DEFAULT_DATA_DIR, dirichlet_partition, label_distribution
from bcflsrv.fl.evidence import (
    DisclosureLevel,
    apply_rule,
    encode_evidence,
    rule_id_for,
)
from bcflsrv.fl.masking import (
    MaskingError,
    aggregate_masked,
    aggregate_masked_mean,
    mask_updates,
    pairwise_mask,
)
from bcflsrv.fl.model import (
    SmallCNN,
    count_parameters,
    fedavg,
    get_flat_params,
    set_flat_params,
)

DIM = 256
requires_data = pytest.mark.skipif(
    not (DEFAULT_DATA_DIR / "t10k-labels-idx1-ubyte.gz").exists(),
    reason="Fashion-MNIST not downloaded",
)


def rand(dim: int = DIM, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(dim).astype(np.float32)


# --------------------------------------------------------------------------
# Model and flat-vector round-tripping
# --------------------------------------------------------------------------

def test_model_is_small_enough_for_cpu():
    n = count_parameters(SmallCNN())
    assert 10_000 < n < 100_000, f"model has {n} params; matrix section 7 targets < 100k"


def test_flat_param_round_trip():
    model = SmallCNN()
    flat = get_flat_params(model)
    perturbed = flat + 0.01
    set_flat_params(model, perturbed)
    assert np.allclose(get_flat_params(model), perturbed, atol=1e-6)


def test_set_flat_params_rejects_wrong_length():
    with pytest.raises((ValueError, RuntimeError)):
        set_flat_params(SmallCNN(), np.zeros(10, dtype=np.float32))


def test_fedavg_is_a_mean():
    a, b = np.ones(4, dtype=np.float32), np.full(4, 3.0, dtype=np.float32)
    assert np.allclose(fedavg([a, b]), 2.0)
    assert np.allclose(fedavg([a, b], weights=[3.0, 1.0]), 1.5)


def test_fedavg_rejects_bad_input():
    with pytest.raises(ValueError):
        fedavg([])
    with pytest.raises(ValueError):
        fedavg([np.ones(3)], weights=[1.0, 2.0])
    with pytest.raises(ValueError):
        fedavg([np.ones(3)], weights=[0.0])


# --------------------------------------------------------------------------
# Evidence ladder
# --------------------------------------------------------------------------

def test_disclosure_size_increases_up_the_ladder():
    """The ladder must actually be a ladder: more disclosure means more bytes."""
    u, prev = rand(), rand(seed=1)
    sizes = [
        encode_evidence(lvl, u, prev, projection_seed=7).size_bytes()
        for lvl in DisclosureLevel
    ]
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_e3_sketch_is_much_smaller_than_the_update():
    """E3 is the key rung: O(d') not O(N). That is what keeps cost independent of N."""
    u = rand(50_000)
    e3 = encode_evidence(DisclosureLevel.E3, u, None, 7)
    e4 = encode_evidence(DisclosureLevel.E4, u, None, 7)
    assert e3.vector is not None and e3.vector.size == 64
    assert e3.size_bytes() < e4.size_bytes() / 100


def test_evidence_digest_binds_content():
    u, prev = rand(), rand(seed=1)
    a = encode_evidence(DisclosureLevel.E2, u, prev, 7)
    b = encode_evidence(DisclosureLevel.E2, u * 1.01, prev, 7)
    assert a.digest() != b.digest()
    assert a.digest() == encode_evidence(DisclosureLevel.E2, u, prev, 7).digest()


def test_projection_is_deterministic_given_the_seed():
    """Client and committee must derive the same matrix or sketches are incomparable."""
    u = rand()
    a = encode_evidence(DisclosureLevel.E3, u, None, 42)
    b = encode_evidence(DisclosureLevel.E3, u, None, 42)
    c = encode_evidence(DisclosureLevel.E3, u, None, 43)
    assert np.array_equal(a.vector, b.vector)
    assert not np.array_equal(a.vector, c.vector)


def test_e0_admits_everything():
    ev = {f"c{i}": encode_evidence(DisclosureLevel.E0, rand(seed=i), None, 7) for i in range(5)}
    decision = apply_rule(DisclosureLevel.E0, ev)
    assert len(decision.admitted) == 5 and not decision.rejected


def test_norm_rule_rejects_a_scaled_outlier():
    ev = {f"c{i}": encode_evidence(DisclosureLevel.E1, rand(seed=i), None, 7) for i in range(8)}
    ev["evil"] = encode_evidence(DisclosureLevel.E1, rand(seed=99) * 20, None, 7)
    decision = apply_rule(DisclosureLevel.E1, ev)
    assert "evil" in decision.rejected


def test_distance_rule_rejects_an_off_manifold_update():
    base = rand(seed=5)
    ev = {
        f"c{i}": encode_evidence(DisclosureLevel.E4, base + 0.01 * rand(seed=i), None, 7)
        for i in range(8)
    }
    ev["evil"] = encode_evidence(DisclosureLevel.E4, -base, None, 7)
    decision = apply_rule(DisclosureLevel.E4, ev)
    assert "evil" in decision.rejected


def test_rule_is_deterministic():
    """AG1 is meaningless unless the rule is a function of recorded inputs."""
    ev = {f"c{i}": encode_evidence(DisclosureLevel.E4, rand(seed=i), None, 7) for i in range(6)}
    assert apply_rule(DisclosureLevel.E4, ev) == apply_rule(DisclosureLevel.E4, ev)


def test_rule_ids_are_distinct_and_stable():
    ids = [rule_id_for(lvl) for lvl in DisclosureLevel]
    assert len(set(ids)) == len(ids)
    assert all("/v1" in i for i in ids)


def test_empty_round_is_handled():
    decision = apply_rule(DisclosureLevel.E2, {})
    assert decision.admitted == () and decision.rejected == ()


# --------------------------------------------------------------------------
# Attacks
# --------------------------------------------------------------------------

def test_sign_flip_reverses_direction_but_keeps_norm():
    u = rand()
    out = apply_attack(u, AttackConfig(attack=AttackType.SIGN_FLIP))
    assert np.allclose(out, -u)
    assert np.isclose(np.linalg.norm(out), np.linalg.norm(u))


def test_scaled_attack_inflates_the_norm():
    u = rand()
    out = apply_attack(u, AttackConfig(attack=AttackType.SCALED, scale=10.0))
    assert np.isclose(np.linalg.norm(out), 10 * np.linalg.norm(u), rtol=1e-4)


def test_none_attack_is_identity():
    u = rand()
    assert np.array_equal(apply_attack(u, AttackConfig()), u)


def test_label_flip_is_an_involution():
    y = np.arange(10)
    assert np.array_equal(flip_labels(flip_labels(y)), y)
    assert np.array_equal(flip_labels(y), np.array([9, 8, 7, 6, 5, 4, 3, 2, 1, 0]))


def test_data_attacks_are_classified_correctly():
    assert is_data_attack(AttackType.LABEL_FLIP)
    assert is_data_attack(AttackType.SLOW_DRIFT)
    assert not is_data_attack(AttackType.SIGN_FLIP)
    assert not is_data_attack(AttackType.SCALED)


@pytest.mark.parametrize("beta", [0.25, 0.5, 0.9, 1.1, 1.5])
def test_slow_drift_lands_at_beta_times_the_threshold(beta):
    """The whole attack: sit at beta * threshold, inside the rule when beta < 1."""
    honest, malicious = rand(seed=1), rand(seed=2)
    threshold = 5.0
    out = apply_attack(
        honest,
        AttackConfig(attack=AttackType.SLOW_DRIFT, beta=beta),
        malicious_update=malicious,
        norm_threshold=threshold,
    )
    assert np.isclose(np.linalg.norm(out), beta * threshold, rtol=1e-4)


def test_slow_drift_preserves_the_malicious_direction():
    """Only the magnitude is tuned; the direction stays hostile."""
    malicious = rand(seed=2)
    out = apply_attack(
        rand(seed=1),
        AttackConfig(attack=AttackType.SLOW_DRIFT, beta=0.9),
        malicious_update=malicious,
        norm_threshold=5.0,
    )
    cosine = np.dot(out, malicious) / (np.linalg.norm(out) * np.linalg.norm(malicious))
    assert cosine > 0.999


def test_slow_drift_without_a_threshold_falls_back_to_label_flip():
    malicious = rand(seed=2)
    out = apply_attack(
        rand(seed=1),
        AttackConfig(attack=AttackType.SLOW_DRIFT),
        malicious_update=malicious,
        norm_threshold=None,
    )
    assert np.array_equal(out, malicious)


def test_data_attacks_require_a_malicious_update():
    for attack in (AttackType.LABEL_FLIP, AttackType.SLOW_DRIFT):
        with pytest.raises(ValueError):
            apply_attack(rand(), AttackConfig(attack=attack))


def test_malicious_selection_is_deterministic_and_correctly_sized():
    ids = [f"c{i:02d}" for i in range(30)]
    a = select_malicious(ids, 0.2, seed=7)
    assert a == select_malicious(ids, 0.2, seed=7)
    assert len(a) == 6
    assert select_malicious(ids, 0.0, seed=7) == frozenset()
    with pytest.raises(ValueError):
        select_malicious(ids, 1.5, seed=7)


# --------------------------------------------------------------------------
# Simplified additive masking -- NOT production secure aggregation
# --------------------------------------------------------------------------

def test_pairwise_masks_are_exact_negatives():
    a = pairwise_mask("alice", "bob", 3, DIM)
    b = pairwise_mask("bob", "alice", 3, DIM)
    assert np.allclose(a, -b)


def test_masks_differ_across_rounds():
    """Reusing a mask would let an observer cancel it by subtracting two rounds."""
    assert not np.allclose(
        pairwise_mask("alice", "bob", 1, DIM), pairwise_mask("alice", "bob", 2, DIM)
    )


def test_masked_sum_equals_the_true_sum():
    updates = {f"c{i}": rand(DIM, seed=i) for i in range(5)}
    masked = mask_updates(updates, round_id=3)
    total = aggregate_masked(masked, sorted(updates))
    assert np.allclose(total, sum(updates.values()), atol=1e-3)


def test_masked_mean_equals_the_true_mean():
    updates = {f"c{i}": rand(DIM, seed=i) for i in range(6)}
    masked = mask_updates(updates, round_id=1)
    mean = aggregate_masked_mean(masked, sorted(updates))
    assert np.allclose(mean, np.stack(list(updates.values())).mean(axis=0), atol=1e-3)


def test_masked_vector_hides_the_update():
    """The property the whole design assumes: the aggregator cannot read an update."""
    updates = {f"c{i}": rand(DIM, seed=i) for i in range(5)}
    masked = mask_updates(updates, round_id=3)
    for cid, original in updates.items():
        assert not np.allclose(masked[cid], original, atol=1e-2)
        # And it is not merely scaled or shifted: correlation is destroyed.
        corr = np.corrcoef(masked[cid], original)[0, 1]
        assert abs(corr) < 0.5, f"{cid} masked vector still correlates {corr:.2f}"


def test_missing_participant_aborts_rather_than_corrupting():
    """No dropout recovery: fail loudly instead of returning a wrong aggregate."""
    updates = {f"c{i}": rand(DIM, seed=i) for i in range(4)}
    masked = mask_updates(updates, round_id=2)
    del masked["c2"]
    with pytest.raises(MaskingError):
        aggregate_masked(masked, sorted(updates))


def test_masking_requires_at_least_two_participants():
    with pytest.raises(MaskingError):
        mask_updates({"solo": rand(DIM)}, round_id=1)


def test_masking_rejects_inconsistent_dimensions():
    with pytest.raises(MaskingError):
        mask_updates({"a": rand(8), "b": rand(16)}, round_id=1)


# --------------------------------------------------------------------------
# Non-IID partitioning
# --------------------------------------------------------------------------

def test_dirichlet_partition_is_deterministic_and_covers_the_data():
    labels = np.repeat(np.arange(10), 200)
    ids = [f"c{i}" for i in range(8)]
    a = dirichlet_partition(labels, ids, alpha=0.5, seed=3)
    b = dirichlet_partition(labels, ids, alpha=0.5, seed=3)
    assert [s.indices.tolist() for s in a] == [s.indices.tolist() for s in b]
    assert sum(len(s) for s in a) == len(labels)
    all_idx = np.concatenate([s.indices for s in a])
    assert len(np.unique(all_idx)) == len(labels), "shards must be disjoint"


def test_low_alpha_is_more_skewed_than_high_alpha():
    """The point of Dirichlet partitioning: alpha controls how non-IID it is."""
    labels = np.repeat(np.arange(10), 300)
    ids = [f"c{i}" for i in range(10)]

    def mean_classes_per_client(alpha: float) -> float:
        shards = dirichlet_partition(labels, ids, alpha=alpha, seed=1)
        table = label_distribution(labels, shards)
        return float((table > 0).sum(axis=1).mean())

    assert mean_classes_per_client(0.1) < mean_classes_per_client(10.0)


def test_partition_rejects_bad_parameters():
    labels = np.repeat(np.arange(10), 50)
    with pytest.raises(ValueError):
        dirichlet_partition(labels, ["a", "b"], alpha=0.0)
    with pytest.raises(ValueError):
        dirichlet_partition(labels, [], alpha=0.5)


@requires_data
def test_real_dataset_loads_with_expected_shape():
    from bcflsrv.fl.data import load_fashion_mnist

    ds = load_fashion_mnist()
    assert ds.x_train.shape == (60000, 1, 28, 28)
    assert ds.x_test.shape == (10000, 1, 28, 28)
    assert ds.y_train.shape == (60000,)
    assert 0.0 <= ds.x_train.min() and ds.x_train.max() <= 1.0
    assert set(np.unique(ds.y_train).tolist()) == set(range(10))


def test_masked_sum_precision_is_acceptable():
    """Large masks hide better but cost float32 precision. Measure the trade-off.

    Masks cancel exactly in real arithmetic; in float32 they do not. The residual
    error must stay far below the scale at which any admission rule operates.
    """
    updates = {f"c{i}": rand(DIM, seed=i) for i in range(8)}
    masked = mask_updates(updates, round_id=5)
    recovered = aggregate_masked(masked, sorted(updates))
    truth = sum(updates.values())
    rel_error = np.linalg.norm(recovered - truth) / np.linalg.norm(truth)
    assert rel_error < 1e-2, f"masking lost too much precision: {rel_error:.2e}"


def test_mask_scale_is_documented_and_large():
    """The constant is load-bearing for the hiding property; guard it."""
    from bcflsrv.fl.masking import MASK_SCALE

    assert MASK_SCALE >= 10.0
