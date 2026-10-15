# SESSION_HANDOVER.md — BC-FL-SRV

Written so a fresh session with **zero conversation memory** can continue.
**Startup procedure:** read the control files in Section 22 order, then inspect the actual repo. Never rely on conversation memory.

---

## Session 1 — 2026-09-03 — canary `KING`

### What this project is (one sentence)

BC-FL-SRV is a federated-learning system whose per-round **admission decisions** are attested by a rotating committee and anchored in an append-only Merkle transcript, so an external auditor can verify *which clients were admitted and that the declared rule was applied* — without the aggregator ever seeing individual updates.

### Accomplishments

1. **Environment verified end-to-end.** Filesystem, Bash, PowerShell, git, Python 3.13.3, torch 2.12.0+cpu, pytest. Build -> test -> measure is available.
2. **Locality constraint honoured** (user instruction): everything lives in `C:\Study`. Project venv reuses base torch via `--system-site-packages`; nothing installed globally; git config repo-scoped.
3. **ECC plugin inventoried by direct file reading** -> `TOOLING_INVENTORY.md`. Found **four name-traps** and **one operational hazard**.
4. **Two multi-agent runs were killed by usage limits.** Research was salvaged from disk: 202 searches, ~1,700 references, and **13 full PDFs** now text-extracted in `research/papers/`.
5. **`RD-001` LOCKED** — six candidate framings, five killed on evidence.
6. **`D-003` (SecAgg<->robustness stance), `D-004` (contribution boundary), `D-005` (scope) LOCKED.**
7. **`PROJECT_MASTER_SPEC.md` and `IMPLEMENTATION_PLAN.md` written.**
8. **T-A1 IMPLEMENTED, TESTED, MEASURED** — RFC 6962 Merkle primitives, 100% line coverage.

### Discoveries that shaped the design

- **The anchor paper** (read as a full primary source, not a summary): Rizzini et al., *SoK: Verifiable Integrity Claims for Privacy-Preserving Federated Learning*, **PoPETs 2026(4):248-271**. It models FL as an append-only transcript and defines integrity claims AG1 (correct admission), AG2 (correct aggregation), AG3 (non-equivocation).
- **The gap, in the SoK's own numbers:** AG2 adoption 10/13; **AG1 = 2/13, AG3 = 3/13** — despite AG1/AG3 being the *cheapest* claims to build (O(K), O(1); ease 4.5/5 and 5/5). The SoK covers only ZKP and TEE instantiations; the word *committee* appears **twice** in the whole paper.
- **A hypothesis was killed early:** "cross-round detection under SecAgg" is NOT open — FedGT (IEEE TIFS 2025), Detect & Score (2025), ClusterGuard, CustodianFL all occupy it.
- **A hard impossibility bounds all claims:** the privacy-robustness-utility trilemma (Allouah et al., ICML 2023). BC-FL-SRV must never claim to resolve the tension. NOTE: it is proved for *differential privacy*, not SecAgg privacy — do not conflate them.
- **Cautionary datum:** Certificate Transparency's gossip layer — the load-bearing part of its security argument — was never widely deployed. So BC-FL-SRV must not build a security argument that reduces to "someone will check"; the auditors-absent condition is an explicit experiment (E-6/IE-4).
- **An unanticipated design tension** (from PETS 2022 SCT-auditing work): asking "was my update admitted in round t?" is itself a participation disclosure. Recorded as threat T-7.

### Files touched

Created: `TOOLING_INVENTORY.md`, `PROJECT_PROGRESS.md`, `DECISIONS.md`, `PROJECT_MASTER_SPEC.md`, `IMPLEMENTATION_PLAN.md`, `SESSION_HANDOVER.md`, `.gitignore`, `pytest.ini`, `requirements.txt`, `src/bcflsrv/ledger/merkle.py`, `tests/test_merkle.py`, `research/_salvage/*` (10 corpora + 3 analyses + 1 JSON), `research/papers/*` (13 extracted papers).

### Test results — actually run, not asserted

`pytest tests/ --cov=bcflsrv.ledger.merkle` -> **all passing, 100% line coverage** on `merkle.py` (101 statements, 0 missed).
Adversarial cases covered: in-place edit, deletion, reorder, tampered proof node, truncated proof at every prefix, padded proof, wrong index, wrong root, shrinking tree, out-of-range, empty tree.

**Measured (smoke, not the full E-1 experiment):** inclusion-proof verification ~4.5 us, flat across payloads 1 KB -> 1 MB. First evidence toward NFR-1.

### Security findings

- `ecc:security-reviewer` and other ECC agents carry a prompt-defense baseline forbidding "exploit / attack content". BC-FL-SRV must implement legitimate FL poisoning simulations. **Do not route attack-simulation code through ECC's guarded reviewers**; review it directly.
- Verifier robustness treated as a security property: a truncated/padded proof must return False, never raise (a crash in an auditor is a DoS on audit) and never accept. Tested at every truncation prefix.

### Blockers

None.

### Unresolved questions (carry forward)

1. **`D-006`** — which bounded evidence encoding? (commitments + structural predicates / FedGT-style group aggregates / masked pairwise statistics). Must be logged **before** T-C2.
2. **`D-008`** — dataset, model, non-IID split, client count, sized to 12 CPU cores. Note `torchvision` is **absent**; either install project-local or hand-roll the loader.
3. **`D-007`** — auditor/gossip model and the no-gossip fallback.
4. **Primary-source re-check** (the human must do this — paywalls block this environment; ACM DL returned HTTP 403): FedGT full text, Detect & Score, ClusterGuard, and the SoK refs [2, 20, 47, 66, 98]. **The "AG1 = 2/13" figure is the load-bearing novelty number and must be independently confirmed.**
5. The 6 literature dimensions whose analysis agents died (crux, slowdrift, secagg, committee, bcfl, zk) — raw corpora are on disk in `research/_salvage/CORPUS-*.md` and can be re-analysed cheaply without new web searches.

### Exact next tasks

1. **T-A3** — `Transcript` object: typed entries (SUBMIT/ADMIT/AGGREGATE/FINALIZE), prev-root chaining, canonical injective encoding with per-kind domain separation. Depends on T-A1 (done).
2. **T-B1** — Ed25519 identity/signing via `cryptography`. No custom crypto.
3. **T-A2** — RFC 6962 interop cross-check, to close the one honest caveat on T-A1.
4. **Log `D-006` and `D-008`** before writing the code they govern (Section 24 requires investigate -> log -> spec -> implement).
5. **T-C1** — verifiable sortition from the prior root + hypergeometric corruption-probability model.
6. **T-B2** — round-context binding and replay rejection.

### Critical context a fresh session must not lose

- **The ledger is load-bearing, not decorative.** AG3 is *defined* by the append-only transcript. That is the answer to "why blockchain?" and it is the reason this project satisfies the immutable goal.
- **Falsification path 4 is a live risk and is stated on purpose:** if a slow-drift attacker passes the admission rule indistinguishably from honest clients, verifiable admission is verifiably useless. That would be a real, publishable negative result — do not quietly design around it.
- **Never claim the ledger "guarantees" anything.** It provides tamper-evidence under a stated auditing assumption. Section 13 discipline.
- **Environment trap:** bare `python` is a Microsoft Store stub that fails. Always use `C:\Study\.venv\Scripts\python.exe`.
- **Workflow trap:** large max-effort agent fan-outs get killed by usage limits at the return step. Keep runs small, and always have agents write to disk before returning.
