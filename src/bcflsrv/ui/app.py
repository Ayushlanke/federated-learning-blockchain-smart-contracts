"""FastAPI backend application for the BC-FL-SRV Research & Testing Platform.

Exposes REST APIs for:
  - Experiment execution and control (start, pause, resume, stop, reset)
  - Live status, metrics, and logs
  - Replicated blockchain ledger explorer and live cryptographic verification
  - Clients and non-IID data distribution inspection
  - Live model inspection and Fashion-MNIST inference
  - Interactive cryptographic security and tampering tests
  - Multi-experiment benchmarking and comparison
  - Foundational BC-FL-SRV research results (E1-E5, G2, G3)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bcflsrv.demo.pipeline import DemoConfig
from bcflsrv.demo.runner import runner_instance
from bcflsrv.fl.model import TrainConfig

app = FastAPI(
    title="BC-FL-SRV Research Platform",
    description="Blockchain-Based Decentralized Federated Learning Research & Testing Software",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# Request Models
# ------------------------------------------------------------------

class ExperimentStartRequest(BaseModel):
    n_clients: int = Field(default=5, ge=2, le=20)
    n_rounds: int = Field(default=10, ge=1, le=50)
    dirichlet_alpha: float = Field(default=0.5, gt=0.0, le=10.0)
    epochs: int = Field(default=2, ge=1, le=5)
    max_batches: int = Field(default=40, ge=1, le=100)
    learning_rate: float = Field(default=0.03, gt=0.0, le=1.0)
    n_ledger_nodes: int = Field(default=3, ge=1, le=10)
    ledger_quorum: int = Field(default=2, ge=1, le=10)
    seed: int = Field(default=42)


class InferenceRequest(BaseModel):
    sample_index: int = Field(ge=0, le=9999)


class SecurityTestRequest(BaseModel):
    attack_type: str = Field(..., pattern="^(tampered_update|forged_commitment|unauthorized_client|block_tampering)$")


# ------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------

@app.get("/api/dashboard")
def get_dashboard() -> Dict[str, Any]:
    """Summary KPI cards and live system status."""
    return runner_instance.get_dashboard_summary()


@app.get("/api/charts")
def get_charts() -> Dict[str, Any]:
    """Time-series curves for accuracy, loss, participation, blocks, and runtime."""
    return runner_instance.get_charts_data()


@app.get("/api/clients")
def get_clients() -> List[Dict[str, Any]]:
    """Inspect all FL clients, identities, shard distributions, and local metrics."""
    return runner_instance.get_clients_info()


@app.get("/api/clients/transparency")
def get_clients_transparency() -> Dict[str, Any]:
    """Complete client transparency metrics: weight distributions, layer norms, and logs."""
    return runner_instance.get_clients_transparency()


@app.get("/api/blockchain")
def get_blockchain() -> List[Dict[str, Any]]:
    """Complete replicated blockchain block explorer."""
    return runner_instance.get_blockchain_info()


@app.get("/api/blockchain/uploads")
def get_blockchain_uploads() -> List[Dict[str, Any]]:
    """List all individual client model weight update uploads committed to the blockchain."""
    return runner_instance.get_blockchain_uploads()


@app.post("/api/blockchain/verify")
def verify_blockchain() -> Dict[str, Any]:
    """Execute live cryptographic hash-chain verification across all nodes."""
    return runner_instance.verify_chain_live()


@app.get("/api/model")
def get_model() -> Dict[str, Any]:
    """Model architecture, parameters count, current hash, and accuracy."""
    return runner_instance.get_model_info()


@app.get("/api/model/samples")
def get_samples(count: int = Query(default=12, ge=1, le=50)) -> List[Dict[str, Any]]:
    """Retrieve test Fashion-MNIST samples for live inference demo."""
    return runner_instance.get_test_samples(count=count)


@app.post("/api/model/inference")
def run_inference(req: InferenceRequest) -> Dict[str, Any]:
    """Run real inference on a Fashion-MNIST sample using current model weights."""
    try:
        return runner_instance.run_inference(req.sample_index)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/model/confusion_matrix")
def get_confusion_matrix() -> Dict[str, Any]:
    """Compute 10x10 confusion matrix on the test set."""
    return runner_instance.compute_confusion_matrix(max_samples=2000)


@app.post("/api/security/test")
def run_security_test(req: SecurityTestRequest) -> Dict[str, Any]:
    """Execute a real cryptographic attack and verify the defense layer."""
    try:
        return runner_instance.run_security_attack(req.attack_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------
# Experiment Controls
# ------------------------------------------------------------------

@app.post("/api/experiment/start")
def start_experiment(req: ExperimentStartRequest) -> Dict[str, Any]:
    """Start an interactive FL experiment."""
    cfg = DemoConfig(
        n_clients=req.n_clients,
        n_rounds=req.n_rounds,
        dirichlet_alpha=req.dirichlet_alpha,
        train_config=TrainConfig(
            epochs=req.epochs,
            max_batches=req.max_batches,
            lr=req.learning_rate,
        ),
        n_ledger_nodes=req.n_ledger_nodes,
        ledger_quorum=req.ledger_quorum,
        seed=req.seed,
    )
    try:
        runner_instance.start_experiment(cfg)
        return {"status": "started", "message": "Experiment launched successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/experiment/pause")
def pause_experiment() -> Dict[str, Any]:
    runner_instance.pause_experiment()
    return {"status": "paused"}


@app.post("/api/experiment/resume")
def resume_experiment() -> Dict[str, Any]:
    runner_instance.resume_experiment()
    return {"status": "resumed"}


@app.post("/api/experiment/stop")
def stop_experiment() -> Dict[str, Any]:
    runner_instance.stop_experiment()
    return {"status": "stopped"}


@app.post("/api/experiment/reset")
def reset_experiment() -> Dict[str, Any]:
    runner_instance.reset_experiment()
    return {"status": "idle"}


@app.get("/api/experiment/logs")
def get_logs() -> List[Dict[str, Any]]:
    """Fetch live timestamped application logs."""
    return [
        {
            "timestamp": log.timestamp,
            "round": log.round_id,
            "level": log.level,
            "message": log.message,
            "category": log.category,
        }
        for log in runner_instance.logs
    ]


@app.get("/api/experiments")
def list_experiments() -> List[Dict[str, Any]]:
    """List saved historical experiments."""
    return runner_instance.list_saved_experiments()


@app.get("/api/research")
def get_research_data() -> Dict[str, Any]:
    """Foundational BC-FL-SRV research system details (E1-E5, G2, G3)."""
    return {
        "title": "BC-FL-SRV: Verifiable Admission Decisions for Federated Learning",
        "problem_statement": (
            "In privacy-preserving FL with secure aggregation, the server cannot inspect individual updates. "
            "This creates an accountability hole (AG1): the server can arbitrarily drop honest clients or admit "
            "poisoned updates without external verifiability. BC-FL-SRV solves this with a rotating committee "
            "and append-only Merkle transcript."
        ),
        "experiments": [
            {
                "id": "E1",
                "name": "Verification Cost & Scaling (AG1 & AG3)",
                "description": "Demonstrates auditor inclusion check is independent of model size (64 B to 4 MiB) and logarithmic in transcript size.",
                "key_findings": [
                    "Auditor inclusion check takes ~1.55 µs regardless of model payload size (1.03x ratio for 65,536x model size increase).",
                    "Scaling: inclusion_µs = 0.761 * log2(T), R^2 = 0.985.",
                    "Merkle tree proof is 1,683x faster than linear signed log at T=16,384.",
                ],
            },
            {
                "id": "E2",
                "name": "Tamper Detection & Non-Equivocation",
                "description": "Tests auditor against 14 active attacks on admission decisions and transcript integrity.",
                "key_findings": [
                    "BC-FL-SRV detected 12 / 14 attack vectors (all in-scope attacks caught with 0 false positives).",
                    "Outperformed baseline B1 (signed log, 5/14 caught) and B2 (self-attesting aggregator, 6/14 caught).",
                ],
            },
            {
                "id": "E3",
                "name": "Committee Sortition & Threshold Corruption",
                "description": "Verifiable sortition seeded from transcript root prevents aggregator from packing committees.",
                "key_findings": [
                    "Honest quorum maintained under corrupt fraction f <= 0.33.",
                    "Transcript-derived entropy ensures forward unpredictability.",
                ],
            },
            {
                "id": "E4",
                "name": "Evidence Ladder & Non-IID False Positives",
                "description": "Evaluates 4 admission rules under Dirichlet non-IID data across alpha in [0.1, 1.0].",
                "key_findings": [
                    "Reveals fundamental trade-off: high poisoning TPR often incurs honest client exclusion under severe non-IID skew.",
                    "Bounded evidence disclosure prevents training data leakage while enabling verifiable admission.",
                ],
            },
            {
                "id": "E5",
                "name": "End-to-End FL Convergence with Admission Verification",
                "description": "Verifies that verifiable admission preserves model utility and convergence under label-flip attacks.",
                "key_findings": [
                    "Model achieves >80% accuracy under 20% malicious clients when verifiable admission is enabled.",
                ],
            },
        ],
        "distinction": {
            "research_system": "The admission verification layer: Merkle transcript, rotating committee, auditor, bounded evidence, and non-equivocation proofs.",
            "demo_system": "The decentralized FL layer: multiple clients, local PyTorch training, Ed25519 signatures, update commitments, and multi-node replicated blockchain ledger with quorum consensus.",
        },
    }


# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not yet built")
    return FileResponse(index_file)
