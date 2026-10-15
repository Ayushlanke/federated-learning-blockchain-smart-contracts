# G3 Pre-Registration — Separation-Aware Admission

**Status: written and committed BEFORE the confirmatory experiment ran.**
The commit that introduces this file contains no `results/summary/g3_runs.csv`. The
commit history is the evidence; check it.

---

## 0. What is frozen and stays frozen

| Artefact | Status |
|---|---|
| `results/E4_E5_FINDINGS.md` (G1) | **FROZEN.** Not edited, not re-run, not reinterpreted. |
| `results/G2_FINDINGS.md` (G2, VERDICT B) | **FROZEN.** Including the admission that the slow-drift criterion landed in C. |
| `G2_PREREGISTRATION.md` | **FROZEN**, scorecard and all three failures intact. |
| `src/bcflsrv/fl/evidence.py` (G1 rule) | **Untouched.** |
| `src/bcflsrv/fl/reputation.py` (G2 rule) | **Untouched.** Guarded by `tests/test_g3.py::test_g2_rule_is_unchanged_by_g3`. |

G3 is a **third-generation ablation**, not a replacement. Every table in this round of
work reports G1 and G2 beside G3.

### Evidence classes used throughout

| Tag | Meaning |
|---|---|
| `LIT` | Established in the literature. |
| `RESULT` | Measured by a completed experiment of ours. |
| `EXPLORATORY` | Measured on **development seeds 100–104**, used for design only, **never** reported as evidence for a hypothesis. |
| `PREREG` | A prediction fixed here, before the confirmatory run. |
| `INFERRED` | Our reasoning, not yet measured. |

---

## 1. The question this round exists to answer

`RESULT` G2 reached slow-drift TPR 0.43 against G1's 0.32, short of the 0.80 bar.
The user's question: **is that weakness caused by (a) the admission rule, (b) the
single-round setting, (c) the sketch/disclosure constraint, or (d) something deeper?**

Each is assigned a decisive experiment in §7. None is argued from the armchair.

---

## 2. Mechanism: why the cutoff, specifically, was the bottleneck

`RESULT` `G2_FINDINGS.md` §3 measured a contradiction: the reputation population
**separates** (rank AUC 1.000 after three rounds) while the pre-registered
`median(R) − 3·MAD(R)` cutoff **fails to fire**.

`INFERRED` The explanation is that these are different quantities.
`median − k·MAD` is a **dispersion** test: it models the population as *unimodal with
tail contamination* and asks how far a point sits from the centre. Under attack the
population is **bimodal** — an honest mode and a malicious mode. Rank separation and
distance-from-centre-in-MAD-units come apart precisely when the *within*-cluster
spread, which non-IID heterogeneity makes large, is comparable to the *between*-cluster
gap. A population can therefore separate perfectly and still have both modes sitting
inside `median ± 3·MAD`.

The correction is to threshold on the structure that is actually present: find the
**split between the modes** (Otsu's method — closed-form, deterministic, O(n log n)),
rather than a distance from a centre.

**Why Otsu and not HDBSCAN or k-means.** This is a systems argument, not an ML one.
The premise of the whole system is that a third party recomputes the admission
decision from the transcript. Iterative, initialisation-dependent clustering is
awkward to re-verify bit-exactly; a closed-form threshold is reproduced identically by
any auditor. AG1 verifiability drives the choice, not a claim of better detection.

---

## 3. Prior-art check — verdict **KNOWN**, novelty **NOT** claimed

Checked before designing, not after.

| Prior work | Overlap |
|---|---|
| Auror (ACSAC 2016) | k-means clustering on masked features to identify malicious clients. |
| FLAME (USENIX Sec 2022) | HDBSCAN clustering on cosine distances for dynamic filtering. |
| FLDetector-style defences (KDD 2022 and successors) | k-means with the **gap statistic** to choose cluster count for malicious-client detection. |
| Published FL work combining **Otsu's method** with adaptive thresholding | Directly overlaps the mechanism used here. |
| The same literature | Independently names the failure mode diagnosed in §2 — *static reputation thresholds failing to adapt to changing reputation distributions*. |

**Conclusion: G3 is a competent application of known robust statistics and is claimed
as nothing more.** The literature independently confirming our diagnosis is
*supporting evidence for the diagnosis* and simultaneously a *kill* on any novelty
claim about it. Both are recorded.

`LIT` A concurrent architecture paper — *Trustless Federated Learning at Edge-Scale*
(arXiv 2511.21118) — proposes committee nodes computing masked sums from admitted
contributors with auditors verifying that declared policies were applied consistently.
That is close to this project's architecture. It is, on inspection, an
architecture/position paper with **no experimental evaluation**. This narrows our
contribution honestly: the architecture is not ours alone; what we add is an
implementation with **measured** cost and **measured** detection, including a negative
result. That narrowing is recorded here rather than left for a reader to discover.

---

## 4. Calibration discipline

**Seed split, fixed here:**

- **Development seeds 100–104** — the exploratory diagnostic (`scripts/diag_g3.py`).
  Design decisions were made on these.
- **Confirmatory seeds 0–4** — the experiment in §7. **Not touched during design.**

`EXPLORATORY` The gate was calibrated on the **attack-free condition only**, against
the project's standing bar of **FPR ≤ 0.10** (in force since E-4 — not a bar invented
for G3). The finding was that the **gap gate is unnecessary**: with the minority bound
applied, attack-free FPR is 0.046 at *every* gap threshold tested including zero, and
every positive value strictly costs detection. `G3_GAP_MIN` is therefore **set to
zero, removing it as a tunable parameter** rather than leaving a knob at a flattering
setting.

> **G3 introduces no new calibrated constant.** The warm-up is G2's, unchanged and
> deliberately not re-tuned. The minority bound is not a new assumption either: it is
> the corruption bound the committee already assumes, since a 6-of-9 attestation
> threshold tolerates f < n/3.

**Correction recorded honestly:** the diagnostic was first written to calibrate against
a "gate fires on ≤5% of attack-free rounds" target. That was the wrong quantity — fire
rate is not the harm, false rejection is — and it produced a gate that made G3 *worse*
than G2 on development data. The target was changed to the project's existing FPR bar
**before** any confirmatory seed was run, and the superseded attempt is reported in the
findings rather than deleted.

---

## 5. What G3 changes — exactly one component

| Test | G2 | G3 |
|---|---|---|
| 1. Magnitude | `norm > median(norms) × 1.5` | **identical** |
| 2. Per-round direction | median pairwise cosine on unit-normalised sketches | **identical** |
| 3. Reputation → rejection | `reject if R < median(R) − 3·MAD(R)` | **Otsu split on the reputation population, rejecting the low class only while it is a minority (≤ 1/3)** |

Two further scope choices are **ablated separately** rather than bundled in:
**population scope** (locate the split over every client with enough participations,
not just this round's ten) and **accumulation** (cross-round running mean vs this
round's score alone).

---

## 6. The new attack: A9, camouflage

`PREREG` If a defence needs a **gap**, the attacker's counter is to **refuse to leave
one**. A9 gives each malicious client a *persistent* intensity spread over
`[0.2β, β]`, so the coalition's reputations form a continuum that interpolates into the
honest distribution and no bimodal structure exists to find.

Persistence is the essential design point: the reputation is a running mean, so
freshly-random per-round intensities would average back to a common value and the
cluster would simply re-form. Only a fixed per-client spread survives accumulation.

**A9 is designed to beat G3 and is expected to.** Its cost — mean intensity 0.6β
rather than β — is a real reduction in attack strength and is **reported as a measured
trade-off, not hidden**.

---

## 7. The confirmatory matrix

Five arms. `S1c` isolates G3's ML value; `S3` adds the full verifiable mechanism.

| Arm | System | Rule |
|---|---|---|
| S0 | plain FedAvg | none |
| S1 | trusted server | G1 |
| S1b | trusted server | G2 |
| **S1c** | trusted server | **G3** |
| **S3** | **committee + attestation + transcript** | **G3** |

| # | Experiment | Answers | Runs |
|---|---|---|---|
| X1 | Main: 5 arms × 7 attacks × 3 seeds, 20% malicious | rule comparison, FPR, mechanism cost | 105 |
| X2 | Slow-drift β sweep: **G1, G2 and G3 all re-run** × 6 β × 5 seeds | headline; also **reproduces** the frozen G1/G2 numbers | 90 |
| X3 | Disclosure: G3 at E3 vs **E4 plaintext** | **(c) is it the sketch?** | 10 |
| X4 | Accumulation: G3 with running mean vs single-round score | **(b) is it the single-round setting?** | 10 |
| X5 | Scope: population vs round-local split | does the ledger's cross-client view earn its place? | 10 |
| X6 | Gap gate: `gap_min` 0 vs 0.35, attack-free and slow-drift | re-tests §4 on held-out seeds | 20 |
| X7 | Adaptive A7 γ sweep vs G3 | **(d) deeper limit?** | 25 |
| X8 | Two-sided G3 vs A7, slow-drift, and attack-free | is the adaptive gap fixable *by the rule*? | 15 |
| X9 | **A9 camouflage** vs G1, G2, G3 | can our own defence be beaten? | 15 |
| X10 | Malicious fraction 0.1 / 0.3 | does the minority bound hold at its edge? | 12 |

**312 runs.** Fashion-MNIST, 30 clients, 10 per round, 25 rounds, Dirichlet α = 0.5,
disclosure E3 unless stated. Seeds 0–2 (main) / 0–4 (sweeps). Every attacker keeps
oracle knowledge of the threshold; **no attack is weakened**.

---

## 8. Hypotheses — fixed now

| ID | Prediction | Falsified if |
|---|---|---|
| **G3-P1** | Slow-drift TPR **≥ 0.60** (G2: 0.43) | TPR < 0.60 |
| **G3-P2** | Attack-free FPR **≤ 0.10** | FPR > 0.10 |
| **G3-P3** | Population scope beats round-local by **≥ 0.05** TPR | it does not |
| **G3-P4** | With the cutoff fixed, **accumulation now helps** — `accumulate=True` beats single-round by ≥ 0.05 | it does not. *G2-P3 refuted accumulation under the MAD cutoff; this is the proper re-test, and I do not know the answer.* |
| **G3-P5** | **Disclosure is not the bottleneck**: E4 plaintext within 0.05 TPR of E3 sketch | E4 exceeds E3 by > 0.05 |
| **G3-P6** | S3 ≡ S1c on ML metrics to machine precision | any nonzero difference |
| **G3-P7** | **A7 remains undetected** one-sided (TPR ≤ 0.10) **and its damage stays within the clean-run noise band** | either half fails |
| **G3-P8** | Two-sided G3 **catches A7 but at FPR > 0.15** — a fix that costs more than it is worth | it catches A7 cheaply, or fails to catch it at all |
| **G3-P9** | **A9 beats G3**: TPR at least 0.15 below G3's slow-drift TPR, at a measured cost in damage | A9 fails to degrade G3 |
| **G3-P10** | The gap gate is **unnecessary**: `gap_min = 0.35` detects strictly worse at no FPR benefit | the gate improves the FPR/TPR trade |

**Four of these predict failure or a limitation of our own design (P7, P8, P9, and the
"no benefit" half of P10).** A pre-registration that only predicts success is not one.

---

## 9. Success criteria — A / B / C, fixed now

The detection bar is **carried over unchanged from `G2_PREREGISTRATION.md`.** It is
not relaxed.

- **A — strong positive.** TPR **≥ 0.80** at FPR ≤ 0.10 on slow-drift **and** sign-flip
  **and** label-flip.
- **B — qualified.** Substantially improves some attacks but not others; **≥ 0.20**
  absolute TPR gain over G2 on slow drift, at FPR ≤ 0.10.
- **C — negative.** **< 0.20** absolute TPR gain over G2 on slow drift.

Reported **alongside**, not as a substitute, and pre-specified here:

- **Harm criterion.** Whether any attacker — A4, A7 or A9 — achieves accuracy damage
  beyond the clean-run noise band. This is stated separately because G2's A-criterion
  contained an A7 clause that the diagnostic has since shown to be unmeetable by any
  low-side cutoff; rather than quietly drop it or quietly soften it, the detection bar
  above is kept **exactly as it was** and the harm question is reported as its own
  measurement.

If the evidence supports **B**, the verdict stays **B**. Promotion to **A** requires
naming the satisfied criterion and the number that satisfies it.

---

## 10. Standing commitments

1. No threshold, attacker, seed or criterion changes after results are seen.
2. Regressions are reported in the same table as improvements.
3. `G3_GAP_MIN` stays at its calibrated value regardless of outcome.
4. If G3 fails, it is reported as a failure and G2's VERDICT B stands.
5. Fashion-MNIST is a controlled environment. Nothing here is evidence about
   production federated learning.
