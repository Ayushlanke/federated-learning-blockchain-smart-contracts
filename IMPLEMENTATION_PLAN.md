# IMPLEMENTATION_PLAN.md — BC-FL-SRV

**Serves:** `PROJECT_MASTER_SPEC.md`, which serves `RD-001`.
**Ordering rule:** dependency-aware. A task is startable only when its dependencies are `DONE`.
**Definition of done (Section 18):** implementation exists AND tests exist AND tests pass AND security checks ran AND failure handling exists AND docs updated AND acceptance criteria met.

---

## Status legend
`DONE` · `IN PROGRESS` · `READY` (deps met) · `BLOCKED` · `PROPOSED`

---

## Phase A — Transcript foundation (research-critical: AG3)

### T-A1 — RFC 6962 Merkle primitives — **DONE**
- **Purpose:** FR-1, FR-2, FR-3. The append-only transcript on which AG3 is defined.
- **Dependencies:** none (root of the graph).
- **Files:** `src/bcflsrv/ledger/merkle.py`, `tests/test_merkle.py`
- **Security requirements:** RFC 6962 domain separation (0x00 leaf / 0x01 node); every malformed or truncated proof must return False, never raise, never accept.
- **Tests:** 124 passing, **100% line coverage**. Adversarial cases: in-place edit, deletion, reorder, tampered proof node, truncated proof at every prefix, padded proof, wrong index, wrong root, shrinking tree.
- **Acceptance criteria:** MET.
- **Measured:** inclusion-proof verification ~4.5 us, flat across payloads 1 KB -> 1 MB (first NFR-1 evidence).
- **Known gap:** conformance is VERIFIED-BY-DEFINITION, not VERIFIED-BY-INTEROP. See T-A2.

### T-A2 — RFC 6962 interop cross-check — **READY**
- **Purpose:** remove the one honest caveat on T-A1 by checking roots against an independent implementation or published CT vectors.
- **Dependencies:** T-A1.
- **Acceptance:** at least one externally-sourced (root, tree) pair reproduces exactly, or the gap is documented as unresolved with the reason.

### T-A3 — `Transcript` object: typed entries, chaining, persistence — **DONE**
- **Purpose:** FR-1, FR-4. Entry kinds SUBMIT / ADMIT / AGGREGATE / FINALIZE; each entry binds the previous root; canonical length-prefixed encoding with per-kind domain separation.
- **Dependencies:** T-A1.
- **Security requirements:** canonical encoding must be injective (no two distinct entries share bytes); cross-kind confusion must be impossible.
- **Tests:** round-trip encode/decode; chaining breaks on any historical edit; distinct kinds never collide; append is monotonic.

---

## Phase B — Identity and binding (required-supporting)

### T-B1 — Ed25519 identity and signing — **DONE**
- **Purpose:** RS-1. Client and committee keypairs via the `cryptography` library. **No custom crypto** (Section 15).
- **Dependencies:** none.
- **Security:** key lifecycle documented; signature verification failure is a hard reject; no key material logged.

### T-B2 — Round-context binding — **BLOCKED** on T-A3, T-B1
- **Purpose:** FR-4, T-6. Bind `(client_id, round, prev_root, evidence_digest, masked_digest)`.
- **Acceptance:** a submission replayed into another round is deterministically rejected — asserted by test.

---

## Phase C — Committee and admission (research-critical: AG1)

### T-C1 — Verifiable sortition — **DONE**
- **Purpose:** FR-5, RC-2. Committee for round `t` derived from the root at `t-1`.
- **Acceptance:** any party recomputes the same committee from the transcript; altering history alters the committee.
- **Also delivers:** the hypergeometric corruption-probability model used by E-3.

### T-C2 — Bounded evidence encoding — **BLOCKED** on T-B2
- **Purpose:** RC-3, `D-003`. **The tunable disclosure knob — this is the experiment's independent variable.**
- **Note:** encoding choice is `D-006` and must be logged before implementation.

### T-C3 — Admission rule over bounded evidence — **BLOCKED** on T-C2
- **Purpose:** RC-4. A declared, deterministic rule; `rule_id` recorded in the transcript.

### T-C4 — Threshold attestation of the admission set — **BLOCKED** on T-C1, T-C3, T-B1
- **Purpose:** FR-6, RC-5. Below-threshold attestation must be rejected.

---

## Phase D — Aggregation and audit

### T-D1 — Masked-input secure aggregation — **BLOCKED** on T-B1
- **Purpose:** FR-8, RC-7. Aggregator learns only the sum.
- **Acceptance:** test asserts no plaintext individual update is reachable aggregator-side.

### T-D2 — External auditor — **BLOCKED** on T-A3, T-C4
- **Purpose:** FR-7, RC-6. Verifies AG1 and AG3 from the transcript alone.
- **Acceptance:** accepts honest runs; rejects every attack in Phase F.
- **Design requirement:** address T-7 — an inclusion query must not trivially disclose participation.

---

## Phase E — FL substrate (required-supporting)

### T-E1 — FL loop, model, non-IID partitioner, seeding, config, logging — **READY**
- **Purpose:** RS-3..RS-7. Deliberately boring; carries no research content.
- **Note:** dataset/model choice is `D-008`, to be logged before implementation. CPU-only sizing.

---

## Phase F — Adversarial evaluation (research-critical: RC-8)

### T-F1..T-F5 — **BLOCKED** on Phase D
Attacks on the **accountability layer**: T-1 selective dropping · T-2 split-view/equivocation · T-3 committee collusion · T-4 sortition grinding · T-5 slow-drift admission evasion.
Plus the standard model-layer roster (label-flipping and sign-flipping first, per Section 19) as context.

---

## Phase G — Measurement, ablation, reproducibility

### T-G1 — Cost measurement vs N and K (E-1) — **READY** after T-A3
### T-G2 — Ablation runner (E-7) and baselines — **BLOCKED** on Phase D
### T-G3 — Auditors-absent condition (E-6, IE-4) — **BLOCKED** on T-D2
### T-G4 — Run manifests and reproducibility harness — **READY**

---

## Immediate next tasks (in order)

1. **T-A3** — `Transcript` object with typed entries and chaining.
2. **T-B1** — Ed25519 identity and signing.
3. **T-A2** — RFC 6962 interop cross-check (closes the T-A1 caveat).
4. **D-006 / D-008** — log the evidence-encoding and dataset decisions *before* writing that code.
5. **T-C1** — verifiable sortition + corruption-probability model.
