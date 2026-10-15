"""Robust micro-benchmark timing.

Why this exists rather than a bare ``time.perf_counter()`` pair
---------------------------------------------------------------
The operations under test take microseconds. At that scale a single measurement is
dominated by noise: OS scheduling, cache state, CPU frequency scaling, and the timer's
own resolution. Three defences are applied:

* **Auto-calibrated batching.** The callable is run enough times per sample that the
  batch lasts well beyond timer resolution, so per-call cost is a division rather than
  a difference of two nearly-equal numbers.
* **Median over repeats, not mean.** Benchmark noise is one-sided -- interference only
  ever makes things *slower*. The median resists that; a mean would drift upward with
  every scheduler hiccup.
* **Warmup.** The first calls pay import, branch-prediction and cache costs that are
  not representative of steady state.

Reported alongside every measurement: the interquartile range and the minimum. If IQR
is large relative to the median, the number is unstable and should not be trusted --
that judgement belongs to the reader, so the data is always exposed rather than
silently smoothed away.

**This does not eliminate noise.** It reduces it and makes what remains visible.
"""

from __future__ import annotations

import gc
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable, List

__all__ = ["Measurement", "measure"]


@dataclass(frozen=True)
class Measurement:
    """Timing result for one operation, in seconds unless stated otherwise."""

    median_s: float
    min_s: float
    iqr_s: float
    repeats: int
    inner_loops: int
    samples_s: List[float] = field(repr=False, default_factory=list)

    @property
    def median_us(self) -> float:
        return self.median_s * 1e6

    @property
    def min_us(self) -> float:
        return self.min_s * 1e6

    @property
    def iqr_us(self) -> float:
        return self.iqr_s * 1e6

    @property
    def relative_iqr(self) -> float:
        """IQR as a fraction of the median. Above ~0.2 means treat with suspicion."""
        return self.iqr_s / self.median_s if self.median_s > 0 else 0.0

    @property
    def is_stable(self) -> bool:
        return self.relative_iqr < 0.20

    def as_dict(self) -> dict:
        return {
            "median_us": self.median_us,
            "min_us": self.min_us,
            "iqr_us": self.iqr_us,
            "relative_iqr": self.relative_iqr,
            "is_stable": self.is_stable,
            "repeats": self.repeats,
            "inner_loops": self.inner_loops,
        }


def _calibrate(fn: Callable[[], object], target_s: float, cap: int) -> int:
    """Smallest power-of-two loop count whose batch runs for at least ``target_s``."""
    loops = 1
    while loops < cap:
        start = time.perf_counter()
        for _ in range(loops):
            fn()
        elapsed = time.perf_counter() - start
        if elapsed >= target_s:
            return loops
        loops *= 2
    return cap


def measure(
    fn: Callable[[], object],
    *,
    repeats: int = 11,
    warmup: int = 3,
    target_batch_s: float = 0.01,
    max_inner_loops: int = 1_000_000,
    disable_gc: bool = True,
) -> Measurement:
    """Time ``fn`` and return a :class:`Measurement`.

    Args:
        fn: Zero-argument callable. Bind arguments with a closure or ``partial``;
            argument marshalling must not be inside the timed region.
        repeats: Independent samples. Odd values give an unambiguous median.
        warmup: Untimed calls before measuring.
        target_batch_s: Minimum duration of one batch, for timer resolution.
        max_inner_loops: Safety cap for very fast operations.
        disable_gc: Disable the cyclic collector during timing. A collection that
            happens to land inside a sample would be attributed to the operation.

    Raises:
        ValueError: if ``repeats`` is below 3 -- no dispersion could be estimated.
    """
    if repeats < 3:
        raise ValueError(f"repeats must be >= 3 to estimate dispersion, got {repeats}")

    for _ in range(warmup):
        fn()

    inner = _calibrate(fn, target_batch_s, max_inner_loops)

    gc_was_enabled = gc.isenabled()
    if disable_gc:
        gc.disable()
    try:
        samples: List[float] = []
        for _ in range(repeats):
            start = time.perf_counter()
            for _ in range(inner):
                fn()
            samples.append((time.perf_counter() - start) / inner)
    finally:
        if disable_gc and gc_was_enabled:
            gc.enable()

    ordered = sorted(samples)
    lo = statistics.median(ordered[: len(ordered) // 2])
    hi = statistics.median(ordered[(len(ordered) + 1) // 2 :])

    return Measurement(
        median_s=statistics.median(ordered),
        min_s=ordered[0],
        iqr_s=hi - lo,
        repeats=repeats,
        inner_loops=inner,
        samples_s=samples,
    )
