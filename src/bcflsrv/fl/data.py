"""Fashion-MNIST loading and non-IID partitioning for E-4/E-5.

Why a hand-rolled loader instead of torchvision
-----------------------------------------------
``torchvision`` is not installed, and installing it risks pulling a torch build that
does not match the one already present (`D-008`). Fashion-MNIST ships as four IDX
files that are a few dozen lines of numpy to parse, so the dependency risk is not
worth taking. The checksums below also pin the exact bytes, which torchvision would
not have given us.

Scope reminder
--------------
`LIT` Fashion-MNIST is a **controlled experimental environment**, not evidence about
production federated learning. It is used because it is a standard FL benchmark, it
trains on CPU in seconds, and it is not accuracy-saturated the way MNIST is, so
poisoning effects remain visible. No claim here transfers to a real deployment
without re-evaluation. See ``E4_E5_MATRIX.md`` section 10.
"""

from __future__ import annotations

import gzip
import hashlib
import struct
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

__all__ = ["FashionMNIST", "load_fashion_mnist", "dirichlet_partition", "ClientShard"]

# Mirrors are tried in order. GitHub first; the S3 site is the project's own host.
_MIRRORS = (
    "https://github.com/zalandoresearch/fashion-mnist/raw/master/data/fashion/",
    "http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/",
)

# SHA-256 of each file, computed from a verified download on 2026-09-04.
# Pinning the bytes is what makes "same data" a checkable claim rather than a hope.
_CHECKSUMS: Dict[str, str] = {
    "train-images-idx3-ubyte.gz": "3aede38d61863908ad78613f6a32ed271626dd12800ba2636569512369268a84",
    "train-labels-idx1-ubyte.gz": "a04f17134ac03560a47e3764e11b92fc97de4d1bfaf8ba1a3aa29af54cc90845",
    "t10k-images-idx3-ubyte.gz": "346e55b948d973a97e58d2351dde16a484bd415d4595297633bb08f03db6a073",
    "t10k-labels-idx1-ubyte.gz": "67da17c76eaffca5446c3361aaab5c3cd6d1c2608764d35dfb1850b086bf8dd5",
}

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


class DataError(Exception):
    """Dataset could not be obtained or failed verification."""


def _fetch(name: str, data_dir: Path) -> Path:
    """Download ``name`` if absent, then verify its checksum. Never trusts a cache."""
    data_dir.mkdir(parents=True, exist_ok=True)
    dest = data_dir / name

    if not dest.exists():
        last_error: Exception | None = None
        for base in _MIRRORS:
            try:
                req = urllib.request.Request(base + name, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=120) as response:
                    dest.write_bytes(response.read())
                break
            except Exception as exc:  # noqa: BLE001 - try the next mirror
                last_error = exc
        else:
            raise DataError(f"could not download {name} from any mirror: {last_error}")

    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != _CHECKSUMS[name]:
        raise DataError(
            f"checksum mismatch for {name}: expected {_CHECKSUMS[name]}, got {digest}. "
            "Delete the file and re-download."
        )
    return dest


def _read_idx(path: Path) -> np.ndarray:
    """Parse an IDX file (the format Fashion-MNIST ships in)."""
    with gzip.open(path, "rb") as fh:
        magic, = struct.unpack(">I", fh.read(4))
        n_dims = magic & 0xFF
        dims = struct.unpack(f">{n_dims}I", fh.read(4 * n_dims))
        return np.frombuffer(fh.read(), dtype=np.uint8).reshape(dims)


@dataclass(frozen=True)
class FashionMNIST:
    """Normalised Fashion-MNIST split into train and test."""

    x_train: np.ndarray  # (N, 1, 28, 28) float32 in [0, 1]
    y_train: np.ndarray  # (N,) int64
    x_test: np.ndarray
    y_test: np.ndarray

    @property
    def n_classes(self) -> int:
        return 10


def load_fashion_mnist(data_dir: Path | str | None = None) -> FashionMNIST:
    """Load Fashion-MNIST, downloading and verifying on first use."""
    directory = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    paths = {name: _fetch(name, directory) for name in _CHECKSUMS}

    def images(key: str) -> np.ndarray:
        raw = _read_idx(paths[key]).astype(np.float32) / 255.0
        return raw.reshape(-1, 1, 28, 28)

    return FashionMNIST(
        x_train=images("train-images-idx3-ubyte.gz"),
        y_train=_read_idx(paths["train-labels-idx1-ubyte.gz"]).astype(np.int64),
        x_test=images("t10k-images-idx3-ubyte.gz"),
        y_test=_read_idx(paths["t10k-labels-idx1-ubyte.gz"]).astype(np.int64),
    )


@dataclass(frozen=True)
class ClientShard:
    """One client's local dataset."""

    client_id: str
    indices: np.ndarray

    def __len__(self) -> int:
        return len(self.indices)


def dirichlet_partition(
    labels: np.ndarray,
    client_ids: Sequence[str],
    alpha: float = 0.5,
    seed: int = 0,
    min_per_client: int = 20,
) -> List[ClientShard]:
    """Partition indices across clients with label-Dirichlet non-IID skew.

    The standard convention in the FL literature `LIT`: for each class, draw a
    Dirichlet(alpha) vector over clients and split that class's samples accordingly.
    Small alpha means severe skew (a client may hold only one or two classes);
    large alpha approaches IID.

    ``alpha=0.5`` is the commonly used moderate-skew setting and is our default.

    **Why this matters for E-4.** Under non-IID data, honest clients legitimately
    produce updates that look like outliers. That is the source of the false-positive
    rate measured in E4.2, and it is the reason a rule with high TPR is not
    automatically a good rule.

    Args:
        labels: label array for the training set.
        client_ids: client identifiers, one shard each.
        alpha: Dirichlet concentration. Lower is more skewed.
        seed: RNG seed -- fixed for reproducibility.
        min_per_client: re-draw if any client would fall below this many samples,
            since a near-empty client produces meaningless updates.

    Raises:
        ValueError: if the minimum cannot be met after repeated attempts.
    """
    if alpha <= 0:
        raise ValueError(f"alpha must be positive, got {alpha}")
    n_clients = len(client_ids)
    if n_clients == 0:
        raise ValueError("need at least one client")

    rng = np.random.default_rng(seed)
    classes = np.unique(labels)

    for _attempt in range(20):
        buckets: List[List[int]] = [[] for _ in range(n_clients)]
        for cls in classes:
            idx = np.where(labels == cls)[0]
            rng.shuffle(idx)
            proportions = rng.dirichlet(np.repeat(alpha, n_clients))
            cuts = (np.cumsum(proportions) * len(idx)).astype(int)[:-1]
            for bucket, part in zip(buckets, np.split(idx, cuts)):
                bucket.extend(part.tolist())

        if all(len(b) >= min_per_client for b in buckets):
            return [
                ClientShard(cid, np.array(sorted(b), dtype=np.int64))
                for cid, b in zip(client_ids, buckets)
            ]

    raise ValueError(
        f"could not partition with >= {min_per_client} samples per client at "
        f"alpha={alpha} for {n_clients} clients; raise alpha or lower the minimum"
    )


def label_distribution(labels: np.ndarray, shards: Sequence[ClientShard]) -> np.ndarray:
    """Per-client class histogram -- used to report how skewed a partition actually is."""
    n_classes = int(labels.max()) + 1
    table = np.zeros((len(shards), n_classes), dtype=np.int64)
    for i, shard in enumerate(shards):
        counts = np.bincount(labels[shard.indices], minlength=n_classes)
        table[i] = counts
    return table
