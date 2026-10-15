"""Small CNN, local training, and flat-vector update handling for E-4/E-5.

Deliberately small. The research question is about admission decisions, not about
model quality, so the model exists to make attacks and defences *visible* at a size
that runs on 12 CPU cores in seconds per round (`E4_E5_MATRIX.md` section 7).

Updates as flat vectors
-----------------------
Everything downstream -- evidence encoders, admission rules, attacks, masking -- works
on a single flat float32 vector per client. Keeping one canonical representation
means the rules never need to know the architecture, and swapping the model does not
ripple through the experiment code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

__all__ = [
    "SmallCNN",
    "count_parameters",
    "get_flat_params",
    "set_flat_params",
    "local_train",
    "evaluate",
    "TrainConfig",
]


class SmallCNN(nn.Module):
    """Compact CNN for 28x28 grayscale. Roughly 30k parameters."""

    def __init__(self, n_classes: int = 10) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(1, 8, 3, padding=1)
        self.conv2 = nn.Conv2d(8, 16, 3, padding=1)
        self.fc1 = nn.Linear(16 * 7 * 7, 64)
        self.fc2 = nn.Linear(64, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.max_pool2d(F.relu(self.conv1(x)), 2)   # 28 -> 14
        x = F.max_pool2d(F.relu(self.conv2(x)), 2)   # 14 -> 7
        x = x.flatten(1)
        return self.fc2(F.relu(self.fc1(x)))


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


def get_flat_params(model: nn.Module) -> np.ndarray:
    """Flatten all parameters into one float32 vector."""
    with torch.no_grad():
        return torch.cat([p.detach().flatten() for p in model.parameters()]).numpy().copy()


def set_flat_params(model: nn.Module, flat: np.ndarray) -> None:
    """Inverse of :func:`get_flat_params`."""
    tensor = torch.from_numpy(np.asarray(flat, dtype=np.float32))
    offset = 0
    with torch.no_grad():
        for p in model.parameters():
            n = p.numel()
            p.copy_(tensor[offset : offset + n].view_as(p))
            offset += n
    if offset != tensor.numel():
        raise ValueError(f"parameter vector length {tensor.numel()} != model size {offset}")


@dataclass(frozen=True)
class TrainConfig:
    """Local training hyperparameters. Small on purpose -- see module docstring."""

    epochs: int = 1
    batch_size: int = 64
    lr: float = 0.05
    momentum: float = 0.9
    max_batches: int | None = None  # cap work per round for runtime control


def _batches(
    x: np.ndarray, y: np.ndarray, batch_size: int, rng: np.random.Generator
) -> Iterator[Tuple[torch.Tensor, torch.Tensor]]:
    order = rng.permutation(len(x))
    for start in range(0, len(order), batch_size):
        idx = order[start : start + batch_size]
        yield torch.from_numpy(x[idx]), torch.from_numpy(y[idx])


def local_train(
    global_params: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    config: TrainConfig,
    seed: int,
    n_classes: int = 10,
) -> np.ndarray:
    """Train locally from ``global_params`` and return the **update** (delta).

    Returning the delta rather than the new weights is what makes the update
    directly comparable across clients: norms and cosines are meaningful on deltas,
    and FedAvg is a weighted mean of them.
    """
    torch.manual_seed(seed)
    model = SmallCNN(n_classes)
    set_flat_params(model, global_params)
    model.train()

    optimiser = torch.optim.SGD(model.parameters(), lr=config.lr, momentum=config.momentum)
    loss_fn = nn.CrossEntropyLoss()
    rng = np.random.default_rng(seed)

    for _epoch in range(config.epochs):
        for i, (xb, yb) in enumerate(_batches(x, y, config.batch_size, rng)):
            if config.max_batches is not None and i >= config.max_batches:
                break
            optimiser.zero_grad()
            loss_fn(model(xb), yb).backward()
            optimiser.step()

    return get_flat_params(model) - global_params


@torch.no_grad()
def evaluate(
    params: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    n_classes: int = 10,
    batch_size: int = 512,
) -> Dict[str, float]:
    """Accuracy and loss for a parameter vector, plus per-class accuracy.

    Per-class accuracy is reported because a targeted attack can leave overall
    accuracy nearly unchanged while destroying one class -- a headline number alone
    would hide that.
    """
    model = SmallCNN(n_classes)
    set_flat_params(model, params)
    model.eval()

    loss_fn = nn.CrossEntropyLoss(reduction="sum")
    total_loss = 0.0
    correct = 0
    per_class_correct = np.zeros(n_classes, dtype=np.int64)
    per_class_total = np.zeros(n_classes, dtype=np.int64)

    for start in range(0, len(x), batch_size):
        xb = torch.from_numpy(x[start : start + batch_size])
        yb = torch.from_numpy(y[start : start + batch_size])
        logits = model(xb)
        total_loss += float(loss_fn(logits, yb))
        pred = logits.argmax(1)
        correct += int((pred == yb).sum())
        for cls in range(n_classes):
            mask = yb == cls
            per_class_total[cls] += int(mask.sum())
            per_class_correct[cls] += int((pred[mask] == cls).sum())

    n = len(x)
    per_class = np.divide(
        per_class_correct, np.maximum(per_class_total, 1), dtype=np.float64
    )
    return {
        "accuracy": correct / n,
        "loss": total_loss / n,
        "min_class_accuracy": float(per_class.min()),
        "per_class_accuracy": per_class.tolist(),
    }


def fedavg(updates: Sequence[np.ndarray], weights: Sequence[float] | None = None) -> np.ndarray:
    """Weighted mean of client updates -- plain FedAvg, no robustness.

    Robustness in BC-FL-SRV comes from *admission* (which updates are included),
    not from the aggregation rule. Keeping FedAvg unmodified means any measured
    difference is attributable to the admission decision.
    """
    if not updates:
        raise ValueError("no updates to aggregate")
    stacked = np.stack(updates)
    if weights is None:
        return stacked.mean(axis=0)
    w = np.asarray(weights, dtype=np.float64)
    if len(w) != len(updates):
        raise ValueError(f"got {len(w)} weights for {len(updates)} updates")
    if w.sum() <= 0:
        raise ValueError("weights must sum to a positive value")
    return (stacked * (w / w.sum())[:, None]).sum(axis=0).astype(np.float32)
