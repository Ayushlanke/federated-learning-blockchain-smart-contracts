"""Tests for the BC-FL-SRV Research Platform UI and backend APIs."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from bcflsrv.ui.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_index_html_serving(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "BC-FL-SRV" in res.text
    assert "Dashboard" in res.text
    assert "Blockchain Explorer" in res.text


def test_dashboard_api(client):
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "blocks_count" in data
    assert "current_accuracy" in data
    assert "chain_integrity_ok" in data


def test_charts_api(client):
    res = client.get("/api/charts")
    assert res.status_code == 200
    data = res.json()
    assert "rounds" in data
    assert "accuracy" in data
    assert "loss" in data
    assert "cum_blocks" in data


def test_model_and_samples_api(client):
    res = client.get("/api/model")
    assert res.status_code == 200
    m_data = res.json()
    assert "SmallCNN" in m_data["architecture"]
    assert m_data["parameter_count"] == 52138
    assert len(m_data["classes"]) == 10

    # Test samples
    res_samples = client.get("/api/model/samples?count=5")
    assert res_samples.status_code == 200
    samples = res_samples.json()
    assert len(samples) == 5
    assert "pixels" in samples[0]
    assert len(samples[0]["pixels"]) == 28
    assert len(samples[0]["pixels"][0]) == 28


def test_live_inference_api(client):
    res = client.post("/api/model/inference", json={"sample_index": 0})
    assert res.status_code == 200
    inf = res.json()
    assert "predicted_label_name" in inf
    assert "confidence" in inf
    assert len(inf["probabilities"]) == 10
    assert 0.0 <= inf["confidence"] <= 1.0


def test_security_attack_apis(client):
    attacks = [
        "tampered_update",
        "forged_commitment",
        "unauthorized_client",
    ]
    for att in attacks:
        res = client.post("/api/security/test", json={"attack_type": att})
        assert res.status_code == 200
        data = res.json()
        assert data["defense_successful"] is True
        assert "defense_layer" in data


def test_blockchain_and_verification_api(client):
    res = client.get("/api/blockchain")
    assert res.status_code == 200
    blocks = res.json()
    assert isinstance(blocks, list)

    res_verify = client.post("/api/blockchain/verify")
    assert res_verify.status_code == 200
    verif = res_verify.json()
    assert "valid" in verif
    assert "nodes" in verif


def test_research_api(client):
    res = client.get("/api/research")
    assert res.status_code == 200
    data = res.json()
    assert "experiments" in data
    assert len(data["experiments"]) >= 5
    assert "distinction" in data


def test_model_verification_api(client):
    res = client.post("/api/model/verify")
    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is True
    assert "accuracy" in data
    assert "loss" in data
    assert "model_hash" in data
    assert "class_accuracies" in data
    assert len(data["class_accuracies"]) == 10
    assert "proof_signature" in data


def test_system_audit_api(client):
    res = client.get("/api/system/audit")
    assert res.status_code == 200
    data = res.json()
    assert data["all_passed"] is True
    assert "checks" in data
    assert len(data["checks"]) == 5
    assert "audit_timestamp" in data


def test_latencies_breakdown_api(client):
    res = client.get("/api/system/latencies")
    assert res.status_code == 200
    data = res.json()
    assert "blockchain_type" in data
    assert "consensus_protocol" in data
    assert "transactions_throughput_tps" in data
    assert "stage_latencies" in data
    assert "admission_ms" in data["stage_latencies"]
    assert "client_admission_audit" in data

    # Backward compatibility alias
    res_alias = client.get("/api/gas/breakdown")
    assert res_alias.status_code == 200


def test_custom_inference_api(client):
    # Test valid 784-length pixel payload
    pixels = [0.0] * 784
    # Set a small test box in the center
    for r in range(10, 18):
        for c in range(10, 18):
            pixels[r * 28 + c] = 0.8
    res = client.post("/api/model/inference/custom", json={"pixels": pixels})
    assert res.status_code == 200
    data = res.json()
    assert "predicted_label_id" in data
    assert "predicted_label_name" in data
    assert "confidence" in data
    assert "probabilities" in data
    assert len(data["probabilities"]) == 10



