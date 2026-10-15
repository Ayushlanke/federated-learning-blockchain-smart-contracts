# G2 — Second-Generation Admission Rule: Design and Pre-Registration

**Written BEFORE the confirmatory experiment is run.** Hypotheses, thresholds, attacks and success criteria are fixed here so they cannot be adjusted after seeing results.

**The original E-4/E-5 results stand unchanged** and remain the reported result for the first-generation rule (G1). G2 is a clearly separated second-generation ablation, not a replacement.

Status tags: `LIT` literature · `HYP` hypothesis · `IMPL` implemented · `RESULT` measured · `DIAG` design diagnostic (single seed, exploratory).

---

## 1. The question

> Is the E-5 negative result a limitation of **the specific rule we implemented**, or of **committee-backed verifiable admission** as an approach?

If the former, a principled rule should recover detection *without* changing the mechanism — same bounded disclosure, same committee attestation, same auditor. If the latter, no rule will help and the negative result is fundamental.

---

## 2. Diagnosis: why G1 failed

G1 (norm bound + cosine-to-previous-global, or distance-to-median) failed against slow drift. Two distinct causes, established by diagnostic:

### 2.1 L2 distance-to-median rewards the evasion

The attacker shrinks its update to duck the norm bound. **A shorter vector is also *closer* to the coordinate-wise median in L2.** The rule therefore pays the attacker twice for the same move. Magnitude and direction are conflated in a single statistic.

Supporting evidence already in the E-4 data: label-flip at natural magnitude is detected at **0.87–0.94**. The *same malicious direction*, merely rescaled below the threshold, drops to **0.15–0.33**. The direction was always discriminative; the statistic discarded it.

### 2.2 …but normalisation alone does not fix it `DIAG`

The obvious fix — normalise to the unit sphere, then compare directions — was tested first and **largely refuted**:

| client | norm | L2 dist-to-median | median pairwise cosine |
|---|---|---|---|
| **malicious** | 1.661 | 1.643 | **−0.044** |
| **malicious** | 1.661 | 1.758 | **−0.113** |
| honest (range over 8) | 0.97–1.55 | 0.89–1.64 | **−0.085 … 0.156** |

The malicious scores sit *inside* the honest range. At α=0.5 with 12 local batches, honest updates are so heterogeneous that pairwise cosines hover near zero **even among honest clients** — there is barely a consensus direction to deviate from. This is also why full-plaintext E4 reached only 0.33: it is not a disclosure problem, it is a **signal-to-noise problem**.

### 2.3 The real diagnosis

The per-round directional signal is **weak but not absent, and it is unbiased**. Malicious directions are *systematically* anti-correlated with honest consensus; the deviation is simply smaller than the round-to-round noise of honest non-IID updates.

The textbook response to an unbiased signal buried in noise is **not a cleverer single-round statistic — it is accumulation.**

---

## 3. Diagnostic evidence for accumulation `DIAG`

Single seed, 20 rounds, 30 clients, 20% malicious, slow drift at β=0.9, averaging the per-round direction score per client:

| Rounds averaged | Malicious mean | Honest mean | Separable? | AUC |
|---|---|---|---|---|
| 1 | 0.037 | 0.257 | overlapping | 0.833 |
| **3** | −0.047 | 0.256 | **clean** | **1.000** |
| 5 | −0.093 | 0.226 | clean | 1.000 |
| 20 | −0.108 | 0.204 | clean | 1.000 |

After 20 rounds: malicious ∈ [−0.158, −0.077], honest ∈ [0.063, 0.300] — **complete separation with a wide margin.**

**This is one seed and is exploratory.** It establishes that the mechanism is real; it does not establish the result. The confirmatory experiment is specified in §7.

---

## 4. The G2 rule

Operates on the **same E3 evidence** as G1 — a 64-dim random-projection sketch plus the L2 norm. **No additional per-update disclosure.**

Per round *t*, over the participating clients:

1. **Magnitude test** (unchanged from G1): reject if `‖uᵢ‖ > 1.5 × median(‖u‖)`.
   Catches scaling and model-replacement.

2. **Per-round direction score**: normalise each sketch to unit norm, compute all pairwise cosines, and set
   `sᵢ(t) = median_{j≠i} cos(ûᵢ, ûⱼ)`.
   *Median* of pairwise similarities, not a distance to a centre: a centre can be dragged by a coalition, whereas the median pairwise score stays honest while malicious clients are a minority.
   Normalisation removes the magnitude channel entirely, so **shrinking gains the attacker nothing.**
   Johnson–Lindenstrauss preserves inner products, so this is computable from the sketch.

3. **Reputation**: `Rᵢ(t) = mean of sᵢ over every round i has participated in`, carried in the transcript.

4. **Admission**: after a warm-up of `W = 3` participations, reject if
   `Rᵢ(t) < median(R) − 3·MAD(R)` over current participants.
   Before warm-up, the magnitude test alone applies.

### 4.1 Why the ledger becomes load-bearing for *detection*

Committees **rotate and are individually stateless** — the round-*t* committee never saw round *t−1*. Cross-round accumulation therefore needs shared, tamper-evident state, and the append-only transcript is exactly that.

Consequently the reputation is **itself auditable**: an external auditor recomputes every `Rᵢ` from recorded per-round scores and re-checks the admission decision. **AG1 extends from "the rule was applied" to "the reputation was accumulated correctly."**

This is the first point in the project where the accountability mechanism *enables* the detection mechanism rather than merely recording it.

### 4.2 The privacy price — stated, not hidden

G1 recorded only evidence **digests**. G2 records the per-round **score** (one float per client per round) in the transcript, so rotating committees can continue the accumulation and auditors can verify it.

**This is strictly more disclosure than G1, and it is disclosure to the *public*, not just to the committee.** A public observer learns a per-client behavioural time series. That is a real cost, it is the price of verifiable cross-round detection, and it is reported as a limitation rather than elided.

### 4.3 Cold start is an attack surface

A client with fewer than `W` participations is judged on magnitude alone. An attacker could therefore rejoin under a fresh identity every `W` rounds to reset its reputation. This is the **Sybil problem**, already declared out of scope (`LIT` the SoK states AG1 provides no Sybil resistance without external trust anchors). G2 does not fix it and does not claim to.

---

## 5. Novelty position — settled by a prior-art check, before running

A four-front prior-art check was run **before** the confirmatory experiment. Its verdict, quoted:

> **"KNOWN-IN-PARTS, leaning KNOWN. Every one of G2's four components is established prior art, and three of the four are established in the specific form G2 uses."**

Component by component `LIT`:

| G2 component | Status | Closest prior art |
|---|---|---|
| Norm bound at a multiple of the round **median** norm | **KNOWN** — same statistic | FLAME (USENIX Sec 2022) clips at the median of L2 norms; SignGuard uses a median-based norm range |
| Normalise to the unit sphere before comparing directions | **KNOWN** | FLTrust (NDSS 2021) normalises every update to the server update's magnitude; cosine is scale-invariant by construction |
| Pairwise cosine among clients | **KNOWN — this is literally FoolsGold** | FoolsGold (RAID 2020), CONTRA (ESORICS 2021), FLAME |
| Score = **median** of a client's pairwise cosines, cut at median − k·MAD | **UNCOMMON** | FoolsGold uses **max**, not median. AFA uses median+MAD but of cosines *to the global model*, not pairwise. |
| Sketch before the robustness test | **KNOWN** | SketchGuard (2025, Count Sketch), DnC (NDSS 2021, random dimension subsampling), H+ (2025) |
| Evaluation vs an attacker that **shrinks** its update | **PARTLY KNOWN** | MESAS (CCS 2023) is built around constrained adaptive attackers; FoolsGold explicitly declines to evaluate this |

**Conclusion: G2 is NOT a novel defence, and is not claimed as one.** It is a competent
application of established robust statistics, chosen because a diagnosis — not a hunch —
said the magnitude channel was the flaw. The prior-art check's own closing advice is
adopted verbatim: *"this is a small statistical variation, not a new idea — do not sell
it as more."*

**What remains distinctive is the combination, not the detector:** the reputation is
accumulated **through an append-only transcript**, so that *rotating, individually
stateless* committees can perform cross-round detection at all, and so that the
resulting reputation is **externally verifiable** — an auditor recomputes it from the
record rather than trusting the server. Every system above assumes a server that holds
the history and is trusted to use it honestly. **That assumption is exactly the one this
project exists to remove.**

The project's claim is therefore unchanged: **verifiable admission accountability under
bounded disclosure.** G2 is the demonstration that such a mechanism can carry a rule
strong enough to be worth verifying — not a claim to have invented the rule.

## 6. Pre-registered hypotheses

Fixed before the confirmatory experiment.

| ID | Hypothesis | Confidence |
|---|---|---|
| **G2-P1** | G2 achieves **TPR ≥ 0.80 at FPR ≤ 0.10** against slow drift (β=0.9, 20% malicious), versus G1's 0.15. | high |
| **G2-P2** | G2 substantially improves **sign-flip** detection (G1: 0.27 → G2: > 0.70), because sign-flip reverses direction while preserving norm — exactly what a normalised directional test targets. | high |
| **G2-P3** | The advantage **requires the warm-up**. With W=1 (no accumulation) G2 performs no better than G1. | high |
| **G2-P4** | **S3 (full mechanism + G2) ≡ S1b (G2, trusted server)** on all ML metrics, differing only in overhead — the mechanism still buys verifiability, not detection. | high |
| **G2-P5** | The **adaptive attacker A7** (§7.2) can evade G2, but only by reducing its malicious component, and damage falls roughly in proportion — a genuine trade-off curve, not free evasion. | medium |
| **G2-P6** | G2's FPR under honest non-IID rises relative to G1 but stays **≤ 0.12**. | medium |

---

## 7. Confirmatory experiment

### 7.1 Systems (the four the comparison requires)

| ID | System |
|---|---|
| **S0** | no admission rule (plain FedAvg) |
| **S1** | **G1**, original rule, trusted server |
| **S1b** | **G2**, improved rule, trusted server |
| **S3** | **G2 + full committee-backed verifiable mechanism** |

### 7.2 Attacks

| ID | Attack | Status |
|---|---|---|
| A0 | none (honest non-IID) | existing |
| A1 | sign-flip | existing |
| A2 | label-flip | existing |
| A3 | scaled / model replacement | existing |
| **A5** | **Gaussian noise** at median norm — random direction, valid magnitude | **new** |
| **A6** | **targeted single-class poisoning** (class 0 → 6), measured by min-class accuracy | **new** |
| A4 | slow drift, β sweep | existing |
| **A7** | **adaptive attacker vs G2** — mixes malicious direction with the honest consensus direction, `u = normalise(γ·d_mal + (1−γ)·d_consensus) × β·threshold`, with **oracle access to the consensus direction**. γ sweep. | **new** |

**A7 is mandatory.** Testing G2 only against an attacker designed for G1 would be evaluating the new rule against a stale adversary. A7 is given oracle knowledge of both the rule and the consensus direction — the worst case for us.

### 7.3 Conditions

Malicious fractions **0.1 / 0.2 / 0.3**; β sweep for A4; γ sweep for A7; warm-up ablation W ∈ {1, 2, 3, 5}; **3 seeds for sweeps, 5 for the headline curves**. Mean ± std throughout; no single-run numbers.

### 7.4 Setup — unchanged from E-4/E-5

Fashion-MNIST, Dirichlet α=0.5, 30 clients, 10/round, 25 rounds, same 52k-parameter CNN, same thresholds calibrated on the attack-free condition. **Nothing about the environment is re-tuned for G2.**

---

## 8. Success criteria — fixed now

| Verdict | Criteria |
|---|---|
| **A — strong positive** | G2 reaches TPR ≥ 0.80 at FPR ≤ 0.10 on slow drift **and** sign-flip **and** label-flip, **and** the adaptive attacker A7 must give up ≥ 50% of its damage to evade. |
| **B — qualified** | G2 substantially improves some attacks but not others, **or** requires an impractical warm-up, **or** A7 evades cheaply, **or** FPR exceeds 0.12. |
| **C — negative** | G2 does not meaningfully improve on G1 (< 0.2 absolute TPR gain on slow drift). |

**If the outcome is B or C, that is what gets reported.** The E-5 result stands either way, and no threshold, attacker or seed will be adjusted after the fact to move the verdict.

---

## 9. What is deliberately NOT being built

Unchanged from `EVALUATION_PLAN.md` and `E4_E5_MATRIX.md`: no blockchain, no ZK, no networking, no production SecAgg, no staking. G2 adds **one float per client per round** to the transcript and reuses the existing sketch. That is the entire cost.

---

## 10. AMENDMENT — recorded BEFORE the confirmatory run

The prior-art check (§5) surfaced a **published attack that breaks G2 as originally specified**. It is recorded here, before any confirmatory experiment, rather than discovered afterwards.

### 10.1 The vulnerability: null-space evasion (A8)

`LIT` SketchGuard (arXiv 2510.07922, 2025) observes that when the sketch is a **fixed, publicly known linear map**, an adversary can hide an arbitrarily large perturbation in `null(P)` — the projection annihilates it, so any rule computed from the sketch is *structurally* blind.

G2's projection seed was `SHA256("proj" ‖ run_seed ‖ round)` — entirely predictable. **G2 as first written was vulnerable.**

Demonstrated directly (N = 52,138, sketch dim 64):

| Quantity | Value |
|---|---|
| Perturbation injected | 90% of the honest update norm |
| Sketch difference `‖P·evil − P·honest‖` | **5.63 × 10⁻¹⁵** (numerically zero) |
| True full-space cosine to honest | 0.742 |

The sketch sees *nothing*. Keeping the total norm under the bound defeats the magnitude test too, so both of G2's tests are evaded simultaneously.

### 10.2 The fix: commit-then-sketch

The published remedy is to draw the projection seed **after** updates are committed. Our architecture supplies that primitive for free: the transcript already records submission commitments before the committee evaluates them. The seed becomes

`projection_seed = H("proj-cts" ‖ sorted(commitments of this round))`

so no attacker can compute `null(P)` in advance — the seed depends on every participant's commitment, including honest ones it does not control.

**This is a second, independent instance of the ledger doing real cryptographic work**, alongside carrying the reputation. It is not decoration in either case.

### 10.3 Measured effect `DIAG` (1 seed, 15 rounds)

| Projection seed | TPR vs A8 | FPR | malicious admitted |
|---|---|---|---|
| predictable | 0.25 | 0.09 | 0.75 |
| **commit-then-sketch** | **0.39** | **0.03** | **0.61** |

**Honest reading:** commit-then-sketch removes the *structural* blindness — the attacker can no longer guarantee invisibility — but the residual perturbation is only partially caught. It is a mitigation, not a cure, and is reported as such.

### 10.4 Additional pre-registered hypotheses

| ID | Hypothesis |
|---|---|
| **G2-P7** | With a predictable seed, A8 evades G2 almost completely (TPR ≤ 0.3). With commit-then-sketch, detection improves materially but does **not** reach the ≥ 0.8 bar. |
| **G2-P8** | A8 detection under commit-then-sketch is **worse** than G2's detection of sign-flip, because a null-space perturbation with a wrong projection guess is directionally random rather than opposed to consensus. |

### 10.5 A caution that applies to the whole design

`LIT` MESAS (ACM CCS 2023) argues that **any single- or few-metric rule is adaptively evadable**, and forces attackers into multi-objective optimisation by combining many metrics. G2 uses two tests. MESAS's thesis therefore predicts that a sufficiently determined adaptive attacker will find a corner of the space that satisfies both — which is exactly what attacks A7 and A8 probe. **We should not expect G2 to be adaptively unbreakable, and will not claim it is.**
