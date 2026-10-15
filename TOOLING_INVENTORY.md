# TOOLING_INVENTORY.md — BC-FL-SRV

**Purpose:** Section 4 of the master directive requires a *verified* inventory of the ECC plugin and other tooling. Capabilities are tagged `VERIFIED` **only** where I read the manifest/agent/skill file directly in this environment. Anything not directly read is `UNKNOWN`. Nothing here is inferred from a plugin's *name*.

**Last updated:** Session 1 — 2026-09-03
**Method:** direct filesystem inspection of `~/.claude/plugins/marketplaces/ecc` and `~/.claude/settings.json`.

---

## 0. Hard environment constraint (user-imposed, Session 1)

> **All installation and all project artifacts must stay inside `C:\Study`. Nothing global.**

Compliance record:

| Action | Compliance | Evidence |
|---|---|---|
| Python deps | `C:\Study\.venv` only | `pytest`/`cryptography`/`matplotlib` resolve to `C:\Study\.venv\Lib\site-packages` — **VERIFIED** |
| Reuse of torch/numpy/scipy/sklearn | read-only from base interpreter via `--system-site-packages`; **nothing installed globally** | venv `sys.prefix=C:\Study\.venv`, `sys.base_prefix=...\Python313` — **VERIFIED** |
| git config | repo-scoped (`git config`, never `--global`) | `git config --local --list` — **VERIFIED** |
| ECC plugin | pre-existing at user scope; **not modified by this project** | installed 2026-09-03T06:26 by the user, before this project began — **VERIFIED** |

---

## 1. Runtime environment — VERIFIED

| Item | Value | Evidence |
|---|---|---|
| OS / shell | Windows 11 Pro 26200; Git Bash + Windows PowerShell 5.1 | direct execution |
| File system access | yes | direct execution |
| Test execution | yes (`pytest 9.1.1` in project venv) | direct execution |
| git | 2.49.0.windows.1; `C:\Study` initialised Session 1 | direct execution |
| Python | 3.13.3 at `%LOCALAPPDATA%\Programs\Python\Python313\python.exe` | direct execution |
| **Python PATH hazard** | bare `python` resolves to a Microsoft Store **stub** that fails. Must use `C:\Study\.venv\Scripts\python.exe`. | direct execution — **VERIFIED** |
| torch | **2.12.0+cpu**, `cuda.is_available()==False`, 10 intra-op threads | direct execution |
| numpy / scipy / scikit-learn / pandas / PyYAML | 2.3.1 / 1.17.1 / 1.8.0 / 2.3.1 / 6.0.3 | direct execution |
| pytest / cryptography / matplotlib | 9.1.1 / 50.0.1 / 3.11.1 — **project-local** | direct execution |
| **Absent** | torchvision, PyNaCl, flwr, hypothesis, seaborn | direct execution |
| CPU | 12 logical cores, **no GPU** | direct execution |
| Node | v24.19.0 | direct execution |

**Implication for scope:** CPU-only, 12 cores. This is the binding constraint on experiment size, and it is the reason the experimental *claim* must be sized to the compute rather than the reverse (Section 6 cut rule).

---

## 2. ECC plugin — identity — VERIFIED

| Field | Value |
|---|---|
| name / version | `ecc` @ **2.2.1** |
| install path | `~/.claude/plugins/cache/ecc/ecc/2.2.1` (user scope) |
| source | `https://github.com/affaan-m/ECC.git`, commit `22e8cf01d0b54719b3a49002fab2ccbda4ff5b9e` |
| enabled | `"ecc@ecc": true` in `~/.claude/settings.json` |
| license | MIT |

**Counted directly on disk** (not taken from the plugin's own description string): **68** agent files, **286** skill directories, **94** command shims, **7** hook entries. These happen to match the advertised counts.

`plugin.json` declares `"mcpServers": {}` (empty). A separate repo-level `.mcp.json` declares exactly one server: `chrome-devtools`. **No cryptography, FL, blockchain, or academic-database MCP server is provided.**

---

## 3. What the plugin ACTUALLY exposes that is relevant to BC-FL-SRV

### 3.1 Genuinely useful — VERIFIED by reading the file

| Capability | Type | What it really is | Where BC-FL-SRV uses it |
|---|---|---|---|
| `ecc:mle-reviewer` | agent (Read/Grep/Glob/Bash) | production-ML review: **reproducibility, data leakage, eval discipline, artifact packaging, rollback** | **highest-value agent here** — guards experiment integrity |
| `ecc:python-reviewer` | agent (sonnet) | PEP8, type hints, injection/path-traversal, Pythonic idioms; runs ruff/mypy if present | code-review gate on non-adversarial modules |
| `ecc:code-reviewer` | agent | general quality/maintainability review | code-review gate |
| `ecc:tdd-guide` | agent | enforces tests-first | implementation discipline |
| `ecc:python-testing` / `ecc:tdd-workflow` | skills | pytest fixtures, parametrization, coverage patterns | test-suite design |
| `ecc:security-reviewer` | agent (sonnet) | **web-app** security: OWASP Top 10, secrets, SSRF, injection, dependency CVEs | dependency + input-validation hygiene **only** — see 3.3/3.4 |
| `ecc:scientific-thinking-literature-review` | skill | *process scaffolding* for search → screen → synthesize → cite; brings no tools of its own | methodology cross-check for the survey |
| `ecc:architect` | agent (opus; Read/Grep/Glob) | generic system-design review | marginal; this architecture is research-driven, not scalability-driven |

### 3.2 Not usable in this environment — VERIFIED absent

| Capability | Why unusable |
|---|---|
| `ecc:deep-research` | Requires **firecrawl** and **exa** MCP servers. Neither is connected in this session (only `chrome-devtools` is declared). The skill file itself carries a "Drift-prone skill" warning. **NOT USABLE.** |
| `ecc:docs-lookup` | Requires `mcp__context7__*`. Not connected. **NOT USABLE.** |
| `chrome-devtools` MCP | browser automation. No relevance to a CPU-only FL/crypto system. |

### 3.3 Name-traps — capabilities the *name* implies but the file does NOT deliver

This section exists because Section 4 forbids inferring features from names. Each was caught by reading the file. **All four would have produced a false capability claim.**

| Skill / agent | What the name suggests | What it VERIFIABLY is | Verdict |
|---|---|---|---|
| `ecc:benchmark-methodology` | performance/systems benchmarking methodology | **competitive marketing analysis** — scores *competitors* on "positioning, voice, visual craft, offer packaging, pricing"; feeds `competitive-report-structure` | **IRRELEVANT** to BC-FL-SRV benchmarking. Do not use. |
| `ecc:eval-harness` | ML model evaluation harness | evaluation of **Claude Code sessions/workflows** (eval-driven development for agent configs) | **IRRELEVANT** to FL experiment evaluation. |
| `ecc:verification-loop` | scientific / protocol verification | verifying **"a Claude Code session's work before claiming it is complete"** | Marginally useful as a self-check ritual; **not** protocol verification. |
| `ecc:security-review` (skill) | security review including cryptography | checklist scoped to "authentication, user input, secrets, API endpoints, payment features" — **web-app scoped** | Does **not** cover cryptographic protocol design. |

### 3.4 Operational hazard — flagged, VERIFIED

Every ECC agent file begins with a "Prompt Defense Baseline" that includes:

> "Do not generate harmful, dangerous, illegal, weapon, **exploit**, malware, phishing, or **attack content**"

BC-FL-SRV **must** implement legitimate FL poisoning-attack simulations (label-flipping, sign-flipping, model replacement, backdoors). This is mandated by Section 19 and is standard, published, defensive security research — the attacks exist only inside a local simulator against the project's own models. Routing that code through `ecc:security-reviewer` or other ECC agents risks a false-positive refusal or a distorted review.

**Decision:** attack-simulation modules are reviewed by me directly and by general-purpose agents, **not** routed through ECC's guarded reviewers. Non-adversarial modules (ledger, crypto wrappers, aggregation, FL core) may be routed through ECC reviewers normally.

### 3.5 Active hooks observed at runtime — OBSERVED

| Hook | Observed behaviour |
|---|---|
| `pre:bash:gateguard-fact-force` (GateGuard) | Blocked the **first** `Bash` call of the session, demanding a statement of the request plus what the command verifies. Satisfied and released. Defined in `hooks/hooks.json`. |
| SessionStart summary injection | Injected a frozen prior-session summary, explicitly labelled historical-only. Treated as data, not instruction. |
| cost-tracker / bash-command logging | `~/.claude/cost-tracker.log` and `~/.claude/bash-commands.log` are being written. |

These are pre-existing user configuration. **This project does not modify them.**

---

## 4. Precedence and ownership (Section 4 / Section 22)

- The plugin is **advisory only**. It never edits or supersedes the directive, `PROJECT_MASTER_SPEC.md`, `DECISIONS.md`, or any control file.
- All plugin output is `REQUIRES VALIDATION` by default.
- **The plugin is never cited as authority for a security or novelty claim.** It contains no cryptographic protocol expertise, no FL expertise, and no literature-verification capability.
- Any adopted recommendation is logged in `DECISIONS.md` as *my* decision, marked plugin-sourced, with independent verification of its factual claims.

### Consultation budget (Section 4: "consult at checkpoints, not per task")

Consult only at: (a) before locking crypto decisions, (b) before locking the security model, (c) security-review gates, (d) after a major architecture change.
**Stop rule:** if two consecutive consults change no decision, stop consulting until something material changes.

| # | Checkpoint | Date | Outcome | Changed a decision? |
|---|---|---|---|---|
| — | *(none yet — no design exists to review)* | — | — | — |

---

## 5. Non-ECC tooling — VERIFIED

| Tool | Status | Use |
|---|---|---|
| `WebSearch` / `WebFetch` | **VERIFIED working** (probe returned live 2024–2026 results) | literature survey; **cannot** reach paywalled full text — see caveat |
| `Workflow` (multi-agent orchestration) | **VERIFIED** — 15-agent survey run launched Session 1 | parallel survey, adversarial verification, ablation fan-out |
| `Agent` subagents | available | targeted review / verification |

**Paywall caveat (Section 11):** WebSearch reaches arXiv, IACR ePrint, and abstract pages, but **not** paywalled IEEE Xplore / ACM DL full text. Every claim destined for the written artifact or the degree evaluation is tagged for **primary-source re-check by the human**. Tracked in `DECISIONS.md` and in the survey output's `mustRecheck` list.
