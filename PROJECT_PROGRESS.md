# PROJECT_PROGRESS.md — BC-FL-SRV

**Canary:** `KING`
**Current session:** 1
**Date:** 2026-09-03
**Phase:** 2 — Implementation (research definition LOCKED). **See "SESSION 1 CLOSE-OUT" at the end of this file for current status; Sections 3-6 below are the pre-lock snapshot and are SUPERSEDED.**

---

## 1. Effective Section 1 parameters — LOCKED

Section 1 of the master directive was left blank. Per its instruction, defaults apply and are recorded here. **These are not to be asked about again.** A later change is logged as a `DECISIONS.md` entry, not a silent edit.

| Parameter | Effective value | Source |
|---|---|---|
| Deadline(s) | ~10–12 working sessions; research-critical work front-loaded | directive default |
| Team | solo | directive default |
| Target outcome | degree submission + a workshop-paper-shaped artifact | directive default |
| Compute available | single laptop, **CPU-only** — measured: 12 logical cores, `torch 2.12.0+cpu`, `cuda.is_available()==False` | directive default, **confirmed by measurement** |
| Blockchain requirement | local append-only Merkle-hash-chained ledger; **no real testnet** | directive default |
| Dataset domain | a standard FL benchmark with non-IID splits (FEMNIST or CIFAR-10 Dirichlet); **never collect new data**. Specific choice is deferred to a logged decision once `RD-001` fixes what must be measured. | directive default |
| Advisor / evaluator constraints | none fixed | directive default |
| ECC plugin capabilities | inventoried by direct file inspection → `TOOLING_INVENTORY.md` | Section 4 |
| **Locality constraint** (added) | **Every install and every artifact stays inside `C:\Study`. Nothing global.** | **user instruction, Session 1** |

### Locality compliance — VERIFIED

- Python deps → `C:\Study\.venv\Lib\site-packages` (confirmed by resolving `__file__` for each package).
- `torch`/`numpy`/`scipy`/`sklearn`/`pandas` are **read** from the base interpreter via `--system-site-packages`; **nothing was installed globally** (avoids a ~2 GB redundant torch download).
- git config is repo-scoped; `--global` was never invoked.
- The ECC plugin pre-existed at user scope (installed 2026-09-03T06:26, before this project) and is **not modified**.

---

## 2. Anti-drift check (Section 2) — Session 1

**Fixed goal, restated:** BC-FL-SRV is a real, running, tested research system combining **federated learning** + **distributed-ledger anchoring** + **secure/robust verification of client contributions**, built to directly test one falsifiable hypothesis about that combination.

**Status (updated at close-out):** `RD-001` is LOCKED and **CONFIRMED to test the fixed goal**. All three pillars are structurally necessary: the object verified is an FL round; AG3 is *defined* by the append-only transcript, so the ledger is load-bearing; AG1 attests a robust admission rule applied under secure aggregation.

---

## 3. Phase status — SUPERSEDED by SESSION 1 CLOSE-OUT (kept as the pre-lock snapshot)

| Phase | Status |
|---|---|
| 0. Environment + tooling inventory | **DONE** — `TOOLING_INVENTORY.md` |
| 1. Literature survey (Section 11) | **IN PROGRESS** — 15-agent parallel survey running |
| 2. ≥3 candidate framings + prior-art kill matrix (Section 3) | NOT STARTED |
| 3. Research Gap Statement | NOT STARTED |
| 4. `RD-001` lock | NOT STARTED |
| 5. Contribution Boundary Analysis (Section 5) | NOT STARTED |
| 6. SecAgg ↔ Byzantine-robustness stance (Section 15) | NOT STARTED |
| 7. Scope classification lock (Section 6) | NOT STARTED |
| 8. Architecture + adversarial self-review (Section 12) | NOT STARTED |
| 9. `PROJECT_MASTER_SPEC.md` | NOT STARTED |
| 10. `IMPLEMENTATION_PLAN.md` | NOT STARTED |
| 11. Repo structure | NOT STARTED |
| 12. First research-critical task implemented + tested | NOT STARTED |

**Section 17 guardrail:** spec and plan substantially done within the first two sessions; implementation starts **no later than session 3**.

---

## 4. Done / In progress / Blocked / Remaining

### Done (Session 1)
- Environment verified end-to-end: filesystem, Bash, PowerShell, git, Python 3.13.3, torch 2.12.0+cpu, pytest. Build → test → measure is available.
- Found and documented the **Microsoft Store `python` stub hazard**; all invocations use the venv interpreter.
- Project-local venv created reusing system torch without reinstall.
- `git init` (local, repo-scoped config).
- `.gitignore` written.
- ECC plugin inventoried by direct file reading → `TOOLING_INVENTORY.md`, including **four name-traps** and **one operational hazard**.
- `WebSearch`/`WebFetch` verified working against live 2024–2026 sources.

### In progress
- 10-dimension literature survey + 5 adversarial tension lenses (background workflow `wf_02be199f-5a0`).

### Blocked
- Nothing.

### Remaining (immediate)
See Section 8.

---

## 5. Known bugs

None — no implementation exists yet.

---

## 6. Security / research / experiment status — SUPERSEDED (threat + trust models now in PROJECT_MASTER_SPEC.md §4-5)

| Track | Status |
|---|---|
| Threat model | NOT STARTED — depends on `RD-001` |
| Trust model | NOT STARTED |
| Crypto choices | NOT STARTED — must be a logged decision (Section 24) |
| Experiments | NOT STARTED |
| Attack roster | NOT STARTED |
| Reproducibility harness | NOT STARTED |

**Standing honesty note:** nothing in this project is `IMPLEMENTED` until code exists, tests exist, and tests have actually run.

---

## 7. Research signal and incident log

### 7.1 INCIDENT — survey workflow lost to usage limit (Session 1)

The first literature-survey workflow (`wf_02be199f-5a0`, 15 agents) was **terminated by a usage limit at the return step**. Recorded honestly:

| Metric | Value |
|---|---|
| Agents completed | **0 of 15** |
| Subagent tokens spent | 930,680 |
| Tool uses performed | 364 |
| Structured findings returned | **none** — result was `{"surveys":[],"tensions":[]}` |

**Salvage:** the agents had already performed the research before dying. Their on-disk transcripts were parsed locally, recovering **202 searches and ~1,700 source references** into `research/_salvage/CORPUS-*.md` (841 KB, 10 dimensions). **Their synthesis was NOT recoverable** (each had written only 103–443 characters of free text before the failed structured-output call). The 5 tension-lens agents are worthless — they had received the empty corpus.

**Corrective actions taken:**
1. Re-analysis runs against the **local** corpus (no web calls) — far cheaper than re-searching.
2. Every analysis agent now **writes its output to disk before returning**, so a termination cannot destroy the work again.
3. Phases are run as **separate workflows** with a human-in-the-loop read between them, rather than one long chain.

### 7.2 Hypothesis killed early — `H-A` (recorded so it is not re-proposed)

**`H-A` (rejected): "Cross-round / temporal anomaly detection under secure aggregation is an open gap."**

Killed by direct source evidence:

| Prior work | Why it kills `H-A` | Evidence |
|---|---|---|
| **FedGT** — Xhemrishi, Östman, Wachter-Zeh, Graell i Amat, IEEE TIFS 2025 (arXiv 2305.05506) | Identifies malicious clients **under secure aggregation** via overlapping-group testing + decoding. Group size 1 = vanilla FL, group size N = full SecAgg, so it is an explicit tunable privacy/security knob. | primary-literature |
| **Detect & Score** — Xhemrishi, Graell i Amat, Pejó, arXiv 2506.23583 (2025) | Combines FedGT (misbehaviour detection) with QI (contribution evaluation) under SecAgg; QI is **multi-round**. | primary-literature |
| **ClusterGuard** — IACR ePrint 2024/2082 | Secure clustered aggregation maintaining a **historical frequency table across rounds** to track clusters flagged malicious. | secondary-literature — **needs primary check** |
| **CustodianFL** — arXiv 2310.04055 | Performs explicit lightweight **cross-round** detection (cosine similarity vs reference models). | primary-literature |

**Constraint discovered — binding on every future framing:** Allouah, Guerraoui et al., **ICML 2023**, "On the Privacy-Robustness-Utility Trilemma in Distributed Learning" (arXiv 2302.04787) proves a **fundamental impossibility**: no algorithm simultaneously achieves strong privacy, robustness, and utility. **BC-FL-SRV must never claim to resolve this tension.** Any framing that does is indefensible.

**Important technical caveat to carry forward:** the trilemma is proved for **differential privacy**, not for secure-aggregation privacy. SecAgg hides *individual* updates from the server while revealing the *sum* — a different and weaker notion than DP. The impossibility therefore does **not** transfer directly to a SecAgg-only setting. This distinction must be stated precisely in the spec; conflating the two would be a serious error.

### 7.3 Standing signal

"SecAgg + Byzantine robustness" as a bare combination is **saturated** (BREA-lineage, PriRoAgg, LoByITFL, Giskard, ByzFL, FedGT). It will not survive as a novelty claim and is not being pursued as one.

---

## 8. Immediate and next tasks

**Immediate:** consume the survey output; build the prior-art kill matrix.

**Next:**
1. Generate ≥3 candidate framings, each with contribution + falsifiable hypothesis + the experiment that could falsify it.
2. Adversarially kill-check each against prior art; discard `NOT NOVEL` and computationally untestable candidates.
3. Write the Research Gap Statement for survivors.
4. Lock `RD-001` in `DECISIONS.md` with rejected alternatives and rationale.
5. Contribution Boundary Analysis (Section 5).
6. SecAgg ↔ robustness stance as a logged decision (Section 15) — **before** any aggregation code.
7. Scope classification lock (Section 6) — **hard gate before the spec**.
8. Architecture + adversarial self-review, then revise.
9. `PROJECT_MASTER_SPEC.md` → `IMPLEMENTATION_PLAN.md` → cross-check.
10. Repo structure, then first dependency-ready research-critical task with tests.

---

## 9. Tech debt

None yet. Watch items:
- `torchvision` is absent. If the dataset decision needs it, either install it project-local or hand-roll the loader. **Not yet decided — depends on the dataset decision.**
- Paywalled venues (IEEE Xplore / ACM DL) are unreachable from here. Every citation destined for the written artifact carries a **primary-source re-check** flag for the human.

---

## 10. Test results

No test suite exists yet. `pytest 9.1.1` is installed and available in the project venv.

---

## 11. Decisions log pointer

See `DECISIONS.md`. No decisions are locked yet — `RD-001` is pending the survey.

---

# SESSION 1 CLOSE-OUT — 2026-09-03

## Phase status (supersedes Section 3 above)

| Phase | Status |
|---|---|
| 0. Environment + tooling inventory | **DONE** |
| 1. Literature survey | **DONE** (via salvage; 6 of 10 dimension *analyses* incomplete — raw corpora on disk) |
| 2. Candidate framings + kill matrix | **DONE** — 6 candidates, 5 killed |
| 3. Research Gap Statement | **DONE** |
| 4. `RD-001` lock | **DONE** |
| 5. Contribution Boundary Analysis (`D-004`) | **DONE** |
| 6. SecAgg <-> robustness stance (`D-003`) | **DONE** |
| 7. Scope classification lock (`D-005`) | **DONE** |
| 8. Architecture + adversarial review | **DONE** (v0.1 in spec; review continues each session) |
| 9. `PROJECT_MASTER_SPEC.md` | **DONE** v0.1 |
| 10. `IMPLEMENTATION_PLAN.md` | **DONE** |
| 11. Repo structure | **DONE** |
| 12. First research-critical task implemented + tested | **DONE — T-A1** |

**Section 17 guardrail met early:** implementation began in session 1, not session 3.

## Test results — actually executed

```
pytest tests/ --cov=bcflsrv.ledger.merkle
124 passed
src/bcflsrv/ledger/merkle.py   101 stmts   0 missed   100% coverage
```

## Measurements taken

| Measurement | Result | Status |
|---|---|---|
| Inclusion-proof verification vs payload size | ~4.5 us, flat from 1 KB to 1 MB (1024x) | **smoke test**, first NFR-1 evidence — NOT the full E-1 experiment |
| Inclusion proof size | <= ceil(log2 n) nodes, asserted for n = 1..32 | test-enforced |

## Component status — honest labels

| ID | Component | Status |
|---|---|---|
| RC-1 / T-A1 | RFC 6962 Merkle primitives | **IMPLEMENTED** — code exists, tests exist, tests ran, 100% coverage |
| RC-2..RC-9 | committee, evidence, rule, attestation, auditor, SecAgg, attacks, measurement | `PROPOSED` |
| RS-1..RS-7 | identity, binding, FL loop, partitioner, seeding, config, logging | `PROPOSED` |

## Tech debt

1. **RFC 6962 conformance is VERIFIED-BY-DEFINITION, not VERIFIED-BY-INTEROP.** No cross-check against an independent implementation yet. Tracked as T-A2.
2. `torchvision` absent — dataset loading decision pending (`D-008`).
3. Six literature dimensions have raw corpora but no structured analysis (agents died). Re-analysable locally without new web searches.
4. Paywalled venues unreachable; primary-source re-check list is in `DECISIONS.md` / `SESSION_HANDOVER.md`.

## Known bugs

None. No failing tests.

## Immediate next task

**T-A3** — `Transcript` object with typed entries and prev-root chaining. Then T-B1 (Ed25519), then T-A2 (interop cross-check). Log `D-006` and `D-008` before writing the code they govern.
