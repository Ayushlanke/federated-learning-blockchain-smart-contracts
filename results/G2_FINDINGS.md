# G2 Findings — Second-Generation Admission Rule

**Experiment:** `scripts/exp_g2.py`, 235 runs · **Hypotheses pre-registered in `G2_PREREGISTRATION.md` before this ran.**
**The G1 results in `E4_E5_FINDINGS.md` are unchanged.**

> ## VERDICT: **B — qualified result.**
> G2 improves detection materially on some attacks (sign-flip **0.33 → 0.61**) and modestly on others, at slightly *lower* false-positive rate. **It does not reach the pre-registered bar on the headline attack.** Slow-drift TPR rises only 0.32 → 0.43, and my own criteria put a gain that small in **C territory** for that attack specifically. Both readings are reported below; I am not picking the flattering one.

---

## 1. Main comparison — 20% malicious, 3 seeds, disclosure E3

| Attack | G1 TPR | G2 TPR | Δ | G1 FPR | G2 FPR | No-rule acc | G1 acc | G2 acc |
|---|---|---|---|---|---|---|---|---|
| no attack | — | — | — | 0.12 | **0.10** | 0.762 | 0.775 | 0.770 |
| **sign-flip** | 0.33 | **0.61** | **+0.28** | 0.06 | 0.05 | 0.647 | 0.685 | **0.736** |
| label-flip | **0.93** | 0.87 | −0.06 | 0.03 | 0.03 | 0.540 | 0.763 | 0.752 |
| scaled | 1.00 | 1.00 | — | 0.04 | 0.07 | **0.100** | 0.734 | 0.737 |
| noise | 0.23 | **0.34** | +0.11 | 0.06 | 0.05 | 0.763 | 0.760 | 0.765 |
| targeted | 0.22 | 0.22 | — | 0.08 | 0.06 | 0.766 | 0.758 | 0.752 |
| **slow-drift** | 0.32 | **0.43** | **+0.11** | 0.07 | 0.05 | 0.760 | 0.756 | 0.757 |

**What improved.** Sign-flip is the clear win: +0.28 TPR and **+5 accuracy points** (0.685 → 0.736). This is exactly the predicted mechanism — sign-flip reverses direction while preserving norm, so a normalised directional test is precisely the right instrument. Noise and slow-drift each gain +0.11. FPR is unchanged or slightly better throughout.

**What did not.** Label-flip regressed slightly (0.93 → 0.87); targeted poisoning is untouched at 0.22 by both rules. Scaled remains trivially caught (1.00) — and the **no-rule accuracy of 0.100 (random guessing)** is the reminder that *some* rule is enormously better than none.

---

## 2. The headline: slow-drift β sweep, 5 seeds

| β | G1 TPR | G1 admitted | G2 TPR | G2 admitted |
|---|---|---|---|---|
| 0.25 | 0.00 | 1.00 | **0.20** | 0.80 |
| 0.50 | 0.02 | 0.98 | **0.23** | 0.77 |
| 0.75 | 0.11 | 0.89 | **0.29** | 0.71 |
| 0.90 | 0.29 | 0.71 | **0.38** | 0.62 |
| 1.10 | 0.61 | 0.39 | 0.59 | 0.41 |
| 1.50 | 0.92 | 0.08 | 0.93 | 0.07 |

**G2 is strictly better than G1 in exactly the region that matters** — deep inside the threshold, where G1 detected essentially nothing (0.00–0.11) and G2 detects 0.20–0.29. That is a real, consistent improvement and it confirms the diagnosis: the magnitude channel was the flaw.

**But it is nowhere near sufficient.** At β=0.9 the attacker still gets 62% of its updates admitted. **C5 remains false under G2.**

---

## 3. G2-P3 REFUTED — accumulation is not doing the work

The warm-up ablation was meant to confirm that cross-round accumulation drives the improvement. It shows the opposite:

| Warm-up W | TPR vs slow-drift | FPR |
|---|---|---|
| 1 | **0.42 ± 0.04** | 0.04 |
| 2 | 0.39 ± 0.06 | 0.04 |
| 3 | 0.37 ± 0.13 | 0.04 |
| 5 | **0.30 ± 0.02** | 0.03 |

**A longer warm-up makes G2 *worse*.** The gain comes from the **within-round direction test on normalised sketches**, not from the reputation. A longer warm-up simply hands the attacker more free rounds before any reputation test applies, and that outweighs the better statistic.

### Why the diagnostic and the experiment disagree — and what I am *not* doing about it

The design diagnostic showed per-client scores separating **perfectly** (AUC 1.000) after 3 rounds. That result stands: the *statistic* separates. What fails is the **conversion of separation into rejections** — the pre-registered cutoff `median(R) − 3·MAD(R)` is too lenient to fire even when the populations are cleanly separated, because the honest spread under non-IID is wide.

**The bottleneck is the threshold, not the signal.**

Loosening that cutoff after seeing these results would be exactly the post-hoc tuning I was asked not to do, and it would invalidate the pre-registration. **It is therefore recorded as an identified limitation with a specific, testable fix (a separation-aware cutoff, e.g. Otsu or a gap statistic on the reputation distribution) and left for future work.** Anyone repeating this should pre-register that cutoff before running.

---

## 4. G2-P5 — the adaptive attacker (A7), oracle-informed

| γ (malicious fraction of direction) | TPR | admitted | accuracy | damage vs clean |
|---|---|---|---|---|
| 0.00 | 0.00 | 1.00 | 0.749 | 0.021 |
| 0.25 | 0.00 | 1.00 | 0.737 | 0.032 |
| 0.50 | 0.00 | 1.00 | 0.754 | 0.016 |
| 0.75 | 0.13 | 0.87 | 0.767 | 0.003 |
| 1.00 | 0.34 | 0.66 | 0.761 | 0.008 |

**The adaptive attacker evades G2 completely at γ ≤ 0.5 — TPR exactly 0.00.** Blending even half the honest consensus direction into its update makes it invisible.

**But its damage never exceeds noise** (0.003–0.032 accuracy, against a clean-run standard deviation of similar size). Evasion is free, and also pointless: at 20% malicious this attacker cannot convert invisibility into harm. That echoes E-5's finding and is the honest reading — **not** a claim that G2 defeats it. `LIT` MESAS (CCS 2023) predicts exactly this: any few-metric rule is adaptively evadable.

---

## 5. G2-P7 — commit-then-sketch works, partially

| Projection seed | TPR vs null-space (A8) | admitted |
|---|---|---|
| predictable | 0.35 | 0.65 |
| **commit-then-sketch** | **0.44** | **0.56** |

Confirms the fix helps and confirms it is not a cure — exactly as pre-registered. The structural blindness is removed (the attacker can no longer *guarantee* invisibility), but a wrong-guess perturbation is directionally random and only partly caught.

---

## 6. G2-P4 CONFIRMED — the mechanism still costs nothing in ML terms

| Attack | S1b (G2, trusted server) | S3 (G2 + full mechanism) | Difference |
|---|---|---|---|
| sign-flip | 0.7361 | 0.7361 | **0.0e+00** |
| label-flip | 0.7519 | 0.7519 | **0.0e+00** |

Identical to machine precision, identical TPR, differing only by **51,215 bytes of transcript** (~2 KB/round). *(The slow-drift row is omitted: the S1b and S3 seed sets differ there because of overlapping sweeps, so it is not a like-for-like comparison.)*

**This is the project's central result, now reproduced with a second, better rule.** The verifiable mechanism is rule-agnostic: swap in a stronger rule and the accountability guarantees and costs are unchanged.

---

## 7. Scorecard against the pre-registration

| ID | Prediction | Outcome |
|---|---|---|
| G2-P1 | TPR ≥ 0.80 on slow drift | **FAILED** — 0.43 |
| G2-P2 | sign-flip > 0.70 | **FAILED narrowly** — 0.61 (from 0.33) |
| G2-P3 | advantage requires the warm-up | **REFUTED** — longer warm-up is *worse* |
| G2-P4 | S3 ≡ S1b on ML metrics | **CONFIRMED** — 0.0e+00 |
| G2-P5 | adaptive attacker trades damage for evasion | **PARTIALLY** — evades free at γ≤0.5, but does no damage either way |
| G2-P6 | FPR ≤ 0.12 | **CONFIRMED** — 0.10 |
| G2-P7 | commit-then-sketch helps, below 0.8 | **CONFIRMED** — 0.35 → 0.44 |
| G2-P8 | A8 detection < sign-flip detection | **CONFIRMED** — 0.44 < 0.61 |

**Three of eight predictions failed or were refuted.** That is what pre-registration is for.

---

## 8. Verdict, and the tension in my own criteria

The pre-registered criteria were:

- **A** — TPR ≥ 0.80 at FPR ≤ 0.10 on slow drift **and** sign-flip **and** label-flip, and A7 must sacrifice ≥50% damage to evade. → **Not met** (0.43, 0.61, 0.87).
- **C** — "does not meaningfully improve on G1 (**< 0.2 absolute TPR gain on slow drift**)". → Gain is **0.11**. **By the letter, the slow-drift criterion lands in C.**
- **B** — substantially improves some attacks but not others. → sign-flip **+0.28** is substantial; noise +0.11; FPR unchanged or better.

**I am reporting this as B, and flagging that my own slow-drift-specific criterion says C.** Both are true: G2 is a genuine improvement on several attacks and a *marginal* one on the attack the project was named around. Choosing only the B framing would be selective reporting.

---

## 9. The scientific answer to the question that was asked

> *Is the E-5 negative result a limitation of the specific rule, or of committee-backed verifiable admission?*

**Of the rule — but the rule is harder to fix than expected, and the deeper limit is not disclosure.**

Three pieces of evidence:

1. **A better rule does measurably better** with identical disclosure, identical mechanism, identical cost. The magnitude/direction diagnosis was correct: sign-flip +0.28, slow-drift strictly better at every β below threshold.
2. **The mechanism was never the bottleneck.** S3 ≡ S1b to machine precision, twice over, with two different rules. Verifiable admission imposes no ML cost and constrains no rule.
3. **But the ceiling is intrinsic to single-round, bounded-evidence rules.** Full-plaintext disclosure (E4) reached only 0.33 on slow drift — the limit is signal-to-noise under non-IID heterogeneity, not privacy. And an adaptive attacker with oracle knowledge evades *completely* at γ≤0.5. `LIT` MESAS's thesis — that any few-metric rule is adaptively evadable — is supported by our own data.

**The honest final position:** BC-FL-SRV provides cheap, verifiable, quantifiably sound accountability for admission decisions, and that accountability is **rule-agnostic** — demonstrated across two generations of rule. Making the *rule* strong enough to stop a patient, rule-aware attacker is a separate and unsolved problem, and this project narrows it without closing it.
