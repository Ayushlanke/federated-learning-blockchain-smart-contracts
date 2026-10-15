# EVALUATION_PLAN.md — BC-FL-SRV

**Purpose.** Decide *what we are trying to prove or disprove* before building the machinery to test it. Every component in `IMPLEMENTATION_PLAN.md` must be justified by an experiment here. **If a component appears in the plan but in no experiment, it should not be built.**

**Serves:** `RD-001` as narrowed by `D-010`.

**Status discipline used throughout:**
`LIT` = established by literature · `HYP` = our hypothesis · `IMPL` = implemented in this repo · `RESULT` = measured here.

---

## 1. The claim, decomposed into testable pieces

`RD-001` (narrowed): *a rotating committee co-signing admission decisions into an append-only Merkle transcript makes AG1 (correct admission) and AG3 (non-equivocation) verifiable by an external auditor under simplified secure aggregation, using only signatures and hashing, at cost independent of model size.*

Four independent things must hold. Each maps to experiments:

| # | Sub-claim | Status | Experiments | Fails if |
|---|---|---|---|---|
| **C1** | An auditor holding only the transcript can detect admission tampering | `HYP` | E-2 | any in-scope attack goes undetected |
| **C2** | Verification cost is independent of model size N | `HYP` (SoK predicts O(K), O(1) — `LIT`) | E-1 | cost grows with N |
| **C3** | Soundness degrades predictably and quantifiably with committee corruption | `HYP` | E-3 | empirical ≠ analytic, or safe sizes are impractical |
| **C4** | More disclosure to the committee buys more detection power | `HYP` | E-4 | no rung detects usefully, **or** E1 already equals E4 (ladder pointless) |

And one thing we expect to **fail**, kept deliberately:

| # | Sub-claim | Status | Experiment | Honest expectation |
|---|---|---|---|---|
| **C5** | Verifiable admission stops a slow-drift attacker | `HYP` — **we predict this is FALSE** | E-5 | **We expect the attacker to win.** Reporting that is the finding. |

---

## 2. Baselines

A result without a baseline is a number, not evidence. Every experiment compares against at least one.

| ID | Baseline | Purpose | Expected |
|---|---|---|---|
| **B0** | Plain FedAvg, no verification | what verification *costs* | fastest, zero accountability |
| **B1** | Signed log only, no Merkle tree | can signatures alone give AG3? | **No** — cannot prove append-only extension without O(n) re-download |
| **B2** | Aggregator self-attests admission (no committee) | can the aggregator vouch for itself? | **No** — trivially forgeable; this is the status quo the project attacks |
| **B3** | Plaintext admission (E4 rung, no privacy) | upper bound on detection power | best detection, zero privacy |

B1 and B2 are the two "why not just do the simple thing?" questions an interviewer will ask. They exist to answer them with data.

---

## 3. Ablations

Each removes one component and asks whether it earned its place.

| ID | Remove | Question | If it changes nothing |
|---|---|---|---|
| **A1** | Merkle tree (keep flat signed log) | does the tree buy anything over signatures? | drop the tree — the contribution shrinks honestly |
| **A2** | Committee (aggregator self-attests) | does distributing attestation matter? | the whole design is unnecessary |
| **A3** | Hash chaining (keep tree, drop `prev_root`) | is chaining redundant with consistency proofs? | simplify the entry format |
| **A4** | Evidence (E0 rung) | what is verifiable admission worth with nothing to verify? | establishes the floor |

**A3 is a genuine open question I do not know the answer to.** Chaining and consistency proofs overlap; the ablation decides whether both are needed. Committing to an answer before measuring would be dishonest.

---

## 4. Experiments

### E-1 — Verification cost scaling → tests **C2**

| Field | Value |
|---|---|
| **Question** | Does auditor verification cost depend on model size N, transcript size T, or admitted-client count K? |
| **Independent vars** | N ∈ {10³, 10⁴, 10⁵, 10⁶, 10⁷} · T ∈ {10², 10³, 10⁴, 10⁵} entries · K ∈ {5, 10, 20, 50} |
| **Dependent vars** | auditor verify time (µs), proof size (bytes), transcript bytes/round, peak memory |
| **Baselines** | B0 (no verification), B1 (signed log — must re-download O(T)) |
| **Confirms C2 if** | verify time flat in N; grows O(log T); grows O(K) for admission checks |
| **Falsifies C2 if** | verify time grows with N — the design would be no cheaper than ZK approaches |
| **Dataset needed** | **None** — synthetic update vectors (`D-008`) |
| **Runtime estimate** | minutes |
| **Artifact** | log-log plots: verify-time vs N, vs T, vs K; table of bytes/round |

*Early signal (`RESULT`, smoke test only): verification held at ~4.5 µs from 1 KB to 1 MB payloads. Not yet the full sweep.*

### E-2 — Tamper detection → tests **C1**

| Field | Value |
|---|---|
| **Question** | Does an auditor with only the transcript catch each attack AG1/AG3 claim to cover? |
| **Attacks** | selective drop of an honest client · forged admission set · entry reorder · entry deletion · payload edit · truncation vs a known root · replay of a prior round's submission · split-view (two divergent roots) |
| **Dependent vars** | detection rate per attack; **false-positive rate on honest runs** |
| **Baselines** | B1, B2 (both expected to miss most attacks) |
| **Confirms C1 if** | 100% detection on in-scope attacks, 0% false positives |
| **Falsifies C1 if** | any in-scope attack survives |
| **Out of scope, stated** | split-view is **undetectable with a single view** — that is E-6, not a failure of C1 |
| **Dataset needed** | None |
| **Artifact** | attack × {BC-FL-SRV, B1, B2} detection matrix |

### E-3 — Committee corruption → tests **C3**

| Field | Value |
|---|---|
| **Question** | How does AG1 soundness degrade as corrupted clients occupy committee seats? |
| **Independent vars** | committee size m ∈ {3,5,7,9,11,15} · threshold t ∈ {⌈m/2⌉, ⌈2m/3⌉} · corrupt fraction f ∈ {0.05 … 0.5} |
| **Dependent vars** | empirical P(coalition holds ≥ t seats) over many sortitions; **compared against the hypergeometric prediction** |
| **Confirms C3 if** | empirical matches analytic within sampling error, **and** practical (m, t) reach acceptable forge probability at realistic f |
| **Falsifies C3 if** | they diverge (implementation bug) or required m is impractical for 50 clients |
| **Realism anchor** | `LIT`: Shejwalkar et al. (S&P 2022) argue high malicious fractions are unrealistic — low f is foregrounded, high f reported for completeness |
| **Dataset needed** | None — pure sortition sampling |
| **Artifact** | forge-probability curves vs f for each m; empirical-vs-analytic overlay |

### E-4 — Disclosure ladder ablation → tests **C4**

| Field | Value |
|---|---|
| **Question** | How much detection power does each rung of disclosure (E0…E4) actually buy? |
| **Independent vars** | evidence level E0/E1/E2/E3/E4 · attack type (sign-flip, scaled, label-flip) · non-IID Dirichlet α |
| **Dependent vars** | TPR (malicious rejected), **FPR (honest non-IID clients wrongly rejected)** |
| **Baselines** | B3 = E4 rung (upper bound) · A4 = E0 rung (floor) |
| **Confirms C4 if** | TPR rises monotonically E0→E4 with a usable middle rung |
| **Falsifies C4 if** | no rung detects usefully, **or** E1 ≈ E4 (the ladder adds nothing) |
| **Why FPR matters** | `LIT`: under non-IID data, honest clients look like outliers. A rule with high TPR and high FPR is useless — it silently excludes honest participants, which is exactly the harm AG1 exists to make visible. |
| **Dataset needed** | **Yes** — Fashion-MNIST, Dirichlet split |
| **Artifact** | TPR/FPR vs disclosure level, one line per attack; ROC-style view |

### E-5 — Slow-drift attacker → tests **C5** (the falsification path)

| Field | Value |
|---|---|
| **Question** | Can an attacker who knows the admission rule stay inside its bounds and still poison the model? |
| **Attacker** | "A Little Is Enough"-style (`LIT`, Baruch et al. NeurIPS 2019): perturbation scaled to sit just inside the admission threshold, applied over many rounds |
| **Independent vars** | drift magnitude as a fraction of the admission threshold (0.1…1.5×) · malicious fraction (0.05…0.3) · rounds (30–60) |
| **Dependent vars** | **fraction of malicious updates admitted** · main-task accuracy vs clean run · attack objective success |
| **Expected outcome** | **The attacker succeeds at drift < 1.0× threshold.** We predict C5 is FALSE. |
| **Why we run it anyway** | It bounds what the contribution means. AG1 proves *the declared rule was applied*, not *the rule was good enough*. Demonstrating that boundary precisely is more valuable than hiding it. |
| **Reported as** | a headline limitation, not a footnote |
| **Dataset needed** | Yes — Fashion-MNIST |
| **Artifact** | admitted-rate vs drift magnitude; accuracy-over-rounds, clean vs attacked |

### E-6 — Auditors absent → honesty check on AG3

| Field | Value |
|---|---|
| **Question** | What survives when nobody compares views? |
| **Independent vars** | number of independent auditors comparing roots ∈ {0, 1, 2, 5} |
| **Dependent vars** | split-view detection rate; time-to-detection in rounds |
| **Expected** | **0 auditors → 0% split-view detection.** Single-view tampering (edits, reorder, deletion) still caught. |
| **Why it exists** | `LIT`: CT specified gossip but it was never widely deployed; systems assume *"global sets of auditors, who must be blindly trusted"*. A security argument that reduces to "someone will check" must be tested with nobody checking. |
| **Dataset needed** | None |
| **Artifact** | small table: attack class × auditor count → detection |

---

## 5. What each experiment forces us to build

This is the gate on `IMPLEMENTATION_PLAN.md`. **Build order follows experiment need.**

| Component | Needed by | Verdict |
|---|---|---|
| Merkle transcript (T-A1, T-A3) | E-1, E-2, E-6 | **BUILT** (`IMPL`) |
| Ed25519 signing (T-B1) | E-2 (forged attestation), E-3 | **BUILD — small, clearly needed** |
| Verifiable sortition (T-C1) | **E-3 is entirely about this** | **BUILD** |
| Evidence ladder E0–E4 (T-C2) | E-4 | **BUILD** |
| Admission rule (T-C3) | E-4, E-5 | **BUILD — keep it simple** (norm/cosine threshold; a fancier rule is not the contribution) |
| Threshold attestation (T-C4) | E-2, E-3 | **BUILD** |
| Auditor (T-D2) | E-1, E-2, E-6 | **BUILD** |
| Simplified SecAgg masking (T-D1) | E-4 (establishes what the aggregator cannot see) | **BUILD — minimal**, no dropout recovery (`D-010`) |
| FL loop + Fashion-MNIST (T-E1) | E-4, E-5 only | **BUILD — after** the no-dataset experiments land |
| **Real blockchain / testnet** | *nothing* | **DO NOT BUILD** |
| **ZK proofs** | *nothing* — the contribution is the ZK-free point | **DO NOT BUILD** |
| **Full Bonawitz SecAgg with dropout recovery** | *nothing* — E-4 only needs "aggregator sees masked inputs" | **DO NOT BUILD** |
| **Reputation / staking / incentives** | *nothing* | **DO NOT BUILD** |
| **Network layer / RPC / multi-process** | *nothing* — all experiments are in-process simulations | **DO NOT BUILD** |

Five things explicitly cut. Each would have made the project look bigger and prove nothing more.

---

## 6. Reproducibility contract

Every experiment run emits a `manifest.json` next to its results containing: experiment ID, git commit SHA, all config parameters, the RNG seed, resolved package versions, CPU/OS, wall-clock time, and a SHA-256 of the output. Re-running the same manifest must reproduce identical metrics.

- Seeds fixed per run; **each stochastic experiment (E-3, E-4, E-5) repeats over ≥ 5 seeds** and reports mean ± std, never a single run.
- Every experiment is a scripted entry point under `scripts/`; **no undocumented manual steps.**
- Raw results are written as CSV/JSON; plots regenerate from those files, never from memory.

---

## 7. Sequencing

**Phase 1 — no dataset required.** E-1, E-2, E-3, E-6. These test C1, C2, C3 and produce most of the portfolio artifacts. They are fast, deterministic, and independent of any download.

**Phase 2 — training required.** E-4, then E-5.

Running Phase 1 first means that if time runs short, the project still has a complete, defensible core result set. **E-5 is not deferred for being inconvenient** — it is second only because it depends on the FL loop that E-4 also needs.

---

## 8. What a strong result looks like — and what an honest weak one looks like

**Strong:** verification is flat in N and logarithmic in transcript size; every in-scope tamper is caught with zero false positives; committee corruption matches the analytic model so safe parameters can be *chosen* rather than guessed; the disclosure ladder shows a usable middle rung; and the slow-drift attacker succeeds, precisely bounding what the mechanism does and does not promise.

**Honest weak:** if A1/A2/A3 show the Merkle tree or chaining adds nothing over a signed log, we say so and the contribution narrows to the committee attestation alone. If E-4 shows E1 ≈ E4, the ladder collapses and we report that disclosure level barely matters for this rule.

**Either outcome is publishable as a final-year project.** What would not be acceptable is quietly dropping the experiment that produced the inconvenient answer.
