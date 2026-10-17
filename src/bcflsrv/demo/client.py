"""FL Client abstraction for the BC-FL-SRV decentralized demonstration.

Each client:
  - Has a unique Ed25519 cryptographic identity (reuses bcflsrv.crypto.identity)
  - Holds a local data shard (non-IID Dirichlet partition of Fashion-MNIST)
  - Maintains a local copy of the current global model
  - Performs local training via the existing local_train() function
  - Produces a model update (delta) and a cryptographic commitment (SHA-256)
  - Signs its update commitment with its private key
  - Can verify it received the correct global model

Relationship to existing code
------------------------------
This module wraps bcflsrv.fl.model.{local_train, evaluate, fedavg} and
bcflsrv.crypto.identity.{Identity, SigContext} without modifying them.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from bcflsrv.crypto.identity import Identity, SigContext
from bcflsrv.fl.data import ClientShard, FashionMNIST
from bcflsrv.fl.model import TrainConfig, evaluate, get_flat_params, local_train, SmallCNN

__all__ = [
    "FLClient",
    "ClientUpdate",
    "commit_update",
    "verify_update_commitment",
]

_COMMIT_DOMAIN = b"BCFLSRV/demo/update-commit/v1"


def commit_update(client_id: str, fl_round: int, update: np.ndarray) -> bytes:
    """SHA-256 commitment to (client_id, fl_round, update_bytes).

    Including client_id and fl_round in the commitment prevents a client from
    replaying the same update across rounds, and prevents one client from
    submitting another's update.
    """
    update_bytes = update.astype(np.float32).tobytes()
    return hashlib.sha256(
        _COMMIT_DOMAIN
        + client_id.encode("utf-8")
        + fl_round.to_bytes(8, "big")
        + update_bytes
    ).digest()


def verify_update_commitment(
    client_id: str,
    fl_round: int,
    update: np.ndarray,
    claimed_commitment: bytes,
) -> bool:
    """Check that the update matches its commitment (used by the aggregation layer)."""
    return commit_update(client_id, fl_round, update) == claimed_commitment


@dataclass
class ClientUpdate:
    """Everything the server/aggregator receives from one client for one round."""

    client_id: str
    public_key: bytes            # Ed25519 raw public key (32 bytes)
    fl_round: int
    update: np.ndarray           # model delta, float32 flat vector
    commitment: bytes            # SHA-256 of (client_id, fl_round, update)
    signature: bytes             # Ed25519 sig over commitment in SUBMISSION context
    n_samples: int               # local dataset size (for weighted FedAvg)
    local_loss: float            # training loss on this client's data
    tampered: bool = False       # set by TamperingDemo to mark modified updates
    weight_norm: float = 0.0     # L2 norm of the uploaded weight update delta
    weight_stats: Dict[str, float] = field(default_factory=dict)  # min, max, mean, std
    layer_norms: Dict[str, float] = field(default_factory=dict)   # per-layer L2 norms

    def commitment_hex(self) -> str:
        return self.commitment.hex()

    def verify_signature(self) -> bool:
        """Verify the client's signature over its commitment."""
        from bcflsrv.crypto.identity import verify
        return verify(self.public_key, SigContext.SUBMISSION, self.commitment, self.signature)


class FLClient:
    """A single federated learning client with cryptographic identity.

    Args:
        seed_bytes: deterministic seed for Identity.from_seed() -- ensures
            reproducible identities across runs.
        shard: this client's local data partition.
        train_config: local training hyperparameters.
        n_classes: number of output classes (10 for Fashion-MNIST).
    """

    def __init__(
        self,
        seed_bytes: bytes,
        shard: ClientShard,
        train_config: Optional[TrainConfig] = None,
        n_classes: int = 10,
    ) -> None:
        self._identity = Identity.from_seed(seed_bytes)
        self.shard = shard
        self.train_config = train_config or TrainConfig(epochs=1, max_batches=15)
        self.n_classes = n_classes

        # Current global model params (set by distribute_global_model)
        self._global_params: Optional[np.ndarray] = None
        # History for diagnostics
        self._round_updates: List[ClientUpdate] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def client_id(self) -> str:
        """The stable hex identifier derived from the public key."""
        return self._identity.id

    @property
    def public_key(self) -> bytes:
        return self._identity.public_key

    @property
    def n_samples(self) -> int:
        return len(self.shard)

    def sign(self, message: bytes, context: SigContext = SigContext.SUBMISSION) -> bytes:
        """Sign a message using this client's Ed25519 identity."""
        return self._identity.sign(context, message)

    # ------------------------------------------------------------------
    # FL round participation
    # ------------------------------------------------------------------

    def receive_global_model(self, params: np.ndarray) -> None:
        """Store the server-broadcast global model parameters."""
        self._global_params = np.asarray(params, dtype=np.float32).copy()

    def train_and_submit(
        self,
        fl_round: int,
        dataset: FashionMNIST,
        seed_offset: int = 0,
    ) -> ClientUpdate:
        """Perform local training and return a signed update.

        The client trains from the current global model, computes the delta,
        commits to it, and signs the commitment with its Ed25519 key.
        """
        if self._global_params is None:
            raise RuntimeError(
                f"Client {self.client_id}: must call receive_global_model() first"
            )

        x = dataset.x_train[self.shard.indices]
        y = dataset.y_train[self.shard.indices]

        # Deterministic seed: combines client identity and round
        train_seed = (
            int.from_bytes(
                hashlib.sha256(
                    self._identity.public_key
                    + fl_round.to_bytes(8, "big")
                    + seed_offset.to_bytes(8, "big")
                ).digest()[:4],
                "big",
            )
        )

        # Local training -- returns update delta
        update = local_train(
            self._global_params.copy(),
            x, y,
            self.train_config,
            seed=train_seed,
            n_classes=self.n_classes,
        )

        # Evaluate local loss on current global model (before update)
        local_metrics = evaluate(self._global_params, x, y, self.n_classes)

        # Commitment and signature
        commitment = commit_update(self.client_id, fl_round, update)
        signature = self._identity.sign(SigContext.SUBMISSION, commitment)

        # Weight delta stats and layer breakdown
        w_norm = float(np.linalg.norm(update))
        w_stats = {
            "min": float(np.min(update)),
            "max": float(np.max(update)),
            "mean": float(np.mean(update)),
            "std": float(np.std(update)),
        }
        l_norms = {
            "conv1": float(np.linalg.norm(update[:80])) if len(update) >= 80 else 0.0,
            "conv2": float(np.linalg.norm(update[80:1248])) if len(update) >= 1248 else 0.0,
            "fc1": float(np.linalg.norm(update[1248:51488])) if len(update) >= 51488 else 0.0,
            "fc2": float(np.linalg.norm(update[51488:52138])) if len(update) >= 52138 else 0.0,
        }

        cu = ClientUpdate(
            client_id=self.client_id,
            public_key=self.public_key,
            fl_round=fl_round,
            update=update,
            commitment=commitment,
            signature=signature,
            n_samples=self.n_samples,
            local_loss=local_metrics["loss"],
            weight_norm=round(w_norm, 5),
            weight_stats={k: round(v, 6) for k, v in w_stats.items()},
            layer_norms={k: round(v, 5) for k, v in l_norms.items()},
        )
        self._round_updates.append(cu)
        return cu

class MaliciousClient(FLClient):
    """An infected FL client that executes adversarial attacks against the network.

    It intermittently injects broken weights, poisoned gradients, tampered
    payloads, or invalid signatures to rigorously test the multi-stage admission pipeline.
    """
    def __init__(self, seed_bytes: bytes, shard: ClientShard,
                 train_config: Optional[TrainConfig] = None,
                 n_classes: int = 10,
                 malice_rate: float = 0.5):
        super().__init__(seed_bytes, shard, train_config, n_classes)
        self.malice_rate = malice_rate
        self.is_infected = True
        self.is_malicious = True
        self.last_attack_type: Optional[str] = None
        self.attacks_executed: int = 0

    def train_and_submit(self, fl_round: int, dataset: FashionMNIST, seed_offset: int = 0) -> ClientUpdate:
        import random
        cu = super().train_and_submit(fl_round, dataset, seed_offset)

        if random.random() < self.malice_rate:
            attack_type = random.choice([
                "broken_weights",
                "poisoned_gradients",
                "tampered_bytes",
                "forged_signature",
            ])
            self.attacks_executed += 1
            self.last_attack_type = attack_type

            if attack_type == "broken_weights":
                # Inject high-amplitude noise and norm explosion
                noise = np.random.normal(0, 1.5, cu.update.shape).astype(np.float32)
                cu.update = (cu.update * 12.0) + noise
                cu.commitment = commit_update(self.client_id, fl_round, cu.update)
                cu.signature = self.sign(cu.commitment) # Valid sig, fails norm/G2
            elif attack_type == "poisoned_gradients":
                # Invert gradient trajectory to sabotage global consensus
                cu.update = -cu.update * 2.5
                cu.commitment = commit_update(self.client_id, fl_round, cu.update)
                cu.signature = self.sign(cu.commitment) # Valid sig, fails directional G2
            elif attack_type == "tampered_bytes":
                # In-flight MITM byte flipping after signing
                cu.update[:100] *= -5.0
                # Keep original commitment & signature -> fails commitment check
            elif attack_type == "forged_signature":
                # Forged cryptographic signature
                cu.signature = b"\x00" * 64

            cu.tampered = True
            cu.weight_norm = float(np.linalg.norm(cu.update))
            setattr(cu, "attack_type", attack_type)
            setattr(cu, "is_malicious", True)
            return cu

        return cu


