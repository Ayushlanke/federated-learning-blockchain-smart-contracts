"""
Generate all figures, UML diagrams, DFDs, ER diagrams, Gantt charts, and UI screenshots
for the LaTeX Report: "Secure Federated Learning Using Blockchain and Smart Contracts"
Saved into: /Users/ayush/Downloads/Study/SIESGST_CE_sem7_report/
"""
import os
import subprocess
import time
import urllib.request
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
from PIL import Image

OUT_DIR = Path("/Users/ayush/Downloads/Study/SIESGST_CE_sem7_report")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# 1. GANTT CHART (1 Aug 2026 to 5 Oct 2026)
# ----------------------------------------------------------------------
def generate_gantt_chart():
    print("Generating Gantt Chart...")
    tasks = [
        ("Problem Identification & Literature Survey", "2026-08-01", "2026-08-10", "#2563eb"),
        ("Threat Model & Security Formalization", "2026-08-08", "2026-08-18", "#3b82f6"),
        ("RFC 6962 Merkle Tree Ledger Architecture", "2026-08-15", "2026-08-26", "#0284c7"),
        ("Verifiable Committee Sortition & Identities", "2026-08-22", "2026-09-02", "#0d9488"),
        ("Bounded Evidence Ladder & Admission Rules", "2026-08-28", "2026-09-08", "#10b981"),
        ("Threshold Attestation & Auditor Protocol", "2026-09-04", "2026-09-15", "#16a34a"),
        ("Fashion-MNIST FL & Non-IID Partitioning", "2026-09-10", "2026-09-22", "#ca8a04"),
        ("Adversarial Attack Simulation & Detection", "2026-09-18", "2026-09-28", "#ea580c"),
        ("Benchmark Experiments (E1-E5) & Metrics", "2026-09-24", "2026-10-02", "#dc2626"),
        ("Test Suite Validation & Stage-I Report", "2026-09-28", "2026-10-05", "#7c3aed"),
    ]

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    plt.subplots_adjust(left=0.32, right=0.96, top=0.92, bottom=0.15)

    y_pos = np.arange(len(tasks))
    start_dates = [datetime.strptime(t[1], "%Y-%m-%d") for t in tasks]
    end_dates = [datetime.strptime(t[2], "%Y-%m-%d") for t in tasks]
    durations = [(e - s).days for s, e in zip(start_dates, end_dates)]

    for i, (task, start_str, end_str, color) in enumerate(tasks):
        s_date = datetime.strptime(start_str, "%Y-%m-%d")
        dur = (datetime.strptime(end_str, "%Y-%m-%d") - s_date).days
        ax.barh(i, dur, left=s_date, color=color, alpha=0.85, edgecolor="#1e293b", height=0.6, zorder=3)
        # Add date text
        ax.text(s_date + timedelta(days=dur / 2), i, f"{dur}d", ha='center', va='center', color='white', fontweight='bold', fontsize=8, zorder=4)

    ax.set_yticks(y_pos)
    ax.set_yticklabels([t[0] for t in tasks], fontsize=9, fontweight='medium')
    ax.invert_yaxis()

    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b %Y'))
    plt.xticks(rotation=25, ha='right', fontsize=8)

    ax.set_xlim(datetime(2026, 7, 30), datetime(2026, 10, 8))
    ax.grid(axis='x', linestyle='--', alpha=0.4, zorder=0)
    ax.set_title("Stage-I Project Schedule Gantt Chart (1 Aug 2026 – 5 Oct 2026)", fontsize=11, fontweight='bold', pad=12)

    out_file = OUT_DIR / "Gantt Chart.png"
    plt.savefig(out_file, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

# ----------------------------------------------------------------------
# 2. SYSTEM ARCHITECTURE DIAGRAM
# ----------------------------------------------------------------------
def generate_system_diagram():
    print("Generating System Architecture Diagram...")
    fig, ax = plt.subplots(figsize=(12, 7.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Background subtle styling
    ax.add_patch(patches.Rectangle((1, 1), 98, 98, facecolor='#f8fafc', edgecolor='#cbd5e1', linewidth=1.5, zorder=0))

    # Title Banner
    ax.add_patch(patches.Rectangle((2, 91), 96, 7, facecolor='#0f172a', edgecolor='none', zorder=1))
    ax.text(50, 94.5, "Secure Federated Learning Using Blockchain and Smart Contracts (Architecture)", 
            ha='center', va='center', color='white', fontsize=12, fontweight='bold', zorder=2)

    def draw_box(x, y, w, h, title, items, color_header, color_body='#ffffff', border='#94a3b8'):
        # Header
        ax.add_patch(patches.Rectangle((x, y + h - 5), w, 5, facecolor=color_header, edgecolor=border, linewidth=1, zorder=2))
        ax.text(x + w/2, y + h - 2.5, title, ha='center', va='center', color='white', fontsize=9.5, fontweight='bold', zorder=3)
        # Body
        ax.add_patch(patches.Rectangle((x, y), w, h - 5, facecolor=color_body, edgecolor=border, linewidth=1, zorder=1))
        line_y = y + h - 8
        for itm in items:
            ax.text(x + 2, line_y, f"• {itm}", ha='left', va='center', color='#1e293b', fontsize=8, zorder=3)
            line_y -= 4

    # 1. Edge Clients Layer
    draw_box(4, 52, 28, 34, "Edge Clients (C1 ... Cn)", [
        "Private Datasets (Non-IID Fashion-MNIST)",
        "Local SmallCNN Training (PyTorch SGD)",
        "Additive Masking (Pairwise SecAgg)",
        "Bounded Evidence Extraction (E0-E4)",
        "Ed25519 Submission Signature"
    ], '#1e40af')

    # 2. Aggregator Layer
    draw_box(36, 52, 28, 34, "Central Aggregator (AG)", [
        "Collects Masked Tensors",
        "Submits Evidence to Committee",
        "Sums Admitted Masked Vectors",
        "Computes Global Model Update",
        "Submits Finalize Entry to Ledger"
    ], '#0369a1')

    # 3. Smart Contract / Attestation Committee
    draw_box(68, 52, 28, 34, "Rotating Committee (Smart Contract)", [
        "Verifiable Sortition (Seed = Root t-1)",
        "m-Member Ephemeral Committee",
        "Applies Admission Rules (G1/G2)",
        "Evaluates Bounded Norm & Cosine",
        "Threshold Co-Signing (t of m)"
    ], '#047857')

    # 4. RFC 6962 Blockchain Ledger
    draw_box(15, 10, 42, 34, "RFC 6962 Merkle Blockchain Ledger", [
        "Append-Only Typed Transcript",
        "Events: SUBMIT | ADMIT | AGGREGATE | FINALIZE",
        "Prev-Root Chaining (Temporal Linearity)",
        "O(log n) Cryptographic Inclusion Proofs",
        "Append-Only Consistency Proofs"
    ], '#b45309')

    # 5. External Auditor
    draw_box(63, 10, 32, 34, "Stateless External Auditor (AUD)", [
        "Holds Solely Public Merkle Roots",
        "Verifies AG1: Correct Admission Check",
        "Verifies AG3: Non-Equivocation Check",
        "Zero Model-Size Dependency (O(1))",
        "Fast Hash & Ed25519 Signature Audit"
    ], '#6d28d9')

    # Arrows
    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=1.8, shrinkA=3, shrinkB=3), zorder=5)
        if label:
            ax.text((x1 + x2)/2, (y1 + y2)/2 + 1.5, label, ha='center', va='center',
                    fontsize=7.5, fontweight='bold', color="#0f172a",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#f1f5f9", ec="#94a3b8", lw=0.8), zorder=6)

    arrow(32, 70, 36, 70, "Masked Update")
    arrow(64, 70, 68, 70, "Evidence Digest")
    arrow(68, 62, 64, 62, "Attestation")
    arrow(50, 52, 36, 44, "Round Finalize")
    arrow(57, 27, 63, 27, "Merkle Root & Proof")
    arrow(78, 52, 78, 44, "Sortition Seed Check")

    out_file = OUT_DIR / "System diagram.png"
    plt.savefig(out_file, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

# ----------------------------------------------------------------------
# 3. ENTITY-RELATIONSHIP (ER) DIAGRAM
# ----------------------------------------------------------------------
def generate_er_diagram():
    print("Generating ER Diagram...")
    fig, ax = plt.subplots(figsize=(12, 7.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.add_patch(patches.Rectangle((1, 1), 98, 98, facecolor='#fafafa', edgecolor='#cbd5e1', linewidth=1.5))
    ax.add_patch(patches.Rectangle((2, 91), 96, 7, facecolor='#1e293b', edgecolor='none'))
    ax.text(50, 94.5, "Entity-Relationship (ER) Diagram — Blockchain Federated Learning System", 
            ha='center', va='center', color='white', fontsize=12, fontweight='bold')

    def entity_box(x, y, w, h, title, pk, attrs):
        ax.add_patch(patches.Rectangle((x, y + h - 5), w, 5, facecolor='#2563eb', edgecolor='#1e40af', lw=1, zorder=2))
        ax.text(x + w/2, y + h - 2.5, title, ha='center', va='center', color='white', fontsize=9, fontweight='bold', zorder=3)
        ax.add_patch(patches.Rectangle((x, y), w, h - 5, facecolor='#ffffff', edgecolor='#94a3b8', lw=1, zorder=1))
        # PK
        ax.text(x + 2, y + h - 8, f"PK: {pk}", ha='left', va='center', color='#b91c1c', fontsize=8, fontweight='bold', zorder=3)
        cur_y = y + h - 12
        for attr in attrs:
            ax.text(x + 2, cur_y, f"• {attr}", ha='left', va='center', color='#334155', fontsize=7.5, zorder=3)
            cur_y -= 3.5

    entity_box(4, 55, 26, 32, "CLIENT", "client_id", [
        "public_key (Ed25519)",
        "dataset_partition_id",
        "registration_status",
        "sample_count"
    ])

    entity_box(37, 55, 26, 32, "ROUND", "round_id", [
        "start_timestamp",
        "status (Open/Closed)",
        "admission_rule_id",
        "committee_seed"
    ])

    entity_box(70, 55, 26, 32, "SUBMISSION", "submission_id", [
        "FK: client_id",
        "FK: round_id",
        "masked_tensor_digest",
        "evidence_tier (E0-E4)",
        "client_signature"
    ])

    entity_box(4, 12, 26, 32, "COMMITTEE", "committee_id", [
        "FK: round_id",
        "sortition_seed",
        "threshold_t",
        "quorum_m",
        "selected_members_list"
    ])

    entity_box(37, 12, 26, 32, "ADMISSION_SET", "admission_set_id", [
        "FK: round_id",
        "admitted_clients_list",
        "rejected_clients_list",
        "threshold_signatures",
        "set_digest"
    ])

    entity_box(70, 12, 26, 32, "BLOCK_ENTRY", "seq_number", [
        "FK: round_id",
        "entry_kind (SUBMIT/ADMIT...)",
        "payload_digest",
        "merkle_root",
        "prev_block_hash"
    ])

    def connect(x1, y1, x2, y2, rel):
        ax.plot([x1, x2], [y1, y2], color='#475569', lw=1.5, zorder=4)
        ax.text((x1+x2)/2, (y1+y2)/2, rel, ha='center', va='center', fontsize=7, fontweight='bold',
                color='#1e40af', bbox=dict(boxstyle="square,pad=0.2", fc="#ffffff", ec="#cbd5e1"), zorder=5)

    connect(30, 71, 37, 71, "1 : N")
    connect(63, 71, 70, 71, "1 : N")
    connect(50, 55, 50, 44, "1 : 1")
    connect(17, 55, 17, 44, "1 : N")
    connect(63, 28, 70, 28, "1 : 1")

    out_file = OUT_DIR / "ER AdvRAG.png"
    plt.savefig(out_file, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

# ----------------------------------------------------------------------
# 4. UML ACTIVITY DIAGRAM
# ----------------------------------------------------------------------
def generate_uml_activity():
    print("Generating UML Activity Diagram...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.add_patch(patches.Rectangle((1, 1), 98, 98, facecolor='#ffffff', edgecolor='#cbd5e1', linewidth=1.5))
    ax.add_patch(patches.Rectangle((2, 92), 96, 6, facecolor='#0f172a', edgecolor='none'))
    ax.text(50, 95, "UML Activity Diagram — Secure Federated Learning Round Lifecycle", 
            ha='center', va='center', color='white', fontsize=11, fontweight='bold')

    # Initial node
    circle = patches.Circle((50, 88), 2.2, facecolor='#0f172a', edgecolor='none', zorder=2)
    ax.add_patch(circle)

    steps = [
        (80, "1. Edge Local Training: Clients execute SGD epochs on Fashion-MNIST"),
        (71, "2. Masking & Evidence: Additive pairwise masking + E3 projection sketch"),
        (62, "3. Verifiable Sortition: Sample active committee from R_{t-1} seed"),
        (53, "4. Evidence Evaluation: Committee applies G2 norm & cosine filter"),
        (44, "5. Threshold Attestation: Committee threshold-signs valid admission set (t-of-m)"),
        (35, "6. Secure Aggregation: Server computes aggregate sum of admitted updates"),
        (26, "7. Ledger Anchoring: Commit round events into RFC 6962 Merkle tree"),
        (17, "8. External Audit: Auditor checks AG1 admission & AG3 root consistency")
    ]

    for y, text in steps:
        ax.add_patch(patches.FancyBboxPatch((12, y - 2.5), 76, 5, boxstyle="round,pad=0.5",
                                            facecolor='#f8fafc', edgecolor='#2563eb', lw=1.2, zorder=2))
        ax.text(50, y, text, ha='center', va='center', color='#0f172a', fontsize=8.5, fontweight='medium', zorder=3)

    # Connecting arrows
    ax.annotate("", xy=(50, 82.5), xytext=(50, 85.8), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    for i in range(len(steps) - 1):
        ax.annotate("", xy=(50, steps[i+1][0] + 2.5), xytext=(50, steps[i][0] - 2.5),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))

    # Final bullseye
    circle_out = patches.Circle((50, 8), 3, facecolor='none', edgecolor='#0f172a', lw=1.5, zorder=2)
    circle_in = patches.Circle((50, 8), 1.8, facecolor='#0f172a', edgecolor='none', zorder=3)
    ax.add_patch(circle_out)
    ax.add_patch(circle_in)
    ax.annotate("", xy=(50, 11), xytext=(50, 14.5), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))

    out_file = OUT_DIR / "Activity UML AdvRAG.png"
    plt.savefig(out_file, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

# ----------------------------------------------------------------------
# 5. DATA FLOW DIAGRAM (DFD LEVEL 1)
# ----------------------------------------------------------------------
def generate_dfd_diagram():
    print("Generating DFD Diagram...")
    fig, ax = plt.subplots(figsize=(11, 7.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.add_patch(patches.Rectangle((1, 1), 98, 98, facecolor='#ffffff', edgecolor='#cbd5e1', linewidth=1.5))
    ax.add_patch(patches.Rectangle((2, 92), 96, 6, facecolor='#1e293b', edgecolor='none'))
    ax.text(50, 95, "Data Flow Diagram (Level 1) — Secure Blockchain Federated Learning", 
            ha='center', va='center', color='white', fontsize=11, fontweight='bold')

    def entity(x, y, w, h, text):
        ax.add_patch(patches.Rectangle((x, y), w, h, facecolor='#f1f5f9', edgecolor='#0f172a', lw=1.5, zorder=2))
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', color='#0f172a', fontsize=9, fontweight='bold', zorder=3)

    def process(x, y, r, p_num, p_text):
        ax.add_patch(patches.Circle((x, y), r, facecolor='#dbeafe', edgecolor='#1e40af', lw=1.5, zorder=2))
        ax.text(x, y + 2, p_num, ha='center', va='center', color='#1e40af', fontsize=8, fontweight='bold', zorder=3)
        ax.text(x, y - 2.5, p_text, ha='center', va='center', color='#0f172a', fontsize=7.5, fontweight='medium', zorder=3)

    def datastore(x, y, w, h, d_id, d_name):
        ax.add_patch(patches.Rectangle((x, y), w, h, facecolor='#fffbeb', edgecolor='#b45309', lw=1.2, zorder=2))
        ax.plot([x + 6, x + 6], [y, y + h], color='#b45309', lw=1.2, zorder=3)
        ax.text(x + 3, y + h/2, d_id, ha='center', va='center', color='#b45309', fontsize=8, fontweight='bold', zorder=3)
        ax.text(x + 6 + (w-6)/2, y + h/2, d_name, ha='center', va='center', color='#1e293b', fontsize=8, fontweight='medium', zorder=3)

    # Entities
    entity(4, 55, 18, 12, "Edge Client")
    entity(78, 55, 18, 12, "Aggregator")
    entity(78, 15, 18, 12, "Auditor")

    # Processes
    process(34, 75, 7.5, "P1.0", "Mask & Extract")
    process(58, 75, 7.5, "P2.0", "Sortition & Rule")
    process(58, 42, 7.5, "P3.0", "Threshold Attest")
    process(34, 42, 7.5, "P4.0", "Sum Aggregation")
    process(50, 18, 7.5, "P5.0", "Audit Verification")

    # Datastores
    datastore(4, 20, 24, 8, "D1", "RFC 6962 Merkle Ledger")

    # Arrows
    def dfd_arrow(x1, y1, x2, y2, lbl=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#475569", lw=1.3, shrinkA=2, shrinkB=2), zorder=4)
        if lbl:
            ax.text((x1+x2)/2, (y1+y2)/2, lbl, fontsize=7, color="#0f172a",
                    bbox=dict(boxstyle="round,pad=0.15", fc="#ffffff", ec="#cbd5e1", lw=0.6), zorder=5)

    dfd_arrow(22, 61, 26.5, 75, "Raw Gradients")
    dfd_arrow(41.5, 75, 50.5, 75, "Bounded Evidence")
    dfd_arrow(58, 67.5, 58, 49.5, "Evaluated Set")
    dfd_arrow(50.5, 42, 41.5, 42, "Attested Set")
    dfd_arrow(78, 61, 41.5, 42, "Masked Tensors")
    dfd_arrow(34, 34.5, 16, 28, "Finalize Entry")
    dfd_arrow(28, 24, 42.5, 18, "Root & Proofs")
    dfd_arrow(57.5, 18, 78, 21, "Verification Status")

    out_file = OUT_DIR / "DFD AdvRAG.png"
    plt.savefig(out_file, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

# ----------------------------------------------------------------------
# 6. CAPTURE / GATHER UI SCREENSHOTS (1.png, 2.png, 3.png, 4.png)
# ----------------------------------------------------------------------
def gather_ui_screenshots():
    print("Gathering UI Screenshots...")
    # 1.png: Full research dashboard
    src_dash = Path("/Users/ayush/Downloads/Study/results/demo_decentralized_fl/figures/dashboard.png")
    if src_dash.exists():
        img = Image.open(src_dash)
        img.save(OUT_DIR / "1.png")
        print("Saved 1.png (Dashboard Overview)")

    # 2.png: Blockchain Timeline
    src_timeline = Path("/Users/ayush/Downloads/Study/results/demo_decentralized_fl/figures/blockchain_timeline.png")
    if src_timeline.exists():
        img = Image.open(src_timeline)
        img.save(OUT_DIR / "2.png")
        print("Saved 2.png (Blockchain Ledger Timeline)")

    # 3.png: Live web capture of the running platform UI
    env = os.environ.copy()
    env['PYTHONPATH'] = '/Users/ayush/Downloads/Study/src'
    proc = subprocess.Popen(
        ['.venv_mac/bin/python', '-m', 'uvicorn', 'bcflsrv.ui.app:app', '--host', '127.0.0.1', '--port', '8089'],
        cwd='/Users/ayush/Downloads/Study', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    try:
        chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        cmd = [
            chrome_bin, '--headless', '--disable-gpu', '--window-size=1280,850',
            f'--screenshot={OUT_DIR / "3.png"}', 'http://127.0.0.1:8089/'
        ]
        subprocess.run(cmd, check=True)
        print("Saved 3.png (Live Web Application Interface)")
    except Exception as e:
        print("Could not capture live UI, copying alternative:", e)
        Image.open(src_dash).save(OUT_DIR / "3.png")
    finally:
        proc.terminate()

    # 4.png: Accuracy vs. Round (PyTorch Training Convergence)
    src_acc = Path("/Users/ayush/Downloads/Study/results/demo_decentralized_fl/figures/accuracy_vs_round.png")
    if src_acc.exists():
        img = Image.open(src_acc)
        img.save(OUT_DIR / "4.png")
        print("Saved 4.png (Training Accuracy & Convergence)")

    # Average metrics & per-query metrics -> E1 and E4 plots
    src_e1 = Path("/Users/ayush/Downloads/Study/results/figures/e1a_payload_independence.png")
    if src_e1.exists():
        Image.open(src_e1).save(OUT_DIR / "average_metrics.png")
        print("Saved average_metrics.png (Model Size Invariance)")

    src_e4 = Path("/Users/ayush/Downloads/Study/results/figures/e4_disclosure_ladder.png")
    if src_e4.exists():
        Image.open(src_e4).save(OUT_DIR / "per_query_metrics.png")
        print("Saved per_query_metrics.png (Evidence Ladder Evaluation)")

if __name__ == "__main__":
    generate_gantt_chart()
    generate_system_diagram()
    generate_er_diagram()
    generate_uml_activity()
    generate_dfd_diagram()
    gather_ui_screenshots()
    print("All assets successfully generated!")
