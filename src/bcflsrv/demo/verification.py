"""Update verification layer for the BC-FL-SRV demonstration.

Sits between client submissions and blockchain recording. Checks:

1. Signature verification  -- is the update from who it claims?
2. Commitment verification -- does the claimed hash match the actual update?
3. Norm check             -- is the update magnitude within plausible range?
4. Registered client check -- is this client in the known registry?

Tampering demonstration
-----------------------
:class:`TamperingDemo` provides three attack scenarios for the demo:
  * update_tampering  -- modify the update bytes after signing
  * commitment_forgery -- claim a commitment that doesn't match
  * identity_spoofing  -- submit using an unknown client id/key
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from bcflsrv.crypto.identity import verify, SigContext
from bcflsrv.demo.client import ClientUpdate, commit_update

__all__ = [
    "VerificationResult",
    "VerificationStatus",
    "UpdateVerifier",
    "TamperingDemo",
]


class VerificationStatus(Enum):
    ACCEPTED   = "accepted"
    REJECTED_SIG   = "rejected_sig"      # signature invalid
    REJECTED_COMMIT = "rejected_commit"  # commitment doesn't match update
    REJECTED_UNKNOWN = "rejected_unknown"  # client not in registry
    REJECTED_NORM  = "rejected_norm"     # update norm suspiciously large
    REJECTED_ROUND = "rejected_round"    # wrong round number
    REJECTED_TRUST = "rejected_trust"    # persistent trust score below safety threshold
    REJECTED_REP   = "rejected_rep"      # rejected by multi-round reputation (G2/G3)


@dataclass
class VerificationResult:
    client_id: str
    status: VerificationStatus
    detail: str = ""
    update_norm: float = 0.0
    commitment_hex: str = ""

    @property
    def accepted(self) -> bool:
        return self.status == VerificationStatus.ACCEPTED

    def to_ledger_value(self) -> str:
        """String stored in the blockchain verification_results dict."""
        return self.status.value


class UpdateVerifier:
    """Verify FL client updates before they enter the blockchain.

    Args:
        registry: mapping of client_id -> public_key for all known clients.
        max_update_norm: updates with L2 norm above this are flagged.
            Use None to disable.
        expected_round: if set, only accept updates for this round.
    """

    def __init__(
        self,
        registry: Dict[str, bytes],
        max_update_norm: Optional[float] = None,
        expected_round: Optional[int] = None,
        trust_scores: Optional[Dict[str, float]] = None,
        trust_threshold: float = 0.40,
    ) -> None:
        self.registry = dict(registry)
        self.max_update_norm = max_update_norm
        self.expected_round = expected_round
        self.trust_scores = dict(trust_scores) if trust_scores else {}
        self.trust_threshold = trust_threshold

    def verify(self, update: ClientUpdate) -> VerificationResult:
        """Run all verification checks on one client update."""
        cid = update.client_id

        # 0. Persistent Trust Score Firewall
        if self.trust_scores and cid in self.trust_scores:
            score = self.trust_scores[cid]
            if score < self.trust_threshold:
                return VerificationResult(
                    client_id=cid,
                    status=VerificationStatus.REJECTED_TRUST,
                    detail=f"Quarantined: Client trust score {score:.1%} below {self.trust_threshold:.1%} security gate",
                    commitment_hex=update.commitment.hex() if hasattr(update, "commitment") and update.commitment else "",
                )

        # 1. Known client?
        if cid not in self.registry:
            return VerificationResult(
                client_id=cid,
                status=VerificationStatus.REJECTED_UNKNOWN,
                detail=f"client {cid[:12]}... not in registry",
            )

        registered_pk = self.registry[cid]

        # 2. Correct round?
        if self.expected_round is not None and update.fl_round != self.expected_round:
            return VerificationResult(
                client_id=cid,
                status=VerificationStatus.REJECTED_ROUND,
                detail=f"expected round {self.expected_round}, got {update.fl_round}",
            )

        # 3. Signature valid?
        if not verify(registered_pk, SigContext.SUBMISSION, update.commitment, update.signature):
            return VerificationResult(
                client_id=cid,
                status=VerificationStatus.REJECTED_SIG,
                detail="Ed25519 signature failed",
                commitment_hex=update.commitment.hex(),
            )

        # 4. Commitment matches the actual update?
        expected_commit = commit_update(cid, update.fl_round, update.update)
        if expected_commit != update.commitment:
            return VerificationResult(
                client_id=cid,
                status=VerificationStatus.REJECTED_COMMIT,
                detail="SHA-256 commitment does not match update bytes",
                commitment_hex=update.commitment.hex(),
            )

        # 5. Norm check?
        norm = float(np.linalg.norm(update.update))
        if self.max_update_norm is not None and norm > self.max_update_norm:
            return VerificationResult(
                client_id=cid,
                status=VerificationStatus.REJECTED_NORM,
                detail=f"update L2 norm {norm:.3f} > threshold {self.max_update_norm:.3f}",
                update_norm=norm,
                commitment_hex=update.commitment.hex(),
            )

        return VerificationResult(
            client_id=cid,
            status=VerificationStatus.ACCEPTED,
            update_norm=norm,
            commitment_hex=update.commitment.hex(),
        )

    def verify_batch(
        self, updates: Sequence[ClientUpdate]
    ) -> List[VerificationResult]:
        return [self.verify(u) for u in updates]


class TamperingDemo:
    """Three deterministic tampering scenarios for the demonstration.

    Each method takes a real ClientUpdate and returns a *tampered* one that
    should be caught by UpdateVerifier.
    """

    @staticmethod
    def tamper_update_bytes(update: ClientUpdate) -> ClientUpdate:
        """Flip the sign of the first 100 parameters after signing.

        The signature and commitment are unchanged but no longer match the
        modified update -- commitment verification must catch this.
        """
        tampered_params = update.update.copy()
        tampered_params[:100] *= -5.0  # large perturbation
        return ClientUpdate(
            client_id=update.client_id,
            public_key=update.public_key,
            fl_round=update.fl_round,
            update=tampered_params,        # <-- modified
            commitment=update.commitment,   # <-- original (now wrong)
            signature=update.signature,
            n_samples=update.n_samples,
            local_loss=update.local_loss,
            tampered=True,
        )

    @staticmethod
    def forge_commitment(update: ClientUpdate) -> ClientUpdate:
        """Replace the commitment with a random hash (signature now invalid)."""
        fake_commitment = hashlib.sha256(b"forged" + update.commitment).digest()
        return ClientUpdate(
            client_id=update.client_id,
            public_key=update.public_key,
            fl_round=update.fl_round,
            update=update.update,
            commitment=fake_commitment,    # <-- bad commitment
            signature=update.signature,    # <-- sig was over original; fails
            n_samples=update.n_samples,
            local_loss=update.local_loss,
            tampered=True,
        )

    @staticmethod
    def spoof_identity(update: ClientUpdate, fake_client_id: str = "attacker-000") -> ClientUpdate:
        """Claim to be an unregistered client."""
        from bcflsrv.crypto.identity import Identity
        # Generate a brand-new key that isn't in the registry
        fake_identity = Identity.generate()
        fake_commitment = commit_update(fake_client_id, update.fl_round, update.update)
        fake_sig = fake_identity.sign(SigContext.SUBMISSION, fake_commitment)
        return ClientUpdate(
            client_id=fake_client_id,
            public_key=fake_identity.public_key,
            fl_round=update.fl_round,
            update=update.update,
            commitment=fake_commitment,
            signature=fake_sig,
            n_samples=update.n_samples,
            local_loss=update.local_loss,
            tampered=True,
        )

    @staticmethod
    def poison_direction(update: ClientUpdate, scale: float = -3.0) -> ClientUpdate:
        """Invert and amplify gradient direction to push model away from global convergence."""
        tampered_params = update.update.copy() * scale
        fake_commitment = commit_update(update.client_id, update.fl_round, tampered_params)
        return ClientUpdate(
            client_id=update.client_id,
            public_key=update.public_key,
            fl_round=update.fl_round,
            update=tampered_params,
            commitment=fake_commitment,
            signature=update.signature,  # Signature mismatch or directional failure
            n_samples=update.n_samples,
            local_loss=update.local_loss,
            tampered=True,
        )

    @staticmethod
    def exploding_norm(update: ClientUpdate, multiplier: float = 40.0) -> ClientUpdate:
        """Inject massive parameter updates to destabilize FedAvg aggregation."""
        tampered_params = update.update.copy() * multiplier
        fake_commitment = commit_update(update.client_id, update.fl_round, tampered_params)
        return ClientUpdate(
            client_id=update.client_id,
            public_key=update.public_key,
            fl_round=update.fl_round,
            update=tampered_params,
            commitment=fake_commitment,
            signature=update.signature,
            n_samples=update.n_samples,
            local_loss=update.local_loss,
            tampered=True,
        )

