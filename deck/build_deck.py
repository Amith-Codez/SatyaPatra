"""Builds the SatyaPatra SIH 2026 idea deck on the official SIH2026 template (v2).

Keeps the template's logos, footer, slide titles and every "idea details pointer" word for word
(template rule 5), removes the instructions slide (template note), and fills each slide with
real prototype screenshots, measured results and sourced facts.

Run:  python build_deck.py   ->  SatyaPatra_SIH26261_Idea.pptx
"""
import json
import re

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from deck_helpers import (BAD, BG, BLUE, INK, LINE, MUTED, NAVY, OK, WARN, WHITE, box, circle, delete_slide, notes,
                          pointer, remove_shape, set_runs_text, set_team_oval, set_title, shape_by_name, table, text)

TEMPLATE = "SIH2026-official-template.pptx"
OUT = "SatyaPatra_SIH26261_Idea.pptx"
TEAM_NAME = "[Team Name]"   # fill before export: must not contain the college name
TEAM_ID = "[Team ID]"
EVAL = json.load(open("../satyapatra/backend/data/eval/results.json"))
SAFFRON = "B8640F"
from PIL import Image as _I
_l = _I.open("img/ladder.png")
LADDER_RATIO = _l.height / _l.width


def rich(s, size=10, color=INK, accent=BLUE, bullet=True, space_after=3):
    """'**bold**' segments become bold accent text: the one keyword the evaluator should see in each line."""
    runs = []
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", s)):
        if part:
            runs.append((part, {"bold": True, "color": accent} if i % 2 else {}))
    return {"runs": runs, "bullet": bullet, "space_after": space_after, "size": size, "color": color}


prs = Presentation(TEMPLATE)
delete_slide(prs, 6)  # "Important instructions" slide; the template says it can be deleted
s1, s2, s3, s4, s5, s6 = prs.slides
for s in (s2, s3, s4, s5, s6):
    set_team_oval(s)

# ================================================================ 1. TITLE PAGE
sub = shape_by_name(s1, "Subtitle")
for p in sub.text_frame.paragraphs:
    if p.runs:
        set_runs_text(p, "SatyaPatra")
        break
tb = shape_by_name(s1, "TextBox 9")
values = ["Problem Statement ID – SIH26261",
          "Problem Statement Title – AI-Powered Application Validation, Document Authentication and Regulatory Compliance Verification",
          "Theme – Smart Automation", "PS Category – Software", f"Team ID – {TEAM_ID}",
          f"Team Name (Registered on portal) – {TEAM_NAME}"]
for p, v in zip([p for p in tb.text_frame.paragraphs if p.text.strip()], values):
    set_runs_text(p, v)
    p.alignment = PP_ALIGN.LEFT
    p.line_spacing = 1.05
    p.space_after = Pt(10)
    for r in p.runs:
        r.font.size = Pt(17)
notes(s1, "One line per member. Say: PS SIH26261 from AICTE, Smart Automation, software.")

# ================================================================ 2. IDEA TITLE
set_title(s2, "SatyaPatra")
remove_shape(shape_by_name(s2, "TextBox 8"))
text(s2, 1.9, 0.98, 8.7, 0.32, [{"runs": [("Every AICTE approval document, confirmed with the authority that issued it, with the proof on screen",
                                             {"italic": True, "color": NAVY, "size": 12.5})], "align": PP_ALIGN.CENTER}])
pointer(s2, 0.4, 1.34, 8.9, "❖ Proposed Solution (Describe your Idea/Solution/Prototype)", size=14)

cols = [
    ("Detailed explanation of the proposed solution", 2.95, [
        "Reads every upload: PDF text with positions, **OCR** for scans and photos",
        "Applies the **APH 2024-27 rulebook**: missing, expired, below-norm, mismatched",
        "**Asks the issuer**: signature, issuer portal, or a one-click confirm link",
        "Finds **tampering**: white patches, edits after signing, fake seals",
        "Gives **1 of the 6 PS statuses**, risk 0-100, evidence boxed on the page",
    ]),
    ("How it addresses the problem", 2.95, [
        "Today a forged NOC passes until someone checks by hand: Hyderabad police booked **8 junior colleges** after **76 fire NOCs** were sent back to the issuer (Aug 2026)",
        "SatyaPatra makes that check the **default for every document, in under a second**",
        "Officers start with the **riskiest files**; every flag cites its rule and source",
    ]),
    ("Innovation and uniqueness of the solution", 2.75, [
        "**Verify at source**, 3 tiers; never trusts a QR or phone printed on the document",
        "**Cross-institution memory**: same seal scan or faculty at two colleges",
        "**Satellite reality check** of built-up area",
        "**Seal-specimen matching** (ORB + RANSAC)",
        "**On-prem AI**, ₹0 licence, data stays with AICTE",
    ]),
]
x = 0.4
for hdr, w, items in cols:
    box(s2, x, 1.72, w, 3.13, fill=BG, line=LINE)
    text(s2, x + 0.08, 1.77, w - 0.16, 0.48, [{"runs": [(hdr, {"bold": True, "color": NAVY, "size": 11.5})]}])
    text(s2, x + 0.08, 2.26, w - 0.16, 2.55, [rich(t, size=10) for t in items])
    x += w + 0.12
_ev = _I.open("img/shot_evidence.png")
_evw = min(3.51, 2.3 * _ev.width / _ev.height)
s2.shapes.add_picture("img/shot_evidence.png", Inches(9.42 + (3.51 - _evw) / 2), Inches(1.34), width=Inches(_evw))
text(s2, 9.42, 3.68, 3.51, 0.25, [{"runs": [("Working prototype (UX4G-based console): forged NOC flagged; numbered boxes mark the evidence",
                                              {"italic": True, "color": MUTED, "size": 8.5})]}])
box(s2, 9.42, 3.98, 3.51, 0.87, fill="EAF6F0", line="BFE3D1")
f, g = EVAL["forged"], EVAL["genuine"]
text(s2, 9.5, 4.02, 3.35, 0.8, [
    {"runs": [(f"{round(EVAL['catch_rate'] * f)}/{f}", {"bold": True, "color": OK, "size": 17}),
              ("  forgeries caught   ", {"size": 9.5, "color": INK}),
              (f"0/{g}", {"bold": True, "color": OK, "size": 17}), ("  false alarms", {"size": 9.5})]},
    {"runs": [(f"{EVAL['median_ms_pdf'] / 1000:.2f} s per PDF on a laptop CPU · 195 labelled test documents", {"size": 8.5, "color": MUTED})]},
], anchor=MSO_ANCHOR.MIDDLE)
s2.shapes.add_picture("img/pipeline.png", Inches(0.4), Inches(5.0), width=Inches(12.53))
text(s2, 0.4, 6.4, 12.53, 0.3, [{"runs": [
    ("Demo video: ", {"bold": True, "color": NAVY}), ("[add unlisted link]", {"color": MUTED}),
    ("     Live prototype: ", {"bold": True, "color": NAVY}), ("[add link]", {"color": MUTED}),
    ("     Code: ", {"bold": True, "color": NAVY}), ("[add GitHub link]", {"color": MUTED})]}], size=10)
notes(s2, "30 seconds. Open with Hyderabad: 76 fire NOCs checked by hand, 8 colleges booked. "
          "SatyaPatra does that check for every document at upload. Point at the screenshot: the red boxes are the evidence. "
          "Point at the green box: measured, not promised. Close: the officer decides; we make sure they decide on the truth.")

# ================================================================ 3. TECHNICAL APPROACH
remove_shape(shape_by_name(s3, "TextBox 8"))
pointer(s3, 0.4, 1.22, 4.75, "Technologies to be used (e.g. programming languages, frameworks, hardware)", size=11.5, h=0.45)
stack = [
    "**FastAPI · Python 3.12**: typed async API; Python owns document AI (vs Node.js: weak PDF and vision libraries)",
    "**PostgreSQL 16 (+ PostGIS at scale)**: ACID evidence records; the demo runs the same code on SQLite (vs MongoDB: weak joins for audit-grade records)",
    "**Redis + RQ workers**: add workers in approval season (vs Celery: heavier; Kafka: overkill at this scale)",
    "**MinIO (S3) on NIC / MeghRaj**: originals stored by SHA-256, encrypted (vs local disk: does not scale)",
    "**RapidOCR (PP-OCR models, ONNX)**: CPU, layout-robust, Apache-2.0 (vs cloud OCR: data leaves AICTE)",
    "**pyHanko**: validates PAdES signatures to the issuer's certificate; detects edits after signing",
    "**OpenCV ORB + RANSAC**: rotation-proof seal matching (vs image hashes: in our tests fakes scored as close as genuine)",
    "**Ollama + Llama 3.2 3B**: local AI only for unfamiliar layouts, every value grounded (vs cloud LLM APIs: data leaves, per-token cost)",
    "**React 18 + TypeScript on UX4G 3.0 tokens**: the Government of India design system, Noto Sans, accessibility bar (vs a custom look: no GIGW alignment)",
    "**Role-based sign-in + SHA-256 hash chain**: government SSO via OIDC; tamper-evident log (vs blockchain: same proof, no cost)",
]
text(s3, 0.4, 1.72, 4.75, 4.45, [rich(t, size=9.8, space_after=4.5) for t in stack])
box(s3, 0.4, 6.25, 4.75, 0.5, fill=OK, line=None, radius=0.2)
text(s3, 0.45, 6.27, 4.65, 0.46, [{"runs": [("100% open source  ·  ₹0 licence  ·  CPU only, no GPU", {"bold": True, "color": WHITE, "size": 11.5})],
                                  "align": PP_ALIGN.CENTER}], anchor=MSO_ANCHOR.MIDDLE)
pointer(s3, 5.35, 1.22, 7.58, "Methodology and process for implementation (Flow Charts/Images/ working prototype)", size=11.5)
s3.shapes.add_picture("img/architecture2.png", Inches(5.35), Inches(1.55), width=Inches(7.58))
_a = _I.open("img/shot_verify.png"); _b = _I.open("img/shot_geo.png")
_ra, _rb = _a.width / _a.height, _b.width / _b.height
_h = min(1.52, (7.58 - 0.12) / (_ra + _rb))
s3.shapes.add_picture("img/shot_verify.png", Inches(5.35), Inches(3.98), height=Inches(_h))
s3.shapes.add_picture("img/shot_geo.png", Inches(5.35 + _ra * _h + 0.12), Inches(3.98), height=Inches(_h))
text(s3, 5.35, 5.53, 7.58, 0.26, [{"runs": [("Working prototype: a forged NOC checked in 0.26 s, issuer lookup included (left); claimed built-up area vs building footprints (right)",
                                              {"italic": True, "color": MUTED, "size": 8.5})]}])
steps = [("1  Built", "5 engines, issuer sandbox, console, 6 passing tests"),
         ("2  Measured", "195 labelled documents, 8 forgery types"),
         ("3  Pilot", "Our college's EoA, then one regional office")]
sw = (7.58 - 2 * 0.1) / 3
for i, (h, d) in enumerate(steps):
    xx = 5.35 + i * (sw + 0.1)
    box(s3, xx, 5.88, sw, 0.87, fill="EEF0FC", line="DDE1FA")
    text(s3, xx + 0.08, 5.92, sw - 0.16, 0.8, [{"runs": [(h, {"bold": True, "color": NAVY, "size": 11})]},
                                               {"runs": [(d, {"size": 9.5})]}])
notes(s3, "Left: every choice has a reason and a rejected alternative; ask us about any of them. "
          "Right: the portal sends documents to our API, a queue feeds five engines, results land in Postgres and the ledger. "
          "The two screenshots are the running prototype.")

# ================================================================ 4. FEASIBILITY AND VIABILITY
remove_shape(shape_by_name(s4, "TextBox 8"))
pointer(s4, 0.4, 1.22, 8.0, "Analysis of the feasibility of the idea")
tiles = [("Technical", "Built and running today; every part is mature open source", BLUE),
         ("Economic", "₹0 licence, no per-document fee, runs on existing NIC cloud", OK),
         ("Operational", "Plugs in beside the AICTE portal; officers keep the decision", NAVY),
         ("Legal & data", "On-prem, role-based, salted ID hashes; built for DPDP Act 2023", SAFFRON)]
tw = (8.0 - 3 * 0.12) / 4
for i, (h, d, col) in enumerate(tiles):
    xx = 0.4 + i * (tw + 0.12)
    box(s4, xx, 1.55, tw, 0.95, fill=BG, line=LINE)
    text(s4, xx + 0.08, 1.58, tw - 0.16, 0.3, [{"runs": [(h, {"bold": True, "color": col, "size": 11.5})]}])
    text(s4, xx + 0.08, 1.87, tw - 0.16, 0.62, [d], size=9.5)
box(s4, 0.4, 2.6, 8.0, 1.05, fill="EAF6F0", line="BFE3D1")
nums = [(f"{f}/{f}", "forgeries caught"), (f"0/{g}", "false alarms"),
        (f"{EVAL['median_ms_pdf'] / 1000:.2f} s", "per PDF, laptop CPU"), ("6 of 8", "forgery types hit by 2+ independent signals")]
nw = 8.0 / 4
for i, (n, l) in enumerate(nums):
    text(s4, 0.45 + i * nw, 2.62, nw - 0.1, 0.72, [{"runs": [(n, {"bold": True, "color": OK, "size": 20})]},
                                                   {"runs": [(l, {"size": 9.2, "color": INK})]}])
text(s4, 0.5, 3.36, 7.8, 0.27, [{"runs": [("Measured on our labelled test set (195 synthetic documents, forgery types modelled on reported cases). "
                                            "The pilot measures real-world rates.", {"italic": True, "size": 8.5, "color": MUTED})]}])
pointer(s4, 0.4, 3.74, 3.4, "Potential challenges and risks", size=11.5)
pointer(s4, 3.85, 3.74, 4.6, "Strategies for overcoming these challenges", size=11.5)
risks = [["Challenge or risk", "Strategy"],
         ["Genuine document flagged by mistake", "Soft signals alone never mark a forgery; evidence shown; institution can reply"],
         ["Issuer has no API (a city fire office)", "3-tier ladder; no reply within SLA goes to manual review"],
         ["Phone scans and photographed documents", "OCR built in (0/15 false alarms on phone scans); unclear or handwritten fields go to manual review"],
         ["Forgers adapt to the detector", "Issuer confirmation cannot be faked; detector is one signal of many"],
         ["Approval-season peak load", "Queue + more workers; issuer answers cached; ~0.14 s per PDF"],
         ["Handbook changes every cycle", "Rules in YAML with clause IDs, versioned by year, no code change"]]
table(s4, 0.4, 4.03, 8.0, [3.2, 4.8], risks, size=9.2, row_h=0.39)
s4.shapes.add_picture("img/ladder.png", Inches(8.62), Inches(1.22), width=Inches(4.3))
LAD_H = 4.3 * LADDER_RATIO
box(s4, 8.62, 1.22 + LAD_H + 0.12, 4.3, 6.8 - (1.22 + LAD_H + 0.12), fill=BG, line=LINE)
text(s4, 8.72, 1.22 + LAD_H + 0.17, 4.1, 6.7 - (1.22 + LAD_H + 0.17), [
    {"runs": [("Viability", {"bold": True, "color": NAVY, "size": 12})]},
    rich("**Pilot**: our college's EoA (with permission), then one AICTE regional office, then national", size=9.8),
    rich("**Reuse**: UGC, NCTE, PCI and state boards face the same forged-certificate problem", size=9.8),
    rich("**Sustainable**: open source under AICTE; no vendor lock-in", size=9.8),
    rich("**Scale estimate**: if ~9,000 institutions send ~30 documents each, ~2.7 lakh documents at ~1 s each take under 2 days on 32 CPU cores", size=9.8),
])
notes(s4, "Say the false-positive answer first, judges always ask it. Then the green band: measured, with the caveat. "
          "Right side: the three tiers explain how we confirm even when an issuer has no API.")

# ================================================================ 5. IMPACT AND BENEFITS
remove_shape(shape_by_name(s5, "TextBox 8"))
pointer(s5, 0.4, 1.22, 6.1, "Potential impact on the target audience")
aud = [("S", "Students and parents", "Real labs, real faculty and fire-safe buildings behind every approval", BLUE),
       ("A", "AICTE officers", "Start with the riskiest files; routine checks automated; decisions backed by evidence", NAVY),
       ("I", "Honest institutions", "Self-check before submitting; fewer deficiency rounds; faster approval", OK),
       ("R", "Issuing authorities", "Forged copies of their certificates caught early; one-click confirmation", SAFFRON)]
for i, (ic, h, d, col) in enumerate(aud):
    y = 1.6 + i * 0.86
    circle(s5, 0.45, y + 0.06, 0.5, col, ic, size=14)
    text(s5, 1.1, y, 5.4, 0.8, [{"runs": [(h, {"bold": True, "color": NAVY, "size": 12})]}, d], size=10.5)
pointer(s5, 6.75, 1.22, 6.2, "Benefits of the solution (social, economic, environmental, etc.)")
ben = [("Social", ["Fire, building and lab claims actually checked", "Students get the faculty they pay for",
                   "Approved degrees stay trustworthy"], BLUE),
       ("Economic", ["Officer hours saved on routine checks", "Public money not lost to fake institutions or fake FDRs",
                     "₹0 licence, no per-document fee"], OK),
       ("Environmental", ["Paperless verification end to end", "Fewer courier and travel trips to re-verify",
                          "Satellite screening before any site visit"], "2E7D32"),
       ("Governance", ["Same rules for every application", "Tamper-evident record of every decision",
                       "Reusable by UGC, NCTE, PCI, state boards"], NAVY)]
bw, bh = 3.02, 1.62
for i, (h, d, col) in enumerate(ben):
    xx = 6.75 + (i % 2) * (bw + 0.14)
    y = 1.58 + (i // 2) * (bh + 0.12)
    box(s5, xx, y, bw, bh, fill=BG, line=LINE)
    text(s5, xx + 0.1, y + 0.08, bw - 0.2, 0.3, [{"runs": [(h, {"bold": True, "color": col, "size": 12.5})]}])
    text(s5, xx + 0.1, y + 0.42, bw - 0.2, bh - 0.46, [{"runs": [(t, {})], "bullet": True, "space_after": 2} for t in d], size=10.5)
text(s5, 0.4, 5.1, 12.5, 0.3, [{"runs": [("Why it matters: reported cases", {"bold": True, "color": NAVY, "size": 12})]}])
stats = [("8 of 76", "fire NOCs sent back for checking led to 8 Hyderabad junior colleges being booked for forgery (Siasat, Aug 2026)"),
         ("1 in 3", "technical institutes were caught filing false data for AICTE approval (Hindustan Times, Apr 2017)"),
         ("353", "full-time faculty on the payrolls of 2 to 11 engineering colleges at once (DT Next, Jul 2024)"),
         ("₹144 Cr", "in scholarships went to 830 fake or non-operational institutions (CBI FIR via Scroll, FY18-FY22)")]
sw = (12.53 - 3 * 0.14) / 4
for i, (n, d) in enumerate(stats):
    xx = 0.4 + i * (sw + 0.14)
    box(s5, xx, 5.42, sw, 1.38, fill=WHITE, line=LINE)
    text(s5, xx + 0.1, 5.44, sw - 0.2, 0.5, [{"runs": [(n, {"bold": True, "color": BAD, "size": 22})]}])
    text(s5, xx + 0.1, 5.95, sw - 0.2, 0.85, [d], size=9.3, color=INK)
notes(s5, "Who benefits, then the four numbers. Each number has a source on the card; do not round them up.")

# ================================================================ 6. RESEARCH AND REFERENCES
remove_shape(shape_by_name(s6, "TextBox 8"))
pointer(s6, 0.4, 1.22, 12.5, "Details / Links of the reference and research work")
text(s6, 0.4, 1.55, 6.6, 0.3, [{"runs": [("How SatyaPatra compares with what exists today", {"bold": True, "color": NAVY, "size": 11.5})]}])
Y, N, P = ("Yes", OK), ("No", BAD), ("Partly", WARN)
cmp_rows = [["", "Manual scrutiny", "DigiLocker", "Paid KYC / forgery APIs", "Generic OCR", "SatyaPatra"],
            ["Confirms with the issuer", P, ("Its own docs", WARN), ("ID docs", WARN), N, Y],
            ["NOC, lease, FDR, affidavit", Y, ("Few", WARN), N, ("Extracts", WARN), Y],
            ["Evidence for every flag", ("Varies", WARN), ("n/a", MUTED), ("Score", WARN), N, Y],
            ["Memory across institutions", N, N, N, N, Y],
            ["Checks buildings and photos", ("Visits", WARN), N, N, N, ("Screens", OK)],
            ["No per-document fee", Y, Y, ("Paid", BAD), ("Paid", BAD), Y]]
table(s6, 0.4, 1.9, 6.6, [1.85, 0.9, 0.9, 1.1, 0.85, 1.0], cmp_rows, size=9, row_h=0.4)
text(s6, 0.4, 4.85, 6.6, 1.95, [
    {"runs": [("What we learned from earlier SIH work", {"bold": True, "color": NAVY, "size": 11.5})]},
    rich("SIH 2024: an **AI-supported AICTE approval portal** (K L University) automated the workflow. We verify what flows through it", size=9.8),
    rich("SIH 2022 (official winners list): **AICTE one-point student/faculty verification**; **CertiSetu** scholarship verification", size=9.8),
    {"runs": [("Stakeholder input: [add one line from your college's AICTE coordinator]", {"color": MUTED})], "bullet": True, "size": 9.8},
])
refs = [
    ("PS SIH26261, AICTE (sih.gov.in)", "https://sih.gov.in/sih2026PS"),
    ("AICTE Approval Process Handbook 2024-27", "https://aicte.gov.in"),
    ("Qu et al., Robust Tampered Text Detection in Document Images (DocTamper), CVPR 2023", "https://openaccess.thecvf.com/content/CVPR2023/html/Qu_Towards_Robust_Tampered_Text_Detection_in_Document_Image_New_Dataset_CVPR_2023_paper.html"),
    ("Rublee et al., ORB: an efficient alternative to SIFT or SURF, ICCV 2011, doi:10.1109/ICCV.2011.6126544", "https://doi.org/10.1109/ICCV.2011.6126544"),
    ("Fischler & Bolles, Random Sample Consensus, CACM 1981, doi:10.1145/358669.358692", "https://doi.org/10.1145/358669.358692"),
    ("Du et al., PP-OCR: a practical ultra lightweight OCR system, arXiv:2009.09941", "https://arxiv.org/abs/2009.09941"),
    ("Sirko et al., Continental-scale building detection (Open Buildings), arXiv:2107.12283", "https://arxiv.org/abs/2107.12283"),
    ("ETSI EN 319 142 (PAdES): PDF digital signatures", "https://www.etsi.org/"),
    ("GIGW 3.0: Indian government web guidelines (WCAG 2.1 AA)", "https://guidelines.india.gov.in/"),
    ("Siasat, Eight colleges booked for forging HYDRAA chief's signature, Aug 2026", "https://www.siasat.com/eight-colleges-booked-for-forging-hydraa-chiefs-signature-3519057/"),
    ("ThePrint/PTI, DU plans AI tool after manipulated documents, 20 Jul 2026", "https://theprint.in/india/du-plans-to-develop-ai-based-verification-tool-after-detecting-manipulated-documents-in-admissions/2991453/"),
    ("Careers360/PTI, Delhi basement shown as store room in documents, Jul 2024", "https://news.careers360.com/delhi-coaching-centre-where-3-died-falsely-showed-basement-store-room-in-documents"),
    ("Hindustan Times, One in 3 tech institutes filed false data for AICTE nod, 13 Apr 2017", "https://www.pressreader.com/india/hindustan-times-chandigarh/20170413/281779923991822"),
    ("DT Next, Ghost faculties: Anna Univ sends notices to 100 colleges, 2024", "https://www.dtnext.in/news/chennai/ghost-faculties-anna-univ-sends-notices-to-100-colleges-797156"),
    ("Scroll, 830 fake institutes got Rs 144 crore in scholarships (CBI), Aug 2023", "https://scroll.in/latest/1055121/830-fake-institutes-got-rs-144-crore-in-minority-scholarship-funds-alleges-cbi"),
]
text(s6, 7.25, 1.55, 5.68, 0.3, [{"runs": [("Research papers, standards and sources", {"bold": True, "color": NAVY, "size": 11.5})]}])
text(s6, 7.25, 1.86, 5.68, 4.95, [{"runs": [(f"{i}. ", {"bold": True, "color": NAVY}), (t, {"link": u, "color": BLUE})], "space_after": 3}
                                  for i, (t, u) in enumerate(refs, 1)], size=8.8)
box(s6, 7.25, 5.0, 5.68, 1.8, fill=BG, line=LINE)
text(s6, 7.35, 5.05, 5.48, 1.72, [
    {"runs": [("Data and test assets (all free)", {"bold": True, "color": NAVY, "size": 11})]},
    rich("**Labelled test set we built**: 195 documents, 8 forgery types (PS allows synthetic data)", size=9.2),
    rich("**Rules**: APH 2024-27; **public EoA letters** (mandatory disclosure) for real layouts", size=9.2),
    rich("**DocTamper** for tamper-model training; **Open Buildings + OpenStreetMap** for footprints", size=9.2),
    rich("**Sandbox issuer PKI** (our own CA) to test real PDF signatures end to end", size=9.2),
])
notes(s6, "If asked about DigiLocker: it only holds documents issued into it; most fire NOCs, lease deeds and affidavits are not there. "
          "We use it as one Tier 1 source.")

prs.save(OUT)
print("saved", OUT)
