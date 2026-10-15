# E-2 Findings — Tamper Detection

**Experiment:** E-2 (`scripts/exp_e2_tamper_detection.py`)
**Tests:** sub-claim **C1** — *"an auditor holding only the transcript can detect admission tampering"*
**Date:** 2026-09-04 · Population 50, participants 20, committee 9, threshold 6
**Reproduce:** `.venv/Scripts/python.exe scripts/exp_e2_tamper_detection.py`
**Provenance:** `results/runs/e2_*/manifest.json` (clean working tree)

Status tags: `LIT` literature · `HYP` hypothesis · `IMPL` implemented · `RESULT` measured here.

---

## 1. The detection matrix `RESULT`

| Attack | Class | BC-FL-SRV | B1 signed log | B2 self-attested |
|---|---|:---:|:---:|:---:|
| entry edit | transcript | ✅ | ✅ | ✅ |
| entry reorder | transcript | ✅ | ✅ | ✅ |
| entry deletion | transcript | ✅ | ✅ | ✅ |
| truncation vs known root | transcript | ✅ | ✅ | ✅ |
| admitted without submission | AG1 | ✅ | ❌ | ✅ |
| forged admission set | AG1 | ✅ | ❌ | ❌ |
| below-threshold attestation | AG1 | ✅ | ❌ | ❌ |
| outsider signers | AG1 | ✅ | ❌ | ❌ |
| **dishonest rejection (aggregator alone)** | AG1 | ✅ | ❌ | ❌ |
| cross-round attestation replay | AG1 | ✅ | ❌ | ❌ |
| selective drop — public auditor | AG1 | ❌ | ❌ | ❌ |
| selective drop — client self-audit | AG1 | ✅ | ❌ | ❌ |
| split view — 1 observer | AG3 | ❌ | ❌ | ❌ |
| split view — 2 observers | AG3 | ✅ | ✅ | ✅ |
| **Total** | | **12/14** | **5/14** | **6/14** |

**False positives: 0 over 50 honest rounds.** Every outcome matched its pre-registered expectation; the script exits non-zero if any row deviates, so this is a regression test as well as an experiment.

---

## 2. What this demonstrates

1. **C1 is supported, with a stated boundary.** `RESULT` Every attack the transcript *can* expose is caught, with no false positives. The two misses were predicted in advance and are properties of the threat model, not bugs.

2. **The committee earns its place — this is the key row.** `RESULT` *"Dishonest rejection (aggregator alone)"*: an aggregator excludes an honest client for no reason. Under BC-FL-SRV this requires **6 of 9 committee members to co-sign**, so an aggregator acting alone is caught. Under B2 (self-attestation) it requires nothing and leaves no trace. **This single row is the experimental justification for the whole committee design** — without it, B2 would be the simpler and equally good answer.

3. **A signed log is not enough.** `RESULT` B1 catches transcript tampering (5/14) but is blind to every AG1 attack, because a log with no notion of an admission *decision* cannot detect a dishonest one. This is the data behind the "why not just sign the log?" answer, and it complements E-1's finding that B1 is also 1,683× slower to verify.

4. **Zero false positives matters as much as the detections.** `LIT` The transparency-log literature is blunt that auditing which nobody performs provides nothing. An auditor that cried wolf on honest rounds would not be run — so a 0% false-positive rate over 50 honest rounds is a usability result, not a footnote.

---

## 3. What this does NOT demonstrate

1. **It does not test committee *collusion*.** Every attack here assumes an adversary who cannot muster the threshold. A coalition of 6+ committee members can sign any admission set and this auditor will accept it. That is **E-3**, and it is the real soundness boundary. `HYP`

2. **It does not test whether the admission rule is any good.** The rule here is *admit everything*. E-2 asks "was the declared rule faithfully applied and recorded?", never "was the rule worth applying?" A faithfully-recorded bad decision passes this audit cleanly. That gap is **E-4/E-5**, and it is where the project's honest negative result is expected.

3. **Selective dropping is invisible to a public auditor.** `RESULT` Confirmed experimentally, not merely argued. If the aggregator never records a submission, the transcript is internally perfect. Detection requires the *client* to check its own inclusion — which works (row 12) but shifts the burden onto clients and triggers threat **T-7**: asking "was my update included in round t?" discloses participation, under exactly the secure-aggregation regime meant to hide it.

4. **Split view is undetectable with one observer.** `RESULT` Exactly as the Certificate Transparency literature predicts. Two observers catch it immediately; one never does. Since CT's gossip layer was specified but never widely deployed `LIT`, this is a real deployment risk, not a theoretical one — and **E-6** measures the system with the auditor population set to zero.

5. **Simulation, single configuration.** One committee size, one threshold, in-process. No network adversary, no timing or ordering attacks, no Sybil creation of identities.

6. **B2 is a reasonable but not exhaustive stand-in.** It models "aggregator self-attests" while retaining structural transcript checks. A different self-attesting design might catch marginally more; the qualitative conclusion — self-attestation cannot detect a dishonest decision by the self-attesting party — is structural and does not depend on the modelling detail.

---

## 4. Effect on the research hypothesis

| Sub-claim | Before E-2 | After E-2 | Basis |
|---|---|---|---|
| **C1** — tampering detectable | `HYP` | **supported within the stated threat model** `RESULT` | 12/14, 0 false positives |
| **C2** — cost independent of N | supported (E-1) | unchanged | — |
| **C3** — soundness degrades predictably | `HYP` | still open — **now the critical unknown** | E-3 |
| **C4** — disclosure buys detection | `HYP` | unchanged | E-4 |
| **C5** — stops slow drift | `HYP` (predicted false) | unchanged | E-5 |

**Net.** RD-001 now has evidence on two of five sub-claims. The mechanism is **cheap** (E-1) and **catches what it claims to catch** (E-2). What remains untested is the part that decides whether any of it matters:

- **E-3** — how much collusion breaks it. Without this, "detected" only means "detected against an adversary too weak to bribe six people."
- **E-4/E-5** — whether the *decision being attested* is worth attesting. Faithfully recording a decision made by a rule that a slow-drift attacker walks through is a well-audited failure.

**An honest one-line summary for the report:** *E-2 shows the accountability layer works against every adversary weaker than the committee threshold, and that neither a signed log nor self-attestation achieves the same. It says nothing yet about adversaries stronger than the threshold, or about whether the underlying admission rule is any good.*

---

## 5. An observation worth keeping for the write-up

The three-way split of attacks — transcript-detectable, client-detectable, undetectable-with-one-view — was not designed in advance. It **fell out of implementing the auditor honestly**: when writing `audit()`, there was no way to detect a submission that was never recorded, and the choice was to expose that as `AuditReport.unchecked` rather than let a PASS imply more than it meant.

That split turned out to be the most useful framing in the project so far. It maps cleanly onto the Certificate Transparency experience `LIT`, where the same structure appears: the log proves its own consistency, clients must check their own inclusion, and equivocation needs gossip that was never deployed. Arriving at the same three-way split independently, from a federated-learning starting point, is a modest but genuine validation that the problem was framed correctly.
