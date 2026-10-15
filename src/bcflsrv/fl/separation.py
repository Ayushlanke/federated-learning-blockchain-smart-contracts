"""Separation-aware thresholding primitives for the G3 admission rule.

Kept in its own module so that G1 (:mod:`bcflsrv.fl.evidence`) and G2
(:mod:`bcflsrv.fl.reputation`) remain byte-for-byte unchanged and their published
results stay reproducible.

Why a separate primitive is needed
----------------------------------
G2 converts a per-client reputation into a decision with ``median(R) - k*MAD(R)``.
That is a **dispersion** test: it asks "is this point far from the centre relative to
the population spread?", which implicitly models the population as *unimodal with
tail contamination*.

Under attack the reputation population is not unimodal -- it is **bimodal**: an
honest cluster and a malicious cluster. For a bimodal population the discriminative
information lives in the **gap between the modes**, and that is not the same quantity
as distance-from-centre. A population can have perfectly separated modes (rank AUC
1.000) while *both* modes sit inside ``median +/- 3*MAD``, whenever the within-cluster
spread -- which non-IID heterogeneity makes large -- is comparable to the
between-cluster gap. That is precisely the regime measured in ``G2_FINDINGS.md`` s3.

Otsu's method is the standard answer: choose the split that maximises between-class
variance. It is closed-form, deterministic, parameter-free for the split itself, and
O(n log n) -- so an auditor can recompute the exact same threshold from the recorded
transcript, which AG1 requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

__all__ = ["OtsuSplit", "otsu_split"]


@dataclass(frozen=True)
class OtsuSplit:
    """The best two-class split of a 1-D sample.

    Attributes:
        threshold: values strictly below this belong to the low class.
        eta: Otsu's separability criterion, ``between-class variance / total
            variance``, in [0, 1]. 1.0 means two perfectly tight, distant clusters;
            values near 0 mean the sample is effectively unimodal. **This is the
            statistic the G3 gate tests** -- it is what distinguishes "there is a
            malicious cluster" from "this is just an honest population".
        gap: the width of the EMPTY region between the two classes, in units of the
            sample standard deviation. Otsu's ``eta`` alone is a weak gate -- a plain
            uniform ramp with no cluster structure at all scores eta = 0.76 -- because
            eta rewards any split of a spread-out sample. ``gap`` instead measures
            whether the split falls in a region the data actually vacates, which is
            what "there are two clusters" means.
        low_count: number of sample points in the low class.
        low_mean: mean of the low class.
        high_mean: mean of the high class.
    """

    threshold: float
    eta: float
    gap: float
    low_count: int
    low_mean: float
    high_mean: float

    @property
    def low_fraction(self) -> float:
        total = self.low_count + 1e-12
        return self.low_count / total if total else 0.0


def otsu_split(values: Sequence[float]) -> OtsuSplit | None:
    """Exact 1-D Otsu threshold.

    Exhaustive over the ``n-1`` split points rather than histogram-binned: the samples
    here are tiny (tens of clients), binning would add an arbitrary bin-count
    parameter, and exactness makes the result trivially reproducible by an auditor.

    Returns:
        The maximising split, or ``None`` if there are fewer than two distinct values
        (no split is meaningful, and reporting one would be an invitation to reject
        an arbitrary half of an honest population).
    """
    sample = np.asarray(sorted(float(v) for v in values), dtype=np.float64)
    n = sample.size
    if n < 2 or float(np.ptp(sample)) <= 1e-12:
        return None

    total_variance = float(np.var(sample))
    if total_variance <= 1e-18:
        return None

    prefix = np.cumsum(sample)
    total = float(prefix[-1])
    best_between, best_k = -1.0, 1
    for k in range(1, n):
        w0 = k / n
        mean0 = prefix[k - 1] / k
        mean1 = (total - prefix[k - 1]) / (n - k)
        between = w0 * (1.0 - w0) * (mean1 - mean0) ** 2
        if between > best_between:
            best_between, best_k = between, k

    low = sample[:best_k]
    high = sample[best_k:]
    # Threshold sits midway between the clusters so it is stable to a single point
    # moving, and so it is well defined for clients not in the calibrating sample.
    threshold = float((low[-1] + high[0]) / 2.0)
    spread = float(np.std(sample))
    return OtsuSplit(
        threshold=threshold,
        eta=float(best_between / total_variance),
        gap=float((high[0] - low[-1]) / spread) if spread > 1e-12 else 0.0,
        low_count=int(best_k),
        low_mean=float(low.mean()),
        high_mean=float(high.mean()),
    )
