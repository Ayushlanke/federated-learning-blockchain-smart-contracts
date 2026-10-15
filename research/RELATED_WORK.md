# Related Work — BC-FL-SRV

Curated prior art. Every entry carries an **evidence tag** stating how strongly it is
established, so a reader can tell what the literature says from what we assume.

| Tag | Meaning |
|---|---|
| `VERIFIED` | Full paper text read directly in this project |
| `ABSTRACT` | Abstract / landing page read directly |
| `SECONDARY` | Only seen described in another source — **needs primary check before relied on** |
| `PAYWALLED` | Could not be reached from this environment (ACM DL / IEEE Xplore) |

---

## 1. The anchor paper

**Rizzini, Esposito, Gagliardoni, Bruschi — "SoK: Verifiable Integrity Claims for
Privacy-Preserving Federated Learning."** *Proceedings on Privacy Enhancing
Technologies* **2026(4): 248–271.** IACR ePrint 2025/2296. — `VERIFIED` (full 24-page text)

Models FL as *"an append-only transcript of submissions, admissions, aggregation, and
finalization events"* and formalises verifiability as **integrity claims** checked by
verifier classes `V ∈ {AG}, {AG,CL}, {auditor}, {public}`.

**Aggregator-side claims (quoted):**

| Claim | Definition |
|---|---|
| **AG1** Correct admission set | *"the aggregator neither adds nor omits submissions relative to the declared verification rule"* |
| **AG2** Correct aggregation | output consistent with the declared rule over exactly the admitted submissions |
| **AG3** Non-equivocation | *"cannot present different aggregates to different verifiers (or at different times) without detection"* — enforced by binding into the shared transcript |

**Table 2 — Deployability of integrity claims** (verbatim; the evidence the project's
positioning rests on):

| Claim | Adoption (/13) | Complexity | Ease of impl. (/5) |
|---|---|---|---|
| CL1 | 2 | O(D) | 4 |
| CL2 | 6 | O(E·D·N) | 1 |
| CL3 | 5 | O(N) | 3 |
| CL4 | 1 | O(1) | 5 |
| **AG1** | **2** | **O(K)** | **4.5** |
| AG2 | 10 | O(K·N) | 2 |
| **AG3** | **3** | **O(1)** | **5** |

Its own conclusion: *"a concentration of prior work on verifiable aggregation, while
alternative verifiability claims receive limited coverage in the literature, despite
their practical implementability (e.g. CL1, CL4, AG1, AG3)."*
Its **Table 5** maps **AG1+AG3 → mitigating *selective dropping* and *split-view***.

### 1.1 The specific opening BC-FL-SRV targets — `VERIFIED`

The SoK's *Excluded papers* discussion rules out custom-primitive (non-ZK, non-TEE)
schemes — VerifyNet, bilinear-aggregate-signature approaches, Lagrange-interpolation
approaches — for two stated reasons:

1. *"verification is restricted to protocol participants only: the correctness check
   relies on secret parameters distributed by a trusted authority during setup, so that
   any external party, such as a regulator or third-party auditor … cannot verify
   anything, even ex-post over a recorded transcript."*
2. *"The proving methodology is structurally limited to a partial coverage of AG2 and
   **cannot extend to AG1, since there is no mechanism to bind the aggregation output to
   a declared admission set**."*

**This is the gap BC-FL-SRV addresses.** It supplies exactly that missing binding — a
committee-attested admission-set digest recorded in the transcript — using public-key
signatures (so *any* external party can verify, answering objection 1) and explicit
admission-set recording (answering objection 2). The SoK itself invites this:
*"Future works referring to our classification framework with a focus on different
primitives, can still explore a hybrid approach."*

### 1.2 Honest caveat on the novelty claim — stated deliberately

The SoK **scoped itself** to ZKP- and TEE-based instantiations. Therefore "no
committee-based AG1 appears in the SoK" is **partly an artifact of its inclusion
criteria**, not proof that no such work exists. The claim BC-FL-SRV makes is the
narrow, defensible one: *this design point is not covered by the most recent
systematization of verifiable FL, and that systematization explicitly argues cheap
primitives cannot reach AG1.* We do not claim "nobody has ever done this."

### 1.3 Blockchain roles, per the SoK's Table 4 — `VERIFIED`

- **Passive role** — auditability medium: events/commitments recorded on-chain for
  ex-post inspection.
- **Active role** — verifiability medium: proofs verified on-chain by smart contracts.
- *"the dominant pattern results the active one"* — most surveyed systems verify ZK
  proofs on-chain.

BC-FL-SRV deliberately occupies the **passive** role with **committee attestations
instead of ZK proofs** — a combination absent from that table.

---

## 2. Secure aggregation and its limits

| Work | Venue | What it gives | What it does NOT give | Tag |
|---|---|---|---|---|
| Bonawitz et al., SecAgg | CCS 2017 | server learns only the sum; dropout resilience via secret sharing | robustness, DP, protection from a malicious committee | `SECONDARY` |
| Bell et al., SecAgg+ | CCS 2020 | polylog communication via sparse graphs | as above | `SECONDARY` |
| **Flamingo** | IEEE S&P 2023 | multi-round single-server secure aggregation | robustness | `VERIFIED` (full text) |
| **RoFL** | IEEE S&P 2023 | **norm bounds enforced under encryption** via ZK | outlier rejection; **cannot stop a within-bound poisoning attack** | `VERIFIED` (full text) |
| **EIFFeL** | CCS 2022 | integrity for verified inputs under secure aggregation | | `VERIFIED` (full text) |
| Pasquini et al., "Eluding Secure Aggregation via Model Inconsistency" | CCS 2022 | a malicious server can break SecAgg privacy via inconsistent models | — | `SECONDARY` |

**Key point BC-FL-SRV relies on:** SecAgg hides individual updates *from the
aggregator*. It provides **no** robustness and **no** differential privacy. These are
distinct properties and the spec keeps them distinct.

---

## 3. Robustness under privacy — the crowded space (why framings F1/F2 were killed)

| Work | Venue | Relevance | Tag |
|---|---|---|---|
| **FedGT** — Xhemrishi, Östman, Wachter-Zeh, Graell i Amat | IEEE TIFS 2025 (arXiv 2305.05506) | Identifies malicious clients **under secure aggregation** by overlapping-group testing. Group size 1 = plaintext FL, group size N = full SecAgg — an explicit tunable privacy/security knob. | `ABSTRACT`; full text `PAYWALLED` |
| **Detect & Score** — Xhemrishi, Graell i Amat, Pejó | arXiv 2506.23583 (2025) | Combines FedGT (detection) with QI (contribution evaluation); QI is multi-round. | `ABSTRACT`; ACM DL **HTTP 403** |
| **ClusterGuard** | IACR ePrint 2024/2082 | Secure clustered aggregation with a **historical frequency table across rounds**. | `VERIFIED` (full text) |
| BREA / ByzSecAgg | — | Recover distance-based detection via secret sharing, but **leak pairwise distances** to the aggregator. | `SECONDARY` |
| ELSA, ACORN, zPROBE, PriRoAgg, LoByITFL | S&P'23 / USENIX'23 / ICCV'23 / 2024 / 2024 | Other privacy-preserving robust-aggregation points. | `SECONDARY` |

**Consequence:** "robustness under secure aggregation" is **saturated**. BC-FL-SRV does
not compete there. It targets *verifiability of the admission decision* (AG1), which is
a different claim, not a better detection rule.

---

## 4. The impossibility that bounds every claim

**Allouah, Guerraoui et al. — "On the Privacy-Robustness-Utility Trilemma in
Distributed Learning."** ICML 2023 (arXiv 2302.04787). — `ABSTRACT`

Proves a fundamental trade-off: no algorithm simultaneously achieves strong privacy,
robustness, and utility.

> **Precision matters here.** The trilemma is proved for **differential privacy**, not
> for secure-aggregation privacy. SecAgg hides individual updates from the server while
> revealing the sum — a different, weaker notion. The impossibility therefore does not
> transfer directly to a SecAgg-only setting. BC-FL-SRV states this distinction
> explicitly and **never claims to resolve the tension.**

---

## 5. Attacks that must be taken seriously

| Work | Venue | Why it matters here | Tag |
|---|---|---|---|
| **"Manipulating the Byzantine" — Shejwalkar & Houmansadr** | NDSS 2021 | AGR-tailored and AGR-agnostic attacks that defeat robust aggregation rules | `VERIFIED` (full text) |
| **Fang et al., Local Model Poisoning** | USENIX Sec 2020 | breaks Krum / trimmed-mean | `VERIFIED` (full text) |
| Baruch et al., "A Little Is Enough" | NeurIPS 2019 | **bounded perturbations that stay inside detection thresholds** — direct inspiration for our slow-drift attacker | `SECONDARY` |
| Bagdasaryan et al., constrain-and-scale | AISTATS 2020 | backdoors that evade anomaly detection | `SECONDARY` |
| **FLTrust** | NDSS 2021 | server-side root-dataset robustness baseline | `VERIFIED` (full text) |

**The one that defines our falsification path:** a "little is enough"-style attacker
tunes its update to sit *inside* whatever bound the admission rule enforces. If it
succeeds, verifiable admission is **verifiably useless** — the mechanism faithfully
attests that a poisoned update was legitimately admitted. We test for this on purpose.

---

## 6. Evaluation realism

**Shejwalkar, Houmansadr, Kairouz, Ramage — "Back to the Drawing Board: A Critical
Evaluation of Poisoning Attacks on Production Federated Learning."** IEEE S&P 2022.
— `VERIFIED` (full text)

Argues FL is *"highly robust in practice even when using simple, low-cost defenses"*
and that much prior work assumes unrealistically high malicious-client fractions.

**How BC-FL-SRV complies:** malicious fractions are swept across a range with the
realistic low end foregrounded, never reported at a single convenient value.

---

## 7. Transparency logs — where the ledger claims come from

| Work | Venue | Contribution | Limitation we inherit | Tag |
|---|---|---|---|---|
| **Crosby & Wallach**, tamper-evident logging | USENIX Sec 2009 | Merkle "history tree", O(log n) inclusion + consistency proofs | **tamper-evidence, not prevention**; the logger can still equivocate unless auditors compare views | `SECONDARY` |
| **RFC 6962** Certificate Transparency | IETF | the inclusion/consistency proof constructions BC-FL-SRV implements | same | `VERIFIED` (implemented) |
| **Chase & Meiklejohn**, Transparency Overlays | ACM CCS 2016 | formal transparency model; gossip as an Auditor–Monitor interaction producing evidence | security theorem is **conditional on gossip actually happening** | `SECONDARY` |
| **"Think Global, Act Local"** — gossip and client audits | arXiv 2011.04551 | argues transparency systems rely on *"global sets of auditors, who must be blindly trusted"* | client-side auditing reintroduces a privacy leak | `VERIFIED` (full text) |
| **SoK: SCT Auditing in CT** | PETS 2022 | *"requesting a proof of inclusion directly reveals the certificate"* | **inclusion queries leak** | `ABSTRACT` |

### 7.1 Two lessons that shaped the design

1. **A log gives tamper-evidence, not tamper-prevention.** BC-FL-SRV never writes "the
   ledger guarantees X"; it states the property and the auditing assumption behind it.
2. **CT's gossip layer — the load-bearing part of its security argument — was never
   widely deployed.** So BC-FL-SRV must not build a security argument that reduces to
   "someone will check". The **auditors-absent** condition is an explicit experiment.

### 7.2 A tension we import into FL — threat T-7

From PETS 2022: an inclusion-proof query discloses what is being queried. Transplanted
to FL, a client asking *"was my update admitted in round t?"* **discloses its
participation pattern** — under exactly the SecAgg regime meant to hide it. Recorded as
threat T-7; the audit interface is designed around it.

---

## 8. Outstanding primary-source checks

Cited but **not** fully verified from this environment. To be checked before any
external submission; none is load-bearing for the implementation:

- **FedGT** full text (IEEE TIFS 2025) — `PAYWALLED`
- **Detect & Score** (ACM DL returned HTTP 403) — `PAYWALLED`
- Bonawitz SecAgg, Bell SecAgg+, Baruch "A Little Is Enough", Bagdasaryan — `SECONDARY`
- The SoK's references [2], [20], [47], [51], [66], [98] — the systems it credits with
  AG1/AG3 coverage. Their venues are confirmed from the SoK's own tables (IEEE ICAIC
  2024, Prog. in AI 2025, arXiv 2025, IEEE TII 2023, ACM 2024, IEEE TBDATA 2023) and
  **all are ZKP- or TEE-based** — which is the fact our positioning actually uses.
