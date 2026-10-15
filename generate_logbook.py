"""
12-Week Project Log Book Generator for BC-FL-SRV
SIES Graduate School of Technology (Autonomous), Navi Mumbai
Academic Year 2026-27 (Semester VII)
Project Implementation Period: 1 August 2026 to 5 October 2026

Group Members:
1. Ayush Lanke (Roll No: 123A7004)
2. Bhumi Beloshe (Roll No: 123A7005)
3. Sakshi Bhandare (Roll No: 123A7007)
"""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_cell_border(cell, **kwargs):
    """
    Set cell borders: top, bottom, left, right.
    kwargs: top={"sz": 4, "val": "single", "color": "000000"}
    """
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        edge_data = kwargs.get(edge)
        if edge_data:
            tag = 'w:{}'.format(edge)
            element = OxmlElement(tag)
            element.set(qn('w:val'), edge_data.get('val', 'single'))
            element.set(qn('w:sz'), str(edge_data.get('sz', 4)))
            element.set(qn('w:space'), '0')
            element.set(qn('w:color'), edge_data.get('color', 'auto'))
            tcBorders.append(element)
    tcPr.append(tcBorders)

def set_run_font(run, name="Times New Roman", size=12, bold=False, italic=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)

def add_p(doc, text="", size=12, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0, space_after=6, line_spacing=1.15):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    if text:
        run = p.add_run(text)
        set_run_font(run, size=size, bold=bold, italic=italic)
    return p

def add_header_field(doc, label, value):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    run1 = p.add_run(label + " ")
    set_run_font(run1, size=11, bold=True)
    run2 = p.add_run(value)
    set_run_font(run2, size=11, bold=False)
    return p

def add_section_box(doc, title, content):
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(2)
    run_t = p_title.add_run(title)
    set_run_font(run_t, size=11, bold=True)

    p_body = doc.add_paragraph()
    p_body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_body.paragraph_format.space_before = Pt(0)
    p_body.paragraph_format.space_after = Pt(6)
    p_body.paragraph_format.line_spacing = 1.15
    run_b = p_body.add_run(content)
    set_run_font(run_b, size=11, bold=False)

def build_logbook():
    doc = Document()

    # Set page layout to standard A4 with 1-inch margins
    for section in doc.sections:
        section.page_height = Inches(11.69)
        section.page_width = Inches(8.27)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.top_margin = Inches(0.9)
        section.bottom_margin = Inches(0.9)

    # ---------------------------------------------------------
    # COVER / TITLE PAGE OF LOG BOOK
    # ---------------------------------------------------------
    add_p(doc, "PROJECT LOG BOOK", size=18, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=18, space_after=12)
    add_p(doc, "DEPARTMENT OF COMPUTER ENGINEERING", size=13, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    add_p(doc, "SIES GRADUATE SCHOOL OF TECHNOLOGY (AUTONOMOUS)", size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_p(doc, "Affiliated to University of Mumbai", size=11, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_p(doc, "Nerul, Navi Mumbai – 400 706", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)

    add_p(doc, "PROJECT TITLE", size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_p(doc, "BC-FL-SRV: Verifiable Admission Decisions for Privacy-Preserving Federated Learning", size=13, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)

    add_p(doc, "Academic Year: 2026–27 (Semester VII)", size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    add_p(doc, "Project Duration: 1 August 2026 to 5 October 2026", size=11, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)

    add_p(doc, "PROJECT GUIDE", size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_p(doc, "Prof. ___________________________", size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)

    add_p(doc, "PROJECT GROUP MEMBERS", size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    tbl_team = doc.add_table(rows=4, cols=3)
    tbl_team.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_team.style = 'Table Grid'
    team_headers = ["Sr. No.", "Name of Student", "Roll Number"]
    for i, h in enumerate(team_headers):
        cell = tbl_team.rows[0].cells[i]
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        set_run_font(run, size=11, bold=True)

    members = [
        ("1", "Ayush Lanke", "123A7004"),
        ("2", "Bhumi Beloshe", "123A7005"),
        ("3", "Sakshi Bhandare", "123A7007")
    ]
    for row_idx, data in enumerate(members, start=1):
        for col_idx, text in enumerate(data):
            cell = tbl_team.rows[row_idx].cells[col_idx]
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_idx != 1 else WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(text)
            set_run_font(run, size=11, bold=False)

    doc.add_page_break()

    # ---------------------------------------------------------
    # 12 WEEKS LOG DATA (1 Aug 2026 to 5 Oct 2026)
    # ---------------------------------------------------------
    weeks = [
        {
            "week_num": "1",
            "date": "01 Aug 2026",
            "next_date": "07 Aug 2026",
            "activity_performed": (
                "We commenced the Stage-I work for our major project. In our initial team meeting, we thoroughly "
                "reviewed the academic project guidelines, timeline, and semester deliverables. We conducted our "
                "first literature review session focused on federated learning architectures and identified a critical "
                "unaddressed gap: while secure aggregation cryptographically conceals individual updates from the "
                "aggregator, it simultaneously prevents external verification of whether clients were legitimately admitted "
                "or arbitrarily omitted. We finalized our project scope and titled it 'BC-FL-SRV: Verifiable Admission Decisions "
                "for Privacy-Preserving Federated Learning'. We initialized our project environment with Python 3.13, PyTorch, "
                "and Git version control, enforcing strict project-local dependency isolation without relying on global packages."
            ),
            "resources": (
                "Python 3.13 virtual environment, Git version control, IEEE/ACM digital libraries for foundational federated learning papers."
            ),
            "outcome": (
                "Project title and scope defined. Initial project repository structured and committed to Git. Core problem definition "
                "document drafted detailing the accountability gap in secure aggregation."
            ),
            "activity_planned": (
                "Study recent systematizations of verifiable federated learning (PoPETs 2026) and formalize our project's mathematical threat model."
            )
        },
        {
            "week_num": "2",
            "date": "07 Aug 2026",
            "next_date": "13 Aug 2026",
            "activity_performed": (
                "We examined the latest systematization of knowledge on verifiable integrity claims for privacy-preserving federated "
                "learning (Rizzini et al., PoPETs 2026). We analyzed their integrity claim taxonomy (AG1: correct admission, AG2: "
                "correct aggregation, AG3: non-equivocation) and observed that existing solutions overwhelmingly concentrate on AG2 "
                "using expensive Zero-Knowledge Proofs or Trusted Execution Environments, while AG1 and AG3 are neglected despite "
                "being fundamentally lighter to verify. We formulated our falsifiable research hypothesis (RD-001): verifiable admission "
                "and non-equivocation can be achieved under secure aggregation using only cryptographic hashing and digital signatures, "
                "yielding verification overhead strictly independent of neural network model size."
            ),
            "resources": (
                "PoPETs 2026 survey papers, IACR cryptography archives, Whiteboard for protocol state diagrams."
            ),
            "outcome": (
                "Formalized threat model and research hypothesis document. Identified untrusted aggregator, malicious client, "
                "and colluding committee threat vectors."
            ),
            "activity_planned": (
                "Design the mathematical architecture of the append-only Merkle transparency log based on RFC 6962."
            )
        },
        {
            "week_num": "3",
            "date": "13 Aug 2026",
            "next_date": "19 Aug 2026",
            "activity_performed": (
                "We designed the ledger architecture for our verifiable federated learning protocol. We adopted the RFC 6962 standard "
                "for Merkle hash trees, which guarantees append-only transparency with logarithmic proof complexity. We mathematically "
                "derived the leaf hashing scheme (prefixing leaves with 0x00 to prevent second-preimage attacks) and intermediate node "
                "hashing (prefixing with 0x01). We specified the canonical data structures for four round events: client submissions, "
                "committee admission sets, aggregation commitments, and round finalizations. Each entry strictly chains the prior "
                "Merkle root, guaranteeing temporal linearity and non-equivocation."
            ),
            "resources": (
                "IETF RFC 6962 specification, Python cryptography packages, Cryptographic hash functions reference manual."
            ),
            "outcome": (
                "Architectural blueprint for the Merkle transcript module. Formal specification of length-prefixed domain-separated "
                "entry encodings to prevent cross-type collision attacks."
            ),
            "activity_planned": (
                "Implement the core RFC 6962 Merkle tree library and build comprehensive adversarial unit test suites."
            )
        },
        {
            "week_num": "4",
            "date": "19 Aug 2026",
            "next_date": "25 Aug 2026",
            "activity_performed": (
                "We implemented the core RFC 6962 Merkle tree module in Python. We developed the tree builder, leaf commitment hasher, "
                "logarithmic inclusion proof generator, and append-only consistency proof calculator. We wrote an exhaustive test suite "
                "covering 124 unit test cases with 100% line coverage. Our tests specifically exercised adversarial edge cases, including "
                "in-place byte modifications, leaf deletions, leaf reordering, truncated proof paths at every prefix length, padded proofs, "
                "and mismatched tree roots. We ensured all verification routines fail closed and never raise uncaught runtime exceptions "
                "when receiving malformed or attacker-crafted bytes."
            ),
            "resources": (
                "Python 3.13 standard libraries, hashlib, pytest testing framework, pytest-cov coverage tools."
            ),
            "outcome": (
                "Production-ready RFC 6962 Merkle tree module passing all 124 unit and adversarial verification tests with 100% code coverage."
            ),
            "activity_planned": (
                "Implement cryptographic identity management using Ed25519 digital signatures and verifiable committee sortition."
            )
        },
        {
            "week_num": "5",
            "date": "25 Aug 2026",
            "next_date": "31 Aug 2026",
            "activity_performed": (
                "We developed the cryptographic identity and verifiable sortition subsystems. We implemented Ed25519 digital signature "
                "generation and verification for all participating entities (clients, committee members, and aggregator) using the Python "
                "cryptography library. We designed a deterministic committee sortition algorithm that selects an active attestation "
                "committee from the registered participant pool. The sortition pseudorandom seed is derived directly from the prior "
                "round's finalized Merkle root, ensuring that neither the aggregator nor any client can manipulate committee selection "
                "without altering historical round records. We also formulated the hypergeometric statistical model to quantify committee "
                "corruption probabilities across varying adversary fractions."
            ),
            "resources": (
                "Python cryptography library (Ed25519 primitive), SciPy hypergeometric distribution functions, Git repository."
            ),
            "outcome": (
                "Operational cryptographic identity module and verifiable sortition engine. Unit test suite confirming deterministic "
                "and reproducible committee derivation from transcript roots."
            ),
            "activity_planned": (
                "Design the bounded evidence disclosure ladder (E0 to E4) and implement admission decision rules."
            )
        },
        {
            "week_num": "6",
            "date": "31 Aug 2026",
            "next_date": "07 Sep 2026",
            "activity_performed": (
                "We formulated and implemented the bounded evidence encoding ladder to resolve the tension between client privacy and "
                "Byzantine detection. We defined five discrete evidence disclosure levels: E0 (cryptographic commitment only, zero "
                "disclosure), E1 (scalar gradient norm), E2 (binned directional histogram), E3 (randomized Johnson-Lindenstrauss low-dimensional "
                "projection sketch), and E4 (full plaintext update). We implemented two generations of admission rules: G1 (a threshold-based "
                "norm filter) and G2 (an orthogonal evaluation combining bounded gradient norm check with low-dimensional directional cosine "
                "consistency against a running reference trajectory). This allows committee members to audit update validity without "
                "reconstructing private client datasets."
            ),
            "resources": (
                "NumPy for vector projections and cosine similarity, PyTorch tensors, SIES college laboratory workstations."
            ),
            "outcome": (
                "Five-tier evidence encoding library and admission rule engine (G1 and G2). Validated evidence bounds and serialization schemas."
            ),
            "activity_planned": (
                "Implement the threshold attestation protocol and construct the external auditor verification module."
            )
        },
        {
            "week_num": "7",
            "date": "07 Sep 2026",
            "next_date": "14 Sep 2026",
            "activity_performed": (
                "We developed the threshold attestation protocol and the external auditor engine. In our protocol, committee members "
                "independently inspect each submission's bounded evidence against the declared admission rule, form an admission set, "
                "and generate individual Ed25519 signatures over the admission set digest. The aggregator must collect at least a "
                "threshold t of m valid signatures before proceeding to aggregation. We then constructed the external auditor module: "
                "given only the public Merkle transcript, the auditor verifies that the recorded admission set is validly co-signed by "
                "the sortition-selected committee (AG1) and checks root consistency to confirm that the aggregator did not branch or "
                "equivocate across rounds (AG3)."
            ),
            "resources": (
                "Python Ed25519 verification pipelines, Merkle transcript interface, Pytest automated testing suite."
            ),
            "outcome": (
                "Complete threshold attestation and external auditor verification modules. Tested auditor verification under simulated "
                "tampering, signature omission, and signature forgery."
            ),
            "activity_planned": (
                "Integrate the core protocol with an end-to-end federated learning pipeline on Fashion-MNIST dataset."
            )
        },
        {
            "week_num": "8",
            "date": "14 Sep 2026",
            "next_date": "21 Sep 2026",
            "activity_performed": (
                "We integrated our verifiable admission protocol into an end-to-end federated learning simulation. We implemented a "
                "convolutional neural network (SmallCNN) and configured the Fashion-MNIST benchmark dataset. To simulate realistic "
                "heterogeneous edge conditions, we implemented Dirichlet non-IID data partitioning with concentration parameter alpha = 0.5 "
                "across five federated clients. We incorporated additive secure aggregation masking, ensuring the central aggregator "
                "only observes the sum of masked client tensors and cannot inspect individual updates. We conducted our first complete "
                "training run of 10 federated rounds, successfully reaching 83.88% test classification accuracy with verifiable admission sets."
            ),
            "resources": (
                "PyTorch 2.12 (CPU execution), torchvision Fashion-MNIST dataset, Multi-core CPU compute workstation."
            ),
            "outcome": (
                "Functional federated learning pipeline running end-to-end with verifiable admission and secure aggregation, achieving "
                "83.88% test accuracy under non-IID Dirichlet distribution."
            ),
            "activity_planned": (
                "Implement adversarial attack generators to benchmark Byzantine resilience and tamper detection capabilities."
            )
        },
        {
            "week_num": "9",
            "date": "21 Sep 2026",
            "next_date": "26 Sep 2026",
            "activity_performed": (
                "We designed and implemented a comprehensive suite of adversarial attacks targeting both the machine learning and the "
                "cryptographic verification layers. We implemented gradient sign-flip attacks, Gaussian noise injection, label-flipping "
                "attacks, and sophisticated slow-drift evasion attacks (a variant of 'A Little Is Enough'). On the protocol side, we "
                "implemented attacks for selective client dropping, Merkle root equivocation, post-hoc admission set modification, "
                "unauthorized client injection, replay of expired submissions, and sortition seed grinding. We confirmed that our "
                "system successfully intercepts and isolates invalid updates before model aggregation."
            ),
            "resources": (
                "PyTorch gradient manipulation tools, Attack simulation scripts, Pytest verification suite."
            ),
            "outcome": (
                "Adversarial attack harness with 14 distinct attack vectors covering both machine learning poisoning and cryptographic "
                "transcript manipulation."
            ),
            "activity_planned": (
                "Conduct Experiment E-1 (verification cost scaling vs model size) and Experiment E-2 (tamper detection benchmark)."
            )
        },
        {
            "week_num": "10",
            "date": "26 Sep 2026",
            "next_date": "30 Sep 2026",
            "activity_performed": (
                "We executed formal benchmarks for Experiment E-1 and Experiment E-2. In E-1, we measured auditor verification time "
                "across model parameter sizes ranging from 64 bytes to 4 MiB (a 65,536-fold size range). We empirically demonstrated "
                "that inclusion check time remained virtually constant (1.55 microseconds at 64 B vs 1.59 microseconds at 4 MiB, a 1.03x "
                "ratio), validating our core claim that verification overhead is independent of model size N. In E-2, we evaluated tamper "
                "detection against 14 attack scenarios. BC-FL-SRV correctly detected 12 out of 14 attacks with 0 false positives on honest "
                "rounds, outperforming traditional signed-log (5/14) and self-attestation (6/14) baselines."
            ),
            "resources": (
                "High-resolution Python time_ns benchmarking utilities, Matplotlib data visualization libraries, SIES lab systems."
            ),
            "outcome": (
                "Empirical proof of O(1) verification cost scaling relative to model size. Comprehensive detection benchmark table showing "
                "12/14 attacks detected with zero false alarms on honest participants."
            ),
            "activity_planned": (
                "Execute Experiment E-3 (committee corruption probability) and Experiments E-4/E-5 (privacy-detection trade-off curve)."
            )
        },
        {
            "week_num": "11",
            "date": "30 Sep 2026",
            "next_date": "03 Oct 2026",
            "activity_performed": (
                "We conducted experimental evaluations for committee corruption dynamics (E-3) and the privacy-detection trade-off (E-4/E-5). "
                "We ran 10,000 Monte Carlo sortition iterations across varying malicious fractions (10% to 40%) and committee sizes (m = 3 to 15), "
                "confirming that empirical corruption frequencies matched our theoretical hypergeometric model within 3 standard deviations. "
                "In E-4 and E-5, we evaluated the G2 rule across evidence levels and demonstrated that verifiable admission introduces "
                "exactly zero accuracy loss compared to an idealized trusted-server baseline (0.0e+00 difference). We also documented "
                "an honest limitation: under slow-drift evasion, low-magnitude adversarial updates remain geometrically inside the admission "
                "boundary, bounding our security claims realistically."
            ),
            "resources": (
                "NumPy statistical simulation routines, Matplotlib graphing scripts, Tabulated benchmark logs."
            ),
            "outcome": (
                "Validated committee corruption probability curves. Quantified privacy-detection trade-off and confirmed zero machine "
                "learning utility penalty from our verification mechanism."
            ),
            "activity_planned": (
                "Perform full test suite regression, calculate final test coverage, and compile the Stage-I Project Report."
            )
        },
        {
            "week_num": "12",
            "date": "05 Oct 2026",
            "next_date": "Stage-I Examination / Stage-II Phase Kick-off",
            "activity_performed": (
                "We finalized all deliverables for the Stage-I major project review. We executed the complete automated test suite, "
                "achieving a total of 366 passing tests with 99% overall line coverage across our core codebase. We verified that all "
                "cryptographic verifiers fail closed when supplied with malformed inputs. We formatted our comprehensive Stage-I "
                "Project Report in strict compliance with the college formatting guidelines (Times New Roman, 1.5 line spacing, standard "
                "margins, approved chapter structure). We compiled all experimental data, architectural diagrams, literature tables, "
                "and reference citations. Finally, we prepared our Stage-I presentation slides and organized our weekly logbook records."
            ),
            "resources": (
                "Pytest 9.1.1, Coverage analysis report, Microsoft Word / python-docx formatting tools, Presentation software."
            ),
            "outcome": (
                "Completed Stage-I Project Report, finalized 12-week project log book, 366 passing test cases with 99% code coverage, "
                "and full readiness for Semester VII Stage-I project viva and evaluation."
            ),
            "activity_planned": (
                "Prepare for Stage-I project examination and viva; outline Stage-II ablation studies and multi-auditor gossip experiments."
            )
        }
    ]

    for w in weeks:
        # Header line: Week No: [number] \t Date: [date]
        p_hdr = doc.add_paragraph()
        p_hdr.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_hdr.paragraph_format.space_before = Pt(4)
        p_hdr.paragraph_format.space_after = Pt(4)
        run_wn = p_hdr.add_run(f"Week No: {w['week_num']}")
        set_run_font(run_wn, size=11, bold=True)
        run_tab = p_hdr.add_run("\t\t\t\t\t\t\t\t")
        set_run_font(run_tab, size=11, bold=False)
        run_dt = p_hdr.add_run(f"Date: {w['date']}")
        set_run_font(run_dt, size=11, bold=True)

        # Activity performed
        add_section_box(doc, "ACTIVITY PERFORMED:", w['activity_performed'])

        # Resources utilized
        add_section_box(doc, "RESOURCES UTILIZED IF ANY:", w['resources'])

        # Outcome
        add_section_box(doc, "OUTCOME:", w['outcome'])

        # Next date of meeting
        add_header_field(doc, "NEXT DATE OF MEETING:", w['next_date'])

        # Activity planned
        add_section_box(doc, "ACTIVITY PLANNED:", w['activity_planned'])

        # Guide signature line
        p_sig = doc.add_paragraph()
        p_sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_sig.paragraph_format.space_before = Pt(14)
        p_sig.paragraph_format.space_after = Pt(4)
        run_line = p_sig.add_run("_______________________________\nSignature of Guide          ")
        set_run_font(run_line, size=10, bold=False)

        # Team member signature table matching format (4 rows x 3 cols)
        tbl_sig = doc.add_table(rows=4, cols=3)
        tbl_sig.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl_sig.style = 'Table Grid'
        headers = ["Name of Group Members", "Roll no", "Signature"]
        for ci, h in enumerate(headers):
            cell = tbl_sig.rows[0].cells[ci]
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(h)
            set_run_font(run, size=10, bold=True)

        team_rows = [
            ("Ayush Lanke", "123A7004"),
            ("Bhumi Beloshe", "123A7005"),
            ("Sakshi Bhandare", "123A7007")
        ]
        for ri, (m_name, m_roll) in enumerate(team_rows, start=1):
            c0 = tbl_sig.rows[ri].cells[0]
            p0 = c0.paragraphs[0]
            p0.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run0 = p0.add_run(m_name)
            set_run_font(run0, size=10, bold=False)

            c1 = tbl_sig.rows[ri].cells[1]
            p1 = c1.paragraphs[0]
            p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run1 = p1.add_run(m_roll)
            set_run_font(run1, size=10, bold=False)

            c2 = tbl_sig.rows[ri].cells[2]
            p2 = c2.paragraphs[0]
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # signature cell left blank for physical signature

        # Add page break after each week except the last one
        if w['week_num'] != "12":
            doc.add_page_break()

    out_file = "/Users/ayush/Downloads/Study/Logbook_12Weeks_BC-FL-SRV.docx"
    doc.save(out_file)
    print(f"Log book successfully generated at: {out_file}")

if __name__ == "__main__":
    build_logbook()
