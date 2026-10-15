"""Lightweight permissioned blockchain / distributed ledger for FL events.

Architecture notes
------------------
This is a **research/demonstration blockchain**, NOT a cryptocurrency, and NOT
Ethereum or any external infrastructure.

What IS decentralised here:
  * The chain is **replicated** across N simulated ledger nodes.
  * Any node can receive a block proposal.
  * All nodes verify the block before accepting it.
  * A block is only committed when quorum_size nodes accept it.
  * Each node independently verifies hash chaining.

What is honestly acknowledged as simulated:
  * Nodes run in the same process (thread-safe shared state, no network).
  * Consensus is synchronous (proposal → vote → commit in one call).
  * There is no Byzantine-fault-tolerant consensus algorithm (PBFT/Tendermint).
  * This is a demonstration of the FL+blockchain concept, not a production system.

Block structure
---------------
Each block contains FL-specific fields:
  - index               sequential block number
  - prev_hash           SHA-256 of the previous block's canonical bytes
  - fl_round            FL round this block records
  - event_type          one of ROUND_START / UPDATE_SUBMISSION / AGGREGATION / ROUND_END
  - participating_clients  sorted list of client ids in this round
  - update_commitments  dict[client_id -> hex(sha256(update_bytes))]
  - verification_results dict[client_id -> "accepted" | "rejected" | "tampered"]
  - aggregation_commitment  hex(sha256(global_model_bytes)) -- only on AGGREGATION blocks
  - global_model_accuracy   float accuracy -- only on AGGREGATION blocks
  - timestamp           ISO-8601 wall-clock string
  - block_hash          SHA-256 of all of the above (excluding block_hash itself)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


__all__ = [
    "BlockEvent",
    "Block",
    "LedgerNode",
    "DistributedLedger",
    "BlockVerificationError",
]


class BlockEvent(Enum):
    ROUND_START    = "ROUND_START"
    UPDATE_SUBMIT  = "UPDATE_SUBMIT"
    AGGREGATION    = "AGGREGATION"
    ROUND_END      = "ROUND_END"
    TAMPERING_DETECTED = "TAMPERING_DETECTED"


@dataclass
class Block:
    """One block in the FL blockchain."""

    index: int
    prev_hash: str                    # hex SHA-256 of previous block
    fl_round: int
    event_type: BlockEvent
    timestamp: str

    # FL payload -- some fields are round-specific
    participating_clients: List[str] = field(default_factory=list)
    update_commitments: Dict[str, str] = field(default_factory=dict)
    verification_results: Dict[str, str] = field(default_factory=dict)
    aggregation_commitment: str = ""      # SHA-256 of global model params
    global_model_accuracy: float = -1.0  # -1 means "not recorded in this block"
    global_model_loss: float = -1.0
    accepted_count: int = 0
    rejected_count: int = 0
    extra: Dict[str, object] = field(default_factory=dict)

    # Computed after all other fields are set
    block_hash: str = ""

    # ------------------------------------------------------------------
    # Hash / serialisation
    # ------------------------------------------------------------------

    def _payload_bytes(self) -> bytes:
        """Canonical bytes for hashing -- block_hash field is excluded."""
        obj = {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "fl_round": self.fl_round,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "participating_clients": sorted(self.participating_clients),
            "update_commitments": {k: self.update_commitments[k]
                                   for k in sorted(self.update_commitments)},
            "verification_results": {k: self.verification_results[k]
                                     for k in sorted(self.verification_results)},
            "aggregation_commitment": self.aggregation_commitment,
            "global_model_accuracy": self.global_model_accuracy,
            "global_model_loss": self.global_model_loss,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "extra": self.extra,
        }
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_hash(self) -> str:
        return hashlib.sha256(self._payload_bytes()).hexdigest()

    def seal(self) -> "Block":
        """Compute and set block_hash. Returns self for chaining."""
        self.block_hash = self.compute_hash()
        return self

    def verify_hash(self) -> bool:
        return self.block_hash == self.compute_hash()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        d = dict(d)
        d["event_type"] = BlockEvent(d["event_type"])
        return cls(**d)

    def short_hash(self) -> str:
        return self.block_hash[:16] if self.block_hash else "unsealed"

    def __repr__(self) -> str:
        return (
            f"<Block #{self.index} round={self.fl_round} "
            f"event={self.event_type.value} hash={self.short_hash()}...>"
        )


GENESIS_HASH = "0" * 64  # conventional all-zero previous hash for block 0


class BlockVerificationError(Exception):
    """A block failed chain or integrity verification."""


class LedgerNode:
    """One participant in the distributed ledger.

    Each node holds its own independent copy of the chain and independently
    verifies every block before appending. A block is only appended when
    the ledger's quorum is reached (managed by DistributedLedger).
    """

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self._chain: List[Block] = []

    # ------------------------------------------------------------------

    @property
    def height(self) -> int:
        return len(self._chain)

    @property
    def tip_hash(self) -> str:
        if not self._chain:
            return GENESIS_HASH
        return self._chain[-1].block_hash

    @property
    def chain(self) -> List[Block]:
        return list(self._chain)

    # ------------------------------------------------------------------

    def verify_block(self, block: Block) -> Tuple[bool, str]:
        """Check a proposed block for structural validity.

        Returns (ok, reason). Reason is empty string when ok.
        """
        # 1. Hash integrity
        if not block.verify_hash():
            return False, "block_hash mismatch"

        # 2. Index must be next in chain
        expected_index = self.height
        if block.index != expected_index:
            return False, f"expected index {expected_index}, got {block.index}"

        # 3. prev_hash must match our tip
        if block.prev_hash != self.tip_hash:
            return False, (
                f"prev_hash {block.prev_hash[:16]}... does not match "
                f"tip {self.tip_hash[:16]}..."
            )

        return True, ""

    def append(self, block: Block) -> None:
        """Append a pre-verified block (called by DistributedLedger after quorum)."""
        ok, reason = self.verify_block(block)
        if not ok:
            raise BlockVerificationError(
                f"Node {self.node_id} rejected block #{block.index}: {reason}"
            )
        self._chain.append(block)

    def verify_chain(self) -> Tuple[bool, Optional[int]]:
        """Walk the full chain and check every hash link.

        Returns (ok, first_bad_index). first_bad_index is None when ok.
        """
        prev = GENESIS_HASH
        for blk in self._chain:
            if blk.prev_hash != prev:
                return False, blk.index
            if not blk.verify_hash():
                return False, blk.index
            prev = blk.block_hash
        return True, None

    def get_block(self, index: int) -> Optional[Block]:
        if 0 <= index < len(self._chain):
            return self._chain[index]
        return None


class DistributedLedger:
    """Multi-node replicated ledger with synchronous quorum consensus.

    Decentralisation model
    ----------------------
    * N nodes, each with its own independent chain copy.
    * A block is proposed to ALL nodes.
    * Each node votes yes/no independently.
    * If >= quorum_size nodes accept, the block is committed to ALL nodes.
    * If < quorum_size nodes accept, the block is rejected.

    This simulates the core property of a permissioned distributed ledger:
    no single node can unilaterally add a block.
    """

    def __init__(self, n_nodes: int = 3, quorum_size: int = 2) -> None:
        if quorum_size > n_nodes:
            raise ValueError(f"quorum_size {quorum_size} > n_nodes {n_nodes}")
        self.n_nodes = n_nodes
        self.quorum_size = quorum_size
        self.nodes: List[LedgerNode] = [
            LedgerNode(f"ledger-node-{i}") for i in range(n_nodes)
        ]
        self._next_index: int = 0

    # ------------------------------------------------------------------
    # Block creation helpers
    # ------------------------------------------------------------------

    def _make_timestamp(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _tip_hash(self) -> str:
        """Tip hash from node 0 (all nodes are in sync after every commit)."""
        return self.nodes[0].tip_hash

    def propose_block(
        self,
        fl_round: int,
        event_type: BlockEvent,
        *,
        participating_clients: Optional[List[str]] = None,
        update_commitments: Optional[Dict[str, str]] = None,
        verification_results: Optional[Dict[str, str]] = None,
        aggregation_commitment: str = "",
        global_model_accuracy: float = -1.0,
        global_model_loss: float = -1.0,
        accepted_count: int = 0,
        rejected_count: int = 0,
        extra: Optional[Dict[str, object]] = None,
    ) -> Tuple[Optional[Block], List[str]]:
        """Build a block, run quorum vote, and commit if approved.

        Returns (committed_block, rejection_reasons).
        committed_block is None if quorum was not reached.
        """
        block = Block(
            index=self._next_index,
            prev_hash=self._tip_hash(),
            fl_round=fl_round,
            event_type=event_type,
            timestamp=self._make_timestamp(),
            participating_clients=sorted(participating_clients or []),
            update_commitments=dict(update_commitments or {}),
            verification_results=dict(verification_results or {}),
            aggregation_commitment=aggregation_commitment,
            global_model_accuracy=global_model_accuracy,
            global_model_loss=global_model_loss,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            extra=dict(extra or {}),
        ).seal()

        # Quorum vote
        votes_yes = 0
        rejection_reasons: List[str] = []
        for node in self.nodes:
            ok, reason = node.verify_block(block)
            if ok:
                votes_yes += 1
            else:
                rejection_reasons.append(f"{node.node_id}: {reason}")

        if votes_yes < self.quorum_size:
            return None, rejection_reasons

        # Commit to all nodes
        for node in self.nodes:
            node.append(block)
        self._next_index += 1
        return block, []

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def height(self) -> int:
        return self._next_index

    def get_block(self, index: int) -> Optional[Block]:
        return self.nodes[0].get_block(index)

    def all_blocks(self) -> List[Block]:
        return self.nodes[0].chain

    def verify_all_nodes(self) -> Dict[str, Tuple[bool, Optional[int]]]:
        """Verify chain integrity on every node independently."""
        return {node.node_id: node.verify_chain() for node in self.nodes}

    def chains_are_consistent(self) -> bool:
        """All nodes must have valid and identical chains at every height."""
        if not self.nodes:
            return True
        if any(not node.verify_chain()[0] for node in self.nodes):
            return False
        reference = [b.block_hash for b in self.nodes[0].chain]
        return all(
            [b.block_hash for b in node.chain] == reference
            for node in self.nodes[1:]
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path | str) -> None:
        """Save chain (from node 0) as JSONL."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for blk in self.nodes[0].chain:
                json.dump(blk.to_dict(), fh)
                fh.write("\n")

    @classmethod
    def load_chain(cls, path: Path | str) -> List[Block]:
        """Load blocks from a JSONL file (for offline analysis)."""
        blocks = []
        with Path(path).open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    blocks.append(Block.from_dict(json.loads(line)))
        return blocks

    def summary(self) -> str:
        lines = [
            f"DistributedLedger: {self.n_nodes} nodes, quorum={self.quorum_size}",
            f"  Chain height: {self.height} blocks",
            f"  Chains consistent: {self.chains_are_consistent()}",
        ]
        for node in self.nodes:
            ok, bad = node.verify_chain()
            status = "OK" if ok else f"BROKEN at block {bad}"
            lines.append(f"  {node.node_id}: {status}")
        return "\n".join(lines)
