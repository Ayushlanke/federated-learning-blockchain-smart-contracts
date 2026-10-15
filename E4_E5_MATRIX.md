# E-4 / E-5 Experiment Matrix

**Written before implementation, deliberately.** Everything built for E-4/E-5 must be justified by a row here. If a component appears in no row, it does not get built.

**The question these experiments answer:** does the mechanism provide useful security in an actual federated-learning setting, or does it merely provide an auditable record of whatever admission rule it is given?

Status tags: `LIT` literature · `HYP` hypothesis · `IMPL` implemented · `RESULT` measured.

---

## 1. The distinction these experiments must separate

E-1/E-2/E-3 established properties of the **record**: verification is cheap, tampering is detectable, forgery is quantifiably hard. None of them touched the **rule**.

E-4/E-5 exist to separate two things that are easy to conflate:

| | What it means | Where it comes from |
|---|---|---|
| **Detection power** | Does the admission rule actually identify malicious updates? | the **rule**, and the evidence it can see |
| **Accountability** | Can anyone verify the rule was applied as declared? | the **mechanism** (committee + transcript) |

**Predicted result (`HYP`), stated before running:** S1 and S2 below will produce **identical ML outcomes**. The mechanism does not change *what* is admitted — only whether the decision can be verified. If that prediction holds, it is not a disappointing result: it is the precise statement of what the contribution is and is not, and it is what makes the overhead numbers meaningful.

---

## 2. Systems compared

| ID | System | Purpose |
|---|---|---|
| **S0** | Plain FedAvg. No admission rule, no verification. | What ordinary FL does under attack. The floor. |
| **S1** | Admission rule applied by a **trusted** server. No committee, no transcript. | Isolates the rule's ML value from the mechanism. |
| **S2** | Full BC-FL-SRV: same rule, applied by committee, attested, recorded. | The complete system. |

**S1 vs S2 is the key comparison.** Equal accuracy and equal TPR/FPR, differing only in overhead, is the honest demonstration that the mechanism buys *verifiability*, not *detection*.

---

## 3. Attacks

| ID | Attack | Definition | Expected vs rule |
|---|---|---|---|
| **A0** | none | honest clients only | baseline |
| **A1** | sign-flip | malicious client submits `−λ·update`, λ=1 | large norm and negative cosine → **should be caught** |
| **A2** | label-flip | client trains on data with labels permuted (`y → 9−y`) | update is *legitimate-looking* in parameter space; norm is normal → **hard for norm rules** |
| **A3** | scaled / model-replacement | update multiplied by a large factor (×10) | very large norm → **should be caught trivially** |
| **A4** | **slow-drift** | the falsification test — see §4 | **predicted to evade** |

### 3.1 A4 — slow-drift attacker, defined precisely

Inspired by "A Little Is Enough" (Baruch et al., NeurIPS 2019) `LIT`. The attacker:

1. **Knows the admission rule and its threshold** (worst case for us; assumption stated).
2. Computes its malicious direction `d` (label-flip gradient direction).
3. Scales it so the resulting update sits at `β ×` the rule's rejection threshold, with **β < 1** — i.e. deliberately *inside* the admissible region.
4. Submits every round. Damage accumulates across rounds even though no single round is anomalous.

**Independent variable:** β ∈ {0.25, 0.5, 0.75, 0.9, 1.1, 1.5}. β>1 should be caught; β<1 should not.

**Falsification:** if the attacker at β<1 achieves meaningful damage while being admitted at a rate indistinguishable from honest clients, **C5 is false** and the honest conclusion is that verifiable admission is worth little unless the rule is strong. **This attacker will not be weakened to avoid that outcome.**

---

## 4. Evidence disclosure ladder (`D-006`) — E-4's independent variable

| Level | Committee sees | Rule it can apply |
|---|---|---|
| **E0** | commitment only | none — admit all (floor) |
| **E1** | L2 norm | norm bound |
| **E2** | norm + cosine to previous global | norm bound + direction agreement |
| **E3** | random-projection sketch (d′=64) | distance-to-median in projected space |
| **E4** | full plaintext update | distance-to-median in full space (ceiling) |

---

## 5. THE MATRIX

### E-4 — does more disclosure buy more detection?

| Run | Systems | Disclosure | Attacks | Malicious frac | Seeds | Demonstrates |
|---|---|---|---|---|---|---|
| **E4.1** | S1 | E0–E4 | A1, A2, A3 | 0.2 | 5 | TPR/FPR per disclosure level → tests **C4** |
| **E4.2** | S1 | E0–E4 | A0 | 0 | 5 | **FPR under non-IID with no attack** — the usability floor |
| **E4.3** | S0, S1, S2 | E2 | A1, A2, A3 | 0.2 | 5 | end-to-end accuracy; **S1≡S2 check** |
| **E4.4** | S2 | E0–E4 | A2 | 0.2 | 3 | overhead vs disclosure level (transcript bytes, evidence bytes, runtime) |

**E4.2 matters more than it looks.** `LIT` Under non-IID data honest clients legitimately look like outliers. A rule with high TPR *and* high FPR is unusable — it silently excludes honest participants, which is exactly the harm AG1 exists to make visible.

### E-5 — does the slow-drift attacker defeat the rule?

| Run | Systems | Disclosure | β sweep | Malicious frac | Seeds | Demonstrates |
|---|---|---|---|---|---|---|
| **E5.1** | S1 | E2 | 0.25–1.5 | 0.2 | 5 | admitted-rate vs β → **the falsification curve** |
| **E5.2** | S0, S1 | E2 | 0.5, 0.9 | 0.1, 0.2, 0.3 | 5 | accuracy damage vs malicious fraction |
| **E5.3** | S1 | E2, E3, E4 | 0.9 | 0.2 | 3 | can *any* disclosure level catch it? |
| **E5.4** | S1 | E2 | 0.9 | 0.2 | 5 | damage accumulation over rounds (time series) |

### Iteration, only if E-5 shows the rule is the weak point

| Run | Purpose |
|---|---|
| **E5.5** | A **cross-round** rule (per-client historical consistency), evaluated on the same A4 attacker. Labelled clearly as a **separate iteration**; E5.1–E5.4 results stay exactly as measured. |

`LIT` Prior art here is FedGT / FLDetector / ClusterGuard. Framing F1 was killed as not novel, so **E5.5 is an engineering response to our own finding, not a novelty claim.**

---

## 6. Metrics

| Metric | Definition |
|---|---|
| TPR | fraction of malicious submissions rejected |
| FPR | fraction of honest submissions rejected |
| clean accuracy | test accuracy under A0 |
| accuracy under attack | test accuracy with attackers present |
| accuracy damage | clean − attacked, same seed |
| malicious influence | fraction of *admitted* updates that were malicious |
| transcript bytes/round, evidence bytes/client | storage and communication overhead |
| wall-clock/round | runtime overhead of the mechanism |

**Reporting:** every configuration runs over multiple fixed seeds; results are mean ± std. **No single-run numbers.**

---

## 7. Setup — sized for 12 CPU cores

| Parameter | Value | Why |
|---|---|---|
| Dataset | Fashion-MNIST | standard FL benchmark, CPU-tractable, not accuracy-saturated |
| Partition | Dirichlet(α=0.5) non-IID | standard convention; α swept only if time allows |
| Clients | 30 total, 10 sampled/round | enough for meaningful sortition and malicious fractions |
| Rounds | 30 | enough for slow-drift damage to accumulate |
| Model | small CNN, target < 100k params | seconds per round on CPU |
| Local training | 1 epoch, batch 64 | keeps a run to ~1–2 minutes |
| Committee / threshold | 9 / 6 | matches E-2 and E-3 |
| Seeds | 5 (sweeps: 3) | mean ± std, never one lucky run |

**Runtime budget:** the full matrix must complete in well under an hour. If it does not, **round count is reduced and the reduction is reported** — the attacker is never weakened (`D-005` cut rule).

---

## 8. What gets built — and what explicitly does not

| Component | Required by | Build? |
|---|---|---|
| Fashion-MNIST IDX loader, checksummed | all | **yes** |
| Dirichlet non-IID partitioner | all | **yes** |
| Small CNN + local training | all | **yes** |
| FedAvg aggregation | S0, S1, S2 | **yes** |
| Evidence encoders E0–E4 | E4.1, E4.4, E5.3 | **yes** |
| Admission rules per level | E4.1, E5.1 | **yes** |
| Attacks A1–A4 | all | **yes** |
| Experiment runner + metrics | all | **yes** |
| Simplified additive masking | premise of the whole design | **yes, minimal** — see §9 |
| Cross-round rule | E5.5 only, **conditional** | only if E-5 shows the rule is the weak point |
| Full Bonawitz SecAgg with dropout recovery | *nothing* | **no** |
| ZK proofs, real blockchain, staking, network layer | *nothing* | **no** (already cut in `EVALUATION_PLAN.md`) |
| α sweep, CIFAR-10, larger models | *nothing essential* | **no** unless time remains |

---

## 9. Terminology discipline — binding on all output

**What we implement is "simplified additive masking (no dropout recovery)", never "secure aggregation" unqualified.** `D-010` already requires this. Specifically:

- ✅ *"the aggregator observes only masked updates and their sum"* — this is what we implement and test.
- ❌ *"we implemented secure aggregation"* — we did not. No key agreement, no Shamir sharing, no dropout recovery, no malicious-server hardening.

**Masking does not affect any E-4/E-5 metric.** It changes what the *aggregator* sees; the rule operates on what the *committee* sees (the evidence ladder). It is built so the premise of the design is a demonstrated property rather than an assumption, and it is tested for exactly that: masks cancel in the sum, and no individual update is recoverable from what the aggregator holds.

---

## 10. Limitations to state up front — not after the fact

1. **Fashion-MNIST does not prove real-world FL security.** It is a controlled environment for comparing rules and attacks under identical conditions. Nothing here transfers to production FL without re-evaluation.
2. **30 clients is cross-silo scale, not cross-device.** `LIT` Shejwalkar et al. (S&P 2022) argue high malicious fractions are unrealistic in production; 0.1–0.3 is swept with the low end foregrounded, and even 0.1 is generous.
3. **The attacker is given full knowledge of the rule and threshold.** Conservative for us, and the right assumption for a security evaluation.
4. **Single model architecture, single dataset, single α.** No claim of generality across tasks.
5. **Simulation in one process.** No network adversary, no timing attacks, no client churn beyond sampling.
6. **The rule set is deliberately simple.** We are not proposing a state-of-the-art robust aggregation rule; F2 was killed as saturated. The rules exist to make the disclosure ladder measurable.

---

## 11. Pre-registered predictions

Recorded now so the analysis cannot drift toward whatever the data happens to show.

| # | Prediction | Confidence |
|---|---|---|
| P1 | S1 ≡ S2 on all ML metrics; they differ only in overhead | high |
| P2 | A3 (scaled) caught at E1+; A1 (sign-flip) caught at E2+ | high |
| P3 | A2 (label-flip) poorly caught at E1, better at E3/E4 | medium |
| P4 | **A4 at β<1 evades every disclosure level** — C5 false | **high** |
| P5 | FPR rises with disclosure level under non-IID (stricter rules reject honest outliers) | medium |
| P6 | Overhead is dominated by E3/E4 evidence size, not by the transcript | medium |

**If P4 holds, that is the project's headline limitation and will be reported as such.**
