"""
Presentation Defense Cheat-Sheet & Guide Generator (HTML + Headless Chrome PDF)
BC-FL-SRV: Verifiable Admission Decisions for Privacy-Preserving Federated Learning
"""
import os
import subprocess
from pathlib import Path

def generate_pdf():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>BC-FL-SRV Presentation Defense Guide &amp; Cheat-Sheet</title>
<style>
  @page {
    size: A4;
    margin: 1.5cm 1.5cm 1.5cm 1.5cm;
    @bottom-center {
      content: "BC-FL-SRV Defense Guide | Page " counter(page);
      font-size: 8pt;
      font-family: 'Helvetica Neue', Arial, sans-serif;
      color: #666;
    }
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    line-height: 1.45;
    font-size: 10pt;
    margin: 0;
    padding: 0;
  }

  .cover-card {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
    color: white;
    padding: 24px 28px;
    border-radius: 10px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }

  .cover-card h1 {
    font-size: 18pt;
    margin: 0 0 6px 0;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #ffffff;
  }

  .cover-card h2 {
    font-size: 11pt;
    font-weight: 500;
    margin: 0 0 14px 0;
    color: #93c5fd;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    font-size: 9pt;
    background: rgba(255, 255, 255, 0.1);
    padding: 10px 14px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.15);
  }

  .meta-item strong {
    color: #bfdbfe;
  }

  h2.section-header {
    font-size: 12pt;
    color: #0f172a;
    border-bottom: 2px solid #2563eb;
    padding-bottom: 4px;
    margin-top: 20px;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: flex;
    align-items: center;
  }

  h3.sub-header {
    font-size: 10.5pt;
    color: #1e3a8a;
    margin-top: 12px;
    margin-bottom: 4px;
    font-weight: 700;
  }

  .callout {
    background: #f8fafc;
    border-left: 4px solid #2563eb;
    padding: 10px 14px;
    border-radius: 0 6px 6px 0;
    margin-bottom: 12px;
    font-size: 9.5pt;
  }

  .callout-gold {
    background: #fffbeb;
    border-left: 4px solid #d97706;
    padding: 10px 14px;
    border-radius: 0 6px 6px 0;
    margin-bottom: 12px;
    font-size: 9.5pt;
  }

  .callout-green {
    background: #f0fdf4;
    border-left: 4px solid #16a34a;
    padding: 10px 14px;
    border-radius: 0 6px 6px 0;
    margin-bottom: 12px;
    font-size: 9.5pt;
  }

  .script-box {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 10px;
    font-size: 9.5pt;
  }

  .script-step {
    font-weight: 700;
    color: #1e40af;
    margin-bottom: 3px;
  }

  .script-quote {
    color: #0f172a;
    font-style: italic;
    line-height: 1.4;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 14px 0;
    font-size: 9pt;
  }

  th, td {
    padding: 6px 8px;
    border: 1px solid #cbd5e1;
    text-align: left;
  }

  th {
    background: #f1f5f9;
    font-weight: 700;
    color: #0f172a;
  }

  tr:nth-child(even) {
    background: #f8fafc;
  }

  .badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 7.5pt;
    font-weight: 700;
    text-transform: uppercase;
  }

  .badge-blue { background: #dbeafe; color: #1e40af; }
  .badge-green { background: #dcfce7; color: #15803d; }
  .badge-amber { background: #fef3c7; color: #b45309; }

  .qa-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 8px;
    page-break-inside: avoid;
  }

  .qa-q {
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 4px;
    font-size: 9.5pt;
  }

  .qa-a {
    color: #334155;
    font-size: 9pt;
    line-height: 1.4;
  }

  .code-snip {
    background: #1e293b;
    color: #38bdf8;
    padding: 8px 10px;
    border-radius: 6px;
    font-family: 'SFMono-Regular', Consolas, Monaco, monospace;
    font-size: 8.5pt;
    margin: 6px 0;
    overflow-x: auto;
  }

  .page-break {
    page-break-after: always;
  }

  ul, ol {
    margin: 4px 0 8px 18px;
    padding: 0;
  }

  li {
    margin-bottom: 3px;
  }
</style>
</head>
<body>

<!-- PAGE 1 -->
<div class="cover-card">
  <h1>BC-FL-SRV: Presentation &amp; Viva Defense Guide</h1>
  <h2>Verifiable Admission Decisions for Privacy-Preserving Federated Learning</h2>
  <div class="meta-grid">
    <div class="meta-item"><strong>Department:</strong> Computer Engineering, SIES GST</div>
    <div class="meta-item"><strong>Academic Year:</strong> 2026–27 (Semester VII Stage-I)</div>
    <div class="meta-item"><strong>Group Members:</strong> Ayush Lanke (123A7004), Bhumi Beloshe (123A7005), Sakshi Bhandare (123A7007)</div>
    <div class="meta-item"><strong>Implementation Timeline:</strong> 1 August 2026 to 5 October 2026</div>
  </div>
</div>

<h2 class="section-header">1. The 30-Second Elevator Pitch (The Real-World Analogy)</h2>
<div class="callout-gold">
  <strong>The "Blindfolded Teacher" Analogy:</strong><br>
  Imagine students taking an exam from home (Federated Learning). To prevent cheating, they put their answers inside sealed, opaque envelopes (Secure Aggregation). The teacher adds up all the test scores while completely blindfolded so they cannot spy on any single student's paper. That protects privacy.<br><br>
  <strong>The Big Problem:</strong> Because the teacher is blindfolded, <em>nobody can check whether the teacher secretly threw away honest students' papers, included fake exam sheets from unauthorized students, or applied the declared grading curve honestly!</em><br><br>
  <strong>Our Solution (BC-FL-SRV):</strong> We use an immutable cryptographic audit log (RFC 6962 Merkle Tree) and a rotating committee of elected participants who inspect bounded mathematical sketches of updates, threshold-sign the admission decision, and publish it so <strong>any external auditor can mathematically verify fairness in microseconds without seeing raw private data</strong>.
</div>

<h2 class="section-header">2. Core Concepts Cheat-Sheet (Instant Plain-English Definitions)</h2>
<table>
  <tr>
    <th style="width: 25%;">Concept</th>
    <th>What It Actually Means (Plain English)</th>
  </tr>
  <tr>
    <td><strong>Federated Learning (FL)</strong></td>
    <td>Decentralized AI training: edge devices train locally and send only weight deltas to a central server; raw data never leaves the device.</td>
  </tr>
  <tr>
    <td><strong>Secure Aggregation (SecAgg)</strong></td>
    <td>Pairwise additive masking where masks cancel out when added together. Server sees <em>only the sum</em>, not individual contributions.</td>
  </tr>
  <tr>
    <td><strong>The Accountability Gap</strong></td>
    <td>Because updates are masked, the server can secretly drop honest clients or inject poisoned updates without anyone being able to prove it.</td>
  </tr>
  <tr>
    <td><strong>AG1: Correct Admission</strong></td>
    <td>Proving that only clients who met the declared admission rule were included in the round.</td>
  </tr>
  <tr>
    <td><strong>AG2: Correct Aggregation</strong></td>
    <td>Proving the mathematical vector sum was calculated correctly (traditionally requires slow Zero-Knowledge Proofs).</td>
  </tr>
  <tr>
    <td><strong>AG3: Non-Equivocation</strong></td>
    <td>Proving the server cannot show different models or histories to different participants (forking the state).</td>
  </tr>
  <tr>
    <td><strong>RFC 6962 Merkle Tree</strong></td>
    <td>The IETF standard used by Google Certificate Transparency. Guarantees tamper-evidence and microsecond inclusion proofs.</td>
  </tr>
  <tr>
    <td><strong>Verifiable Sortition</strong></td>
    <td>A fair cryptographic lottery that picks an attestation committee using the previous round's Merkle root as a tamper-proof seed.</td>
  </tr>
  <tr>
    <td><strong>Bounded Evidence Ladder (E0–E4)</strong></td>
    <td>Five privacy tiers: E0 (cryptographic commitment only) to E3 (64-dimensional random projection sketch) to E4 (full plaintext update).</td>
  </tr>
  <tr>
    <td><strong>G2 Admission Rule</strong></td>
    <td>Our two-factor filter: checks both update magnitude (norm) and low-dimensional cosine direction against a running momentum reference.</td>
  </tr>
</table>

<div class="page-break"></div>

<!-- PAGE 2 -->
<h2 class="section-header">3. Word-For-Word Presentation Script (5-Minute Speaking Guide)</h2>

<div class="script-box">
  <div class="script-step">Step 1: Introduction (30 seconds)</div>
  <div class="script-quote">
    "Good morning respected guide and faculty members. We are Ayush, Bhumi, and Sakshi. Today we present our Stage-I Major Project titled <strong>BC-FL-SRV: Verifiable Admission Decisions for Privacy-Preserving Federated Learning</strong>. In short, our system solves a major vulnerability in decentralized machine learning: how to guarantee that the central server does not cheat when admitting participants, while preserving complete privacy under secure aggregation."
  </div>
</div>

<div class="script-box">
  <div class="script-step">Step 2: The Core Problem (45 seconds)</div>
  <div class="script-quote">
    "Federated learning protects data privacy by training models locally on edge devices. To prevent the server from spying on gradients, Secure Aggregation masks individual updates so the server only sees the aggregate sum. However, this creates a critical accountability gap: because updates are hidden, the server has unchecked authority. It can secretly discard honest participants or admit poisoned updates, and no external party can verify it.<br>
    Recent literature from PoPETs 2026 shows that over 75% of research focuses solely on verifying aggregation using computationally heavy Zero-Knowledge Proofs. In contrast, verifiable admission (AG1) and non-equivocation (AG3) have been largely overlooked, despite being fundamentally lighter and cheaper to verify."
  </div>
</div>

<div class="script-box">
  <div class="script-step">Step 3: Our Proposed System Architecture (1 minute)</div>
  <div class="script-quote">
    "To solve this without needing slow Zero-Knowledge Proofs or proprietary secure hardware, we developed BC-FL-SRV based on three architectural pillars:<br>
    <strong>First</strong>, an append-only RFC 6962 Merkle Transcript that immutably logs every client submission, admission set, and aggregation.<br>
    <strong>Second</strong>, a Rotating Attestation Committee selected via verifiable sortition seeded from the previous Merkle root. Committee members inspect bounded privacy-preserving sketches (E3) and threshold-sign the admission set.<br>
    <strong>Third</strong>, a Stateless External Auditor that can verify AG1 and AG3 from the public Merkle root alone in microseconds."
  </div>
</div>

<div class="script-box">
  <div class="script-step">Step 4: Experimental Results &amp; Implementation (1 minute)</div>
  <div class="script-quote">
    "Between 1st August and 5th October 2026, we completed the core system implementation and conducted seven benchmark experiments:<br>
    • <strong>Model Size Invariance:</strong> Auditor verification takes just 1.5 microseconds and is strictly independent of model size (a 1.03× ratio across a 65,536× model size scaling range).<br>
    • <strong>Tamper Detection:</strong> Our protocol detects 12 out of 14 adversarial attack vectors with zero false alarms.<br>
    • <strong>Machine Learning Utility:</strong> On Fashion-MNIST under Dirichlet non-IID partitioning, our system reaches 83.88% test accuracy with exactly zero accuracy loss compared to an unmasked baseline.<br>
    • <strong>Code Rigor:</strong> We have 366 automated unit and security tests passing with 99% overall code coverage."
  </div>
</div>

<div class="script-box">
  <div class="script-step">Step 5: Stage-II Roadmap &amp; Closing (30 seconds)</div>
  <div class="script-quote">
    "For Stage-II next semester, we will conduct component ablation studies, simulate peer-to-peer auditor gossip networks to prevent split-view attacks, and prepare our findings for conference publication. Thank you, and we welcome your questions."
  </div>
</div>

<div class="page-break"></div>

<!-- PAGE 3 -->
<h2 class="section-header">4. Top 10 Questions Faculty Will Ask &amp; Winning Answers</h2>

<div class="qa-card">
  <div class="qa-q">Q1: Why did you use an RFC 6962 Merkle tree instead of Ethereum or Hyperledger?</div>
  <div class="qa-a"><strong>Answer:</strong> "Storing frequent model updates on Ethereum is cost-prohibitive in gas fees and leaks privacy on a public chain. RFC 6962 Merkle trees—the exact cryptographic standard powering Google's Certificate Transparency—provide the exact same tamper-evidence, immutability, and O(log n) inclusion proofs at zero cost and microsecond verification speed."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q2: What is the difference between AG1, AG2, and AG3?</div>
  <div class="qa-a"><strong>Answer:</strong> "These are formal integrity claims from the PoPETs 2026 systematization: <strong>AG1 (Correct Admission)</strong> proves only eligible clients were admitted; <strong>AG2 (Correct Aggregation)</strong> proves the sum was computed correctly; and <strong>AG3 (Non-Equivocation)</strong> proves the server shows the same history and model to everyone."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q3: How can the committee check updates without seeing raw private client data?</div>
  <div class="qa-a"><strong>Answer:</strong> "We designed a bounded evidence ladder (E0 to E4). Instead of inspecting raw weights, the committee inspects a bounded sketch (E3)—a 64-dimensional random Johnson-Lindenstrauss projection that preserves norm and directional cosine similarity without revealing the raw training dataset."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q4: What dataset, neural network, and hyperparameters did you use?</div>
  <div class="qa-a"><strong>Answer:</strong> "We evaluated on Fashion-MNIST using a Convolutional Neural Network (SmallCNN) across 5 clients. To simulate real edge heterogeneity, we partitioned data using a non-IID Dirichlet distribution with concentration parameter α = 0.5, reaching 83.88% accuracy in 10 rounds."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q5: What happens if committee members collude or are corrupted?</div>
  <div class="qa-a"><strong>Answer:</strong> "We use threshold multi-signatures (t of m). In Experiment E-3, we analyzed corruption using a hypergeometric probability model. While a single self-attesting aggregator has a 20% forge chance at 20% corruption, an attested committee of size m = 15 suppresses the forgery probability to 2.92 × 10⁻⁷."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q6: What are the two attacks your system could NOT detect? (Honest Negative Results)</div>
  <div class="qa-a"><strong>Answer:</strong> "We detected 12 of 14 attacks. The two undetected cases are: (1) Selective client dropping where only the excluded client observes its absence (resolved via client-side inclusion proofs), and (2) Split-view equivocation when only one auditor is present (which we are addressing in Stage-II via multi-auditor gossip protocols)."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q7: Why does verification cost NOT increase when the AI model gets bigger?</div>
  <div class="qa-a"><strong>Answer:</strong> "Because the auditor only verifies cryptographic hashes and Ed25519 digital signatures on the Merkle tree nodes. Regardless of whether the model has 1,000 parameters (64 bytes) or 1 million parameters (4 MiB), the SHA-256 hash is always exactly 32 bytes, keeping verification time constant at ~1.5 microseconds."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q8: How does verifiable sortition prevent the server from rigging the committee?</div>
  <div class="qa-a"><strong>Answer:</strong> "The random seed used to pick committee members is derived deterministically from the Merkle root of the previous finalized round (R_{t-1}). Because the root is committed cryptographically before round t begins, the server cannot manipulate the seed without invalidating past history."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q9: How do you know the code is bug-free and handles malicious inputs?</div>
  <div class="qa-a"><strong>Answer:</strong> "We wrote 366 automated test cases with 99% line coverage. Our tests specifically assert that every verifier 'fails closed'—meaning malformed, truncated, or tampered bytes immediately reject without crashing the system."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Q10: What is your Stage-II plan for Semester VIII?</div>
  <div class="qa-a"><strong>Answer:</strong> "Stage-II focuses on: (1) Component ablation studies (Experiment E-7) to prove the necessity of each component, (2) Multi-auditor gossip simulations (Experiment E-6), and (3) Compiling our research findings into a conference paper manuscript."</div>
</div>

<div class="page-break"></div>

<!-- PAGE 4 -->
<h2 class="section-header">5. Live Demonstration Cheat-Sheet (Commands to Run)</h2>

<div class="callout-green">
  <strong>Pro-Tip for Tomorrow:</strong> If the faculty asks to see the project running, keep a terminal window open in <code>/Users/ayush/Downloads/Study</code>. You have two options that work reliably:
</div>

<h3 class="sub-header">Option 1: Run the 366 Automated Tests (Takes ~5 Seconds)</h3>
<p>Shows instant engineering maturity and 100% test pass rate in green text:</p>
<div class="code-snip">
.venv_mac/bin/python -m pytest tests/ -v
</div>

<h3 class="sub-header">Option 2: Launch the Interactive Web Dashboard</h3>
<p>Opens a web application at <code>http://127.0.0.1:8000</code> showing Merkle blocks, transactions, and attack simulations:</p>
<div class="code-snip">
.venv_mac/bin/python scripts/run_ui.py
</div>

<h3 class="sub-header">Option 3: Run the Decentralized FL Simulation Demo</h3>
<p>Runs a live 5-client training round simulation on the console:</p>
<div class="code-snip">
.venv_mac/bin/python scripts/run_demo.py --rounds 3 --quiet
</div>

<h2 class="section-header">6. Repository Directory Structure Reference</h2>
<table>
  <tr>
    <th style="width: 32%;">Folder / Module</th>
    <th>Responsibility in the Project</th>
  </tr>
  <tr>
    <td><code>src/bcflsrv/ledger/</code></td>
    <td>RFC 6962 Merkle tree, inclusion proofs, consistency proofs, typed transcript.</td>
  </tr>
  <tr>
    <td><code>src/bcflsrv/crypto/</code></td>
    <td>Ed25519 digital signature keys, verifiable committee sortition engine.</td>
  </tr>
  <tr>
    <td><code>src/bcflsrv/protocol/</code></td>
    <td>Admission sets, multi-signature threshold attestation, external auditor engine.</td>
  </tr>
  <tr>
    <td><code>src/bcflsrv/fl/</code></td>
    <td>PyTorch SmallCNN, Fashion-MNIST, Dirichlet non-IID partition, E0-E4 ladder, G1/G2 rules.</td>
  </tr>
  <tr>
    <td><code>src/bcflsrv/bench/</code></td>
    <td>Microsecond-precision benchmark harnesses and parameter scaling utilities.</td>
  </tr>
  <tr>
    <td><code>src/bcflsrv/ui/</code></td>
    <td>FastAPI web backend and interactive HTML5 Canvas research dashboard.</td>
  </tr>
  <tr>
    <td><code>scripts/</code></td>
    <td>Benchmark runners for E-1 (scaling), E-2 (attacks), E-3 (corruption), E-4/E-5 (trade-off).</td>
  </tr>
  <tr>
    <td><code>tests/</code></td>
    <td>366 comprehensive unit, protocol, security, and UI integration test cases (99% coverage).</td>
  </tr>
</table>

<div class="page-break"></div>

<h2 class="section-header">7. Code Walkthrough: Explaining merkle.py (Lines 117–157)</h2>
<div class="callout">
  <strong>Why this matters:</strong> If the faculty asks you to open the codebase and explain how the Merkle tree works, navigate to <code>src/bcflsrv/ledger/merkle.py</code> and explain these exact lines:
</div>

<div class="qa-card">
  <div class="qa-q">Line 119: What is self._stack = []?</div>
  <div class="qa-a"><strong>Explanation:</strong> "It stores subtrees as tuples of <code>(subtree_root, subtree_size)</code>. The sizes are strictly decreasing from left to right (like powers of 2: 8, 4, 2, 1). This allows us to append new leaves incrementally without rebuilding the entire tree from scratch."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Lines 129–134: How does append() merge equal-sized neighbours?</div>
  <div class="qa-a"><strong>Explanation:</strong> "When a new leaf is added, it pushes <code>(leaf_hash, 1)</code> to the stack. The while-loop checks if the top two items have equal sizes. If both subtrees have size 1, they merge into a parent of size 2. If the stack now has two trees of size 2, they merge into size 4. This is identical to <strong>binary carry addition</strong> (1 + 1 = 10 in binary), giving an O(log n) append amortized time."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Lines 137–144: How is the current root computed?</div>
  <div class="qa-a"><strong>Explanation:</strong> "If there are remaining unequal subtrees on the stack (for instance, a tree of size 4 and size 1), the property folds them together from left to right using <code>hash_children(left_root, right_root)</code>, producing the exact canonical Merkle Tree Hash specified in RFC 6962."</div>
</div>

<div class="qa-card">
  <div class="qa-q">Lines 147–157: What is inclusion_proof()?</div>
  <div class="qa-a"><strong>Explanation:</strong> "It generates the audit path for a leaf at a given index. It recursively splits the tree at the largest power of two below n (<code>k = _largest_power_of_two_below(n)</code>), providing the sequence of sibling hashes needed for an auditor to recompute the root in O(log n) hash steps."</div>
</div>

<h2 class="section-header">8. Last-Minute 10-Hour Checklist for Tomorrow</h2>
<div class="callout-gold">
  <ul>
    <li><strong>1. Open Terminal in Project Folder:</strong> Run <code>cd /Users/ayush/Downloads/Study</code> and make sure <code>.venv_mac</code> is ready.</li>
    <li><strong>2. Practice Running Pytest Once Tonight:</strong> Run <code>.venv_mac/bin/python -m pytest tests/ -q</code> so you see the green dots yourself.</li>
    <li><strong>3. Read the 5-Minute Script Twice Out Loud:</strong> Don't try to memorize every word; just remember the sequence: <em>(1) Title &rarr; (2) The Blindfolded Teacher Problem &rarr; (3) Our 3 Pillars &rarr; (4) The 4 Key Numbers &rarr; (5) Conclusion.</em></li>
    <li><strong>4. Remember the 4 Key Numbers:</strong>
      <ul>
        <li><strong>83.88%</strong> test accuracy on Fashion-MNIST with SmallCNN.</li>
        <li><strong>1.03×</strong> verification ratio (meaning 1.5 µs verification cost whether model is 64 B or 4 MiB).</li>
        <li><strong>12 / 14</strong> adversarial attacks detected with 0 false alarms.</li>
        <li><strong>366</strong> automated test cases passing with <strong>99%</strong> code coverage.</li>
      </ul>
    </li>
    <li><strong>5. Files to Keep Ready on Screen:</strong>
      <ul>
        <li><code>Stage1_Report_BC-FL-SRV.docx</code> (your formal report)</li>
        <li><code>Logbook_12Weeks_BC-FL-SRV.docx</code> (your 12-week logbook)</li>
        <li><code>BC-FL-SRV_Presentation_CheatSheet_and_Defense_Guide.pdf</code> (this cheat-sheet guide)</li>
      </ul>
    </li>
  </ul>
</div>

<div class="callout" style="margin-top: 14px; text-align: center;">
  <strong>Prepared for:</strong> Stage-I Major Project Viva Defense | SIES Graduate School of Technology (Autonomous)<br>
  <em>Ayush Lanke • Bhumi Beloshe • Sakshi Bhandare</em>
</div>

</body>
</html>
"""
    html_path = Path("/Users/ayush/Downloads/Study/presentation_defense_guide.html")
    pdf_path = Path("/Users/ayush/Downloads/Study/BC-FL-SRV_Presentation_CheatSheet_and_Defense_Guide.pdf")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML saved at: {html_path}")

    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_bin,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and pdf_path.exists():
        size_kb = pdf_path.stat().st_size / 1024
        print(f"PDF generated successfully at: {pdf_path} ({size_kb:.1f} KB)")
    else:
        print("Chrome error:", res.stderr)

if __name__ == "__main__":
    generate_pdf()
