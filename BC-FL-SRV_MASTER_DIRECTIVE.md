# BC-FL-SRV — PROJECT MASTER DIRECTIVE (v4, self-directed)

## 0. What this is and where it runs

This is the first message of a from-scratch research + build project. **There is no blueprint and there will not be one.** You are responsible for producing everything a blueprint would have contained — problem statement, architecture, mechanisms, threat model, experiments — and for defending every choice with evidence.

This directive assumes an agentic environment with a real file system, bash, and test execution (Claude Code or equivalent). If you are running in plain chat with no code execution, say so in your first response: research → spec → plan still works; build → test → measure does not.

Fill in Section 1 if you want to; leave it blank if you don't. Blank fields are not a reason to stall — Section 1 has defaults, and you are expected to choose sensibly and record what you chose.

---

## 1. Project parameters

| Parameter | Your answer | Default if blank |
|---|---|---|
| Deadline(s) | | assume ~10–12 working sessions; front-load research-critical work |
| Team | | solo |
| Target outcome | | degree submission + a workshop-paper-shaped artifact |
| Compute available | | single laptop, CPU-only |
| Blockchain requirement | | local append-only Merkle-hash-chained ledger; no real testnet |
| Dataset domain | | a standard FL benchmark with non-IID splits (FEMNIST or CIFAR-10 Dirichlet); never collect new data |
| Advisor / evaluator constraints | | none fixed |
| ECC plugin capabilities you already know of | | none stated — inventory it yourself per Section 4 |

Record the effective values (yours or defaults) in `PROJECT_PROGRESS.md` in your first session. Do not ask about them again later; if a default turns out to be wrong, log the change as a decision.

---

## 2. Goal lock — immutable

**Fixed. Not open to redesign, reinterpretation, narrowing into something else, or "improvement":**

- **Project identity:** BC-FL-SRV.
- **Domain:** federated learning, combined with distributed-ledger anchoring, combined with secure and robust verification of client contributions. All three. Not FL alone, not a ledger project with FL bolted on, not a pure-crypto project.
- **Deliverable class:** a real, running, tested research system — plus the research artifacts around it (spec, prior-art position, experiments, measurements, honest limitations). Not a survey, not a design document, not a prototype-shaped demo.
- **Scientific form:** the system must directly test a falsifiable hypothesis about that combination.
- **Every rule in this directive**, including the honesty rule (Section 23) and the control-file precedence (Section 22).

**Open — and you are expected to decide these yourself, with evidence, not to ask:**

- The precise research question and hypothesis.
- Which mechanism, combination, interaction, resilience property, or evaluation methodology is the claimed contribution.
- The architecture, protocol, mechanism set, cryptographic choices, and ledger form.
- The SecAgg ↔ Byzantine-robustness stance (Section 15).
- Dataset, model, baselines, attack roster, metrics.
- Stack, repo layout, testing and benchmarking strategy.
- What gets cut, and what gets shrunk instead of cut.

**Anti-drift check.** At the start of every session, and before locking any decision, restate the fixed goal in one sentence and confirm the current plan still tests it. A redesign that leaves the system no longer a ledger-anchored FL system with secure/robust verification is out of bounds — find a different redesign.

**Escape valve, deliberately narrow.** If evidence genuinely indicates the fixed goal is unachievable or indefensible as stated, do **not** silently pivot and do not quietly reshape the project into an adjacent one. Write a `GOAL-CHALLENGE` entry in `DECISIONS.md` — evidence, what specifically fails, what the alternatives would be — and stop for a human decision. Goal changes are the one thing you never make autonomously.

---

## 3. Self-authored research definition — do this before designing anything

You are inventing the project. The failure mode that matters most is therefore a **plausible-sounding but hollow project**: a well-written spec for a system whose contribution dissolves the moment someone checks the literature. Guard against it by working in this order, not by writing a problem statement first and justifying it later.

1. **Literature first.** Survey before you design (Section 11). You do not get to know what the gap is yet.
2. **Draft at least three candidate framings.** Each one: candidate contribution, falsifiable hypothesis, and the specific experiment that could show it false.
3. **Prior-art comparison per candidate.** Kill any candidate that is NOT NOVEL, or that no experiment available in your compute budget could demonstrate.
4. **Write the Research Gap Statement** (Section 11) for the survivor(s).
5. **Pick one.** Lock it in `DECISIONS.md` as `RD-001`: chosen framing, the framings you rejected, why, and the falsifiable claim in one sentence.
6. **Everything downstream serves `RD-001`** — spec, scope, plan, experiments.

**Traceability guard.** A self-authored problem statement is legitimate only if it traces both backward to cited literature and forward to a feasible experiment. A framing you cannot trace both ways is `INFERRED` — label it and discard it. Never present a self-invented framing as though it came from external requirements, an advisor, or a source you didn't read.

**A caution to check against the literature, not to assume.** Committee-based, blockchain-audited Byzantine-robust aggregation is heavily precedented, going back to 2020. If that combination alone ends up as your whole claim, the gap statement isn't done. Two directions that have historically been sharper and are worth checking specifically:

- Robust aggregation that remains **privacy-preserving** (SecAgg-compatible) *and* ledger-auditable — most committee-blockchain-FL systems verify by direct inspection of plaintext updates, which sidesteps the hard part.
- Evaluation under **adaptive, slow-drift, or colluding-committee** conditions specifically — still less common than static-attack evaluation, though not untouched.

Check both. Neither is a free pass.

---

## 4. ECC plugin — installed, advisory, subordinate

An ECC plugin is installed in this environment. Treat it as a reviewable resource, not an authority.

**Inventory it, don't guess at it.** In your first session: read its manifest / README / exposed skills / commands / tools and write what it *actually* exposes into `TOOLING_INVENTORY.md` — capability, what it takes, what it returns, tagged `VERIFIED` only for what you read directly. Anything you can't confirm is `UNKNOWN`. Do not infer features from the plugin's name, and do not describe capabilities you haven't seen. If the plugin isn't actually present or loadable, say so plainly and continue without it.

**Use it where it serves `RD-001`** — reviewing cryptographic and protocol choices, sanity-checking primitive selection and parameters, code-review passes on security-sensitive modules, whatever the inventory shows it's actually good for.

**Don't overuse it.** Consult at checkpoints, not per task and not per file: before locking crypto decisions, before locking the security model, at security-review gates, and after any major architecture change. If two consecutive consults produce nothing that changes a decision, stop consulting until something material changes. Volume of plugin calls is not evidence of rigor.

**Precedence — this matters.** This directive and the five control files (Section 22) outrank the plugin absolutely. The plugin never edits, overwrites, reframes, or supersedes this directive, the fixed goal, `PROJECT_MASTER_SPEC.md`, or `DECISIONS.md`. If plugin output conflicts with any of them, the plugin loses, and you log the conflict.

**Ownership and verification.** Plugin output is `REQUIRES VALIDATION` by default. Any recommendation you adopt becomes *your* decision: log it in `DECISIONS.md` with your own reasoning, marked as plugin-sourced, and verify its factual claims independently before relying on them. Never cite the plugin as authority for a security or novelty claim.

**Don't let it shape scope.** If the plugin makes some capability cheap, that is not a reason to move that capability into research-critical scope. Same rule as Section 6: nothing gets promoted because it's convenient or sounds impressive.

---

## 5. Contribution boundary analysis — required before any scope decision

Before assigning necessity or tiers to anything, separate these in writing, as part of the spec's Research Definition:

- **Research hypothesis** — the specific falsifiable claim being tested.
- **Scientific contribution** — what is actually claimed as new: a mechanism, a combination, a protocol interaction, a threat-resilience property, an evaluation methodology, or a systems result. Name which one. Exactly one primary.
- **System mechanisms** — components that implement the contribution.
- **Security mechanisms** — components that protect the system but are not themselves the contribution.
- **Infrastructure** — needed to run the above, no research content of its own.
- **Evaluation infrastructure** — needed to measure the contribution.
- **Optional extensions** — everything else.

Blockchain, ZK, SecAgg, and committee verification are each individually candidates for any of the first three categories. `RD-001` plus a real prior-art check decides which — not assumption, not convenience. Lock this once the gap statement is done, and don't leave it open past that point.

---

## 6. Scope classification — necessity-driven, not cost-driven

Classify every component by **necessity to the hypothesis and contribution**, not by build cost:

- **Research-critical** — the system doesn't test the hypothesis without it. Must exist and be measured.
- **Required-supporting** — not the contribution, but the contribution isn't credible or secure without it.
- **Important-evaluation** — needed to show the contribution held up under adversarial conditions.
- **Optional-enhancement** — improves the system; hypothesis is testable without it.
- **Future work** — document, don't build.

**Rule for cuts:** necessity decides what's cut; feasibility decides how much of what's kept gets fully built. If a research-critical component can't be fully implemented in the time available, don't drop it quietly and don't fake it — **shrink the experimental claim** instead (fewer clients, smaller model, narrower attacker set, reduced parameter regime) and state that as an explicit limitation. Never demote something out of research-critical because it's hard. Never promote something into research-critical because it's impressive, or because the ECC plugin makes it easy. Both directions are scope-integrity failures.

**Hard gate:** this classification is locked, with rationale in `DECISIONS.md`, before `PROJECT_MASTER_SPEC.md` is written.

---

## 7. Canary / instruction-integrity signal

Start every chat response (not every intermediate tool call) with `# KING`. If a response is ever produced without it, say so explicitly — `CANARY FAILURE — KING MISSING` — treat it as a signal that context or instructions may have degraded, and re-ground by re-reading the five control files (Section 22) plus inspecting actual repo state. Never fabricate continuity across a canary failure.

Use this vocabulary whenever confidence matters: **VERIFIED, OBSERVED, IMPLEMENTED, PROPOSED, INFERRED, UNKNOWN, REQUIRES VALIDATION.**

---

## 8. Role

Simultaneously: principal researcher, systems architect, senior engineer, security/crypto engineer, FL/ML engineer, blockchain engineer, QA, performance engineer, DevOps, technical PM, documentation architect, research-paper strategist. One operator, many hats — reconcile contradictions between them rather than letting one hat silently override another.

Operating loop, repeated: UNDERSTAND → RESEARCH → CHALLENGE → DESIGN → SPECIFY → PLAN → IMPLEMENT → TEST → MEASURE → ATTACK → SECURITY REVIEW → RESEARCH REVIEW → IMPROVE → DOCUMENT → HANDOVER → REPEAT.

---

## 9. Starting condition

Repo starts at zero: no implementation, stack, DB, security architecture, test suite, benchmarks, or methodology. There is no prior material to inherit and nothing to defer to. Never claim something exists unless you can inspect it in the repo.

---

## 10. Design revision discipline

Since you are authoring the design, "the design said so" is never a reason to keep anything. Your own earlier choices get the same scrutiny you'd apply to someone else's.

Reject or redesign any mechanism — including one you designed last session — when analysis shows it is: already solved by prior work · technically incorrect · cryptographically unsound · based on unrealistic assumptions · redundant · insecure · experimentally untestable · unnecessarily complex · incompatible with another required mechanism · or inferior to something found during research. When that happens: explain the conflict, log the decision and rationale in `DECISIONS.md`, and redesign.

The inverse also binds: don't churn. Never silently reverse a logged decision. Reversal requires a new `DECISIONS.md` entry citing what new evidence changed, and it must not be a rewrite of `RD-001`'s scientific claim unless the gap analysis genuinely failed — in which case that's a `GOAL-CHALLENGE`, not a routine revision.

---

## 11. Research process

Sources: peer-reviewed venues (USENIX Security, IEEE S&P, CCS, NDSS on security; NeurIPS/ICML/ICLR on FL), arXiv, IACR ePrint, official docs and RFCs, CVE databases, existing open-source implementations and benchmark suites. Search for *different approaches to the same underlying problem*, not just systems with the same name.

**Research Gap Statement — required, and separate from the novelty classification.** Before locking any architecture, answer explicitly: what exactly is missing in the existing literature, and why does BC-FL-SRV's specific mechanism or combination address it? A list of combined technologies never satisfies this. "We combined FL + blockchain + ZK + SecAgg" is a description, not a gap. Identify: closest prior systems, what each already solves, what none of them solve, conflicting requirements between them, and what experiment would show BC-FL-SRV closes the gap.

Tag every important claim — novelty, security, performance: directly verified / primary literature / secondary literature / inferred / unverified. Prioritize recent work. Never manufacture confidence.

**Verification caveat for the human.** Web search misses paywalled venues and occasionally misattributes claims. Anything going into a submitted paper, or staked on the degree evaluation, gets re-checked at the primary source (IEEE Xplore / ACM DL / IACR ePrint / Scholar) before it's relied on. Flag which claims need that re-check.

Never write "this has never been done before." Use: potentially novel / appears underexplored / existing work doesn't appear to address X / novel in this specific combination or evaluation / requires further validation. Per claimed contribution: state the claim → find the closest prior art (papers *and* implementations) → compare explicitly → classify NOT NOVEL / INCREMENTAL / POTENTIALLY NOVEL / REQUIRES FURTHER VALIDATION → design an experiment that could actually demonstrate it.

---

## 12. Adversarial self-review

Before locking any design, ask: why does this need to exist / what's already solved / what's genuinely different / which assumption is unrealistic / what's unnecessary or missing / which claim is too strong / what baseline would defeat this contribution / what would invalidate the hypothesis / what breaks under adaptive attackers, collusion, non-IID data, client churn, slow-drift attacks, a malicious coordinator, colluding committee members, key compromise, infra failure, or scale?

Then actually revise the design. This step doesn't count unless something changed. If nothing changed, say what you re-examined and why it held — don't just assert that review happened.

---

## 13. Trust model — explicit, not aspirational

For every actor: what it can see / modify / prove / cannot prove / is trusted for / is explicitly **not** trusted for.

Never write "the blockchain guarantees security." Specify exactly which property it provides and which it doesn't. Same discipline for SecAgg, DP, ZK, signatures, committee consensus, reputation/staking, content-addressed storage, TLS/mTLS. This mechanism-vs-guarantee distinction is the single most important discipline in the whole spec.

---

## 14. Security architecture

Threat-model explicitly: malicious/compromised/lazy clients, Sybils, replay, equivocation, poisoning, backdoors (adaptive and slow-drift included), collusion, malicious coordinator/aggregator/committee members, committee-selection manipulation, key compromise, network and storage attacks, DoS, resource exhaustion, implementation bugs, crypto misuse, dependency and supply-chain issues.

Per threat: preconditions, affected component, impact, mitigation, detection, recovery, residual risk, test method. Never claim a mechanism eliminates a threat it only reduces.

---

## 15. Cryptography & stack — don't invent, pick mature tools

Design no new cryptography. For every crypto mechanism: primitive, construction, security assumption, parameter choice, library, key lifecycle, serialization, validation, failure behavior. Label anything experimental as experimental.

**The SecAgg ↔ Byzantine-robustness stance is a required early architectural decision, not an add-on.** Standard secure aggregation hides individual updates from the server; standard robust-aggregation rules (Krum, trimmed mean, distance-based outlier detection) need visibility into individual updates to reject outliers. These pull in opposite directions, and it gets harder in a decentralized/committee setting. Before designing the aggregation layer, survey the existing partial solutions — secret-sharing approaches (BREA / ByzSecAgg-style, which recover distance-based detection but leak pairwise distances to the aggregator), ZK-based approaches (RoFL-style, which enforce norm bounds under encryption but don't give full outlier rejection), MPC-based approaches for decentralized settings — then either adopt/extend one with an explicit tradeoff statement, or justify a new combination with the same rigor. Log it in `DECISIONS.md` **before** the aggregation pipeline is built; retrofitting this later means rearchitecting, not bolting on.

Starting-point suggestions — swap if research says otherwise, and record why:

- **Signatures/commitments:** Ed25519 via a maintained library (Python `cryptography` / PyNaCl, or the equivalent in your language).
- **Ledger:** for research-critical and required-supporting scope, a local append-only Merkle-hash-chained log is enough to get integrity and auditability measured. Reach for a real chain (local Anvil/Hardhat, or a testnet) only if Section 1 requires it.
- **FL simulation:** an existing framework (Flower) or a custom asyncio/multiprocessing simulator — custom gives more control for injecting committee logic and attacks.
- **ZK:** circom + snarkjs, or arkworks in Rust — existing circuits and libraries, not custom protocol design.

For every major tech choice: chosen option, alternatives considered, reason, tradeoffs, and security/performance/research implications. Don't pick for popularity, and don't pick because a plugin supports it.

---

## 16. Single source of truth

Once research and design are far enough along, create **`PROJECT_MASTER_SPEC.md`**. Minimum contents: project identity · research definition (question, hypothesis, contribution boundary from Section 5, Research Gap Statement, novelty position, prior-art comparison, assumptions, limitations, threats to validity) · goals and non-goals · scope by necessity classification (Section 6) · functional and non-functional requirements · full architecture (Mermaid where useful) · security model · data architecture · API and interface schemas · failure and reliability behavior · measurable performance targets · testing acceptance criteria · experimental program · reproducibility plan.

Every requirement must be implementable, not vague. Bad: "implement security." Good: "every client update commitment binds client identity, round ID, previous model hash, update format, and update digest; replay from a previous round is rejected by deterministic validation."

Every feature needs: ID, purpose, description, I/O, dependencies, security requirements, failure and edge cases, performance notes, tests, acceptance criteria, implementation status.

---

## 17. Implementation plan

After the spec, create **`IMPLEMENTATION_PLAN.md`** — a dependency-aware roadmap. Each task: ID, description, purpose, dependencies, files/components touched, security requirements, tests, acceptance criteria, deliverables, status, priority.

Rough ordering, adapt as the real architecture demands: repo foundation → dev environment → core domain models → communication layer → identity/auth → update lifecycle → aggregation (with the SecAgg↔robustness stance already decided) → verification → ledger → committee logic → attack simulation → observability → testing → benchmarking → experiments → hardening → reproducibility → deployment → research artifacts.

**Don't plan forever.** Once spec and plan cover research-critical plus required-supporting scope, start implementing. If something is uncertain but doesn't block the current task, document the uncertainty and proceed on the safest justified assumption. Hard guardrail: spec and plan substantially done within the first two sessions; implementation starts no later than session 3. Autonomy is not a license to keep researching indefinitely — a self-directed project fails most often by never shipping code.

---

## 18. Implementation & testing discipline

Per task: read the relevant spec section and plan task → inspect the current repo → implement → write tests → run tests → fix failures → security-check → run relevant benchmarks → update docs/progress/decisions → move to the next dependency-ready task.

**Definition of done:** implementation exists AND tests exist AND tests pass AND security checks ran AND failure handling exists AND docs are updated AND acceptance criteria are met.

---

## 19. Research experiments & adversarial evaluation

Design experiments around `RD-001`, with strong baselines. Never build an experiment whose purpose is making BC-FL-SRV look good.

Vary: client heterogeneity, malicious-client fraction, attack type, adaptive vs. non-adaptive attackers, collusion, committee behavior, non-IID splits, client churn.

Measure: latency, throughput, communication cost, CPU/memory/storage, ledger overhead, crypto/ZK overhead, model accuracy, attack success rate, false-positive rejection rate, utility, robustness.

Per defense claim, state explicitly: maximum coalition size tolerated, attacker knowledge assumed, visibility of individual updates, adaptation horizon. Don't leave these implicit.

Attack roster, scaled to the necessity classification — label-flipping and sign-flipping first: label-flipping, sign-flipping, Gaussian, model replacement, backdoors (including adaptive and stealth), colluding clients, free-riders, slow-drift, replay, equivocation, malicious aggregation, committee collusion and selection manipulation, dropout, communication disruption. The goal is finding where the system succeeds *and* fails, and why.

**Ablations:** measure each component's actual contribution. Never assume a component helps because it's there — especially components you designed yourself.

---

## 20. Reproducibility

Fixed and documented: environment, dependencies, dataset splits, config, experiment scripts, attack scripts, random seeds, metrics, generated results. No undocumented manual steps.

---

## 21. Continuous research & security review

Keep watching for newer papers, attacks, baselines, and vulnerabilities throughout implementation — findings during implementation can themselves become research findings. After any meaningful architecture change, re-check attack surface, trust assumptions, auth, key management, crypto usage, validation, logging, privacy, dependencies, and DoS exposure.

---

## 22. Project control files & precedence

- **`PROJECT_MASTER_SPEC.md`** — authoritative spec (Sec. 16)
- **`IMPLEMENTATION_PLAN.md`** — authoritative roadmap (Sec. 17)
- **`PROJECT_PROGRESS.md`** — phase, milestone, task, done/in-progress/blocked/remaining, known bugs, security/research/experiment status, tech debt, recent changes, test results, decisions, immediate and next tasks, effective Section 1 parameters, current canary
- **`SESSION_HANDOVER.md`** — written so a fresh session with zero conversation memory can continue: session #, date, KING, accomplishments, discoveries, files touched, architecture/implementation/research/experimental state, decisions, security findings, test results, blockers, unresolved questions, exact current and next 3–10 tasks, important files, critical context
- **`DECISIONS.md`** — per decision: ID, date, context, problem, alternatives, chosen approach, rationale, tradeoffs, security/performance/research implications, conditions for revisiting. Holds `RD-001`, the SecAgg↔robustness stance, the scope lock, and any `GOAL-CHALLENGE`.
- **`TOOLING_INVENTORY.md`** — verified capabilities of the ECC plugin and any other tooling (Sec. 4)

**Precedence when things conflict:** this directive's fixed goal and rules (Section 2) → actual code → `PROJECT_MASTER_SPEC.md` → `DECISIONS.md` → `IMPLEMENTATION_PLAN.md` → `PROJECT_PROGRESS.md` → `SESSION_HANDOVER.md` → ECC plugin output and any other advisory tooling (**advisory only; never overrides anything above it, and never edits the files above it**).

**Future-session startup:** read the control files in order, then inspect the actual repo. Never rely on conversation memory.

---

## 23. Scientific & engineering honesty — one rule, no exceptions

Never claim implemented / tested / secure / benchmarked / novel unless, respectively: the code exists / the test actually ran / you can say exactly what was tested and under which assumptions / you have real measurements / you have real prior-art evidence.

Never fabricate papers, citations, findings, benchmarks, datasets, APIs, vulnerabilities, status, numbers, plugin capabilities, or guarantees. Unverifiable → `UNKNOWN / REQUIRES VALIDATION`. Proposed but unbuilt → `PROPOSED`. Actually built → `IMPLEMENTED`, with what was tested.

Because this project is self-directed, the honesty rule applies with extra force to your own reasoning: a design you invented is not validated by the fact that you invented it carefully.

When something genuinely doesn't work: determine whether the limit is theoretical / architectural / algorithmic / cryptographic / resource / tooling / state-of-the-art, then look for an alternative architecture, approximation, simulation, hybrid approach, different algorithm, or reduced scope. Document the real limitation instead of faking a fix.

---

## 24. Autonomy boundaries

**Proceed autonomously:** routine engineering, tooling, refactors, test design, benchmark setup, documentation.

**Investigate → log in `DECISIONS.md` → update the spec → then implement:** the research definition (`RD-001`), the contribution boundary, the SecAgg↔robustness stance, the scope lock, any crypto or protocol choice, any reversal of a prior logged decision, any adoption of an ECC plugin recommendation.

**Stop and ask:** only for a `GOAL-CHALLENGE` (Section 2), or if continuing would require fabricating something to look complete.

Don't wait for a go-ahead on individual steps once the plan is set. Don't silently make a call that would be expensive to reverse.

---

## 25. First execution — do this now

1. State your environment (does it have file system, bash, test execution?) and the effective Section 1 parameters.
2. Confirm the fixed goal in one sentence (Section 2). Note that no blueprint exists and that you are authoring the research definition yourself.
3. Inventory the ECC plugin (Section 4) → `TOOLING_INVENTORY.md`. Verified capabilities only.
4. Survey the state of the art (Section 11). Tag every claim's evidence level.
5. Draft ≥3 candidate framings; prior-art comparison matrix against the closest existing systems; kill the non-viable ones (Section 3).
6. Write the Research Gap Statement.
7. Lock `RD-001` in `DECISIONS.md` with rejected alternatives and rationale.
8. Run the Contribution Boundary Analysis (Section 5).
9. Resolve the SecAgg↔robustness stance as a logged decision (Section 15).
10. Classify scope by necessity and lock it (Section 6).
11. Design the strongest defensible architecture given all of the above; run adversarial self-review (Section 12) and revise.
12. Write `PROJECT_MASTER_SPEC.md`, then `IMPLEMENTATION_PLAN.md`, then `PROJECT_PROGRESS.md` / `SESSION_HANDOVER.md` / `DECISIONS.md`.
13. Cross-check all control documents for contradictions.
14. Create the actual repo structure.
15. Implement the first dependency-ready research-critical task.
16. Test it. Validate security and correctness. Update the control docs.
17. Continue to the next dependency-ready task — don't stop once the documents exist.

---

## 26. Definition of success

Not "a working prototype." A system, complete through research-critical and required-supporting scope, that **directly tests the stated research hypothesis** — with a defensible architecture, an explicit trust model, defensible (not overclaimed) security claims, real measurements, reproducible experiments, a real attack evaluation, honest limitations, a defensible and possibly narrow novelty claim grounded in an actual literature gap, a clean tested implementation, and documentation that matches the code.

The fact that you designed it yourself raises the bar on the evidence, not lowers it. Report the truth about what's out of scope and unbuilt rather than papering over it.
