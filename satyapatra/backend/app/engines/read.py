"""READ engine: classify a document, pull out its fields, and remember where each field sits on the page.

Digital PDFs: text and positions come straight from the PDF (PyMuPDF).
Scans and photos: RapidOCR (ONNX, runs on CPU) reads the image.
Unfamiliar layouts: a local LLM (Ollama) proposes fields, and every value it returns must appear
word for word in the document text, or it is dropped ("grounding check").
"""
import io
import json
import re
from datetime import datetime

import fitz  # PyMuPDF
import httpx
from PIL import Image

from .. import config

DOC_TYPES = {
    "fire_noc": ["FIRE SAFETY NO OBJECTION", "FIRE NOC", "NO OBJECTION CERTIFICATE"],
    "building_completion": ["BUILDING COMPLETION", "COMPLETION CERTIFICATE", "OCCUPANCY"],
    "lease_deed": ["LEASE DEED", "LESSOR", "LESSEE"],
    "fdr": ["FIXED DEPOSIT", "FDR NO", "MATURITY"],
    "affidavit": ["AFFIDAVIT", "DEPONENT", "SOLEMNLY"],
    "faculty_list": ["FACULTY DECLARATION", "FACULTY ID", "DESIGNATION"],
}

LABELS = {
    "fire_noc": {"issuer": "Issued by", "noc_no": "NOC No.", "institution": "Name of Institution",
                 "address": "Premises Address", "issue_date": "Date of Issue", "valid_until": "Valid Until",
                 "permitted_use": "Permitted Use", "verify_url": "Verify at"},
    "building_completion": {"issuer": "Issued by", "cert_no": "Certificate No.", "institution": "Owner",
                            "address": "Premises Address", "builtup_m2": "Total Built-up Area",
                            "floors": "Number of Floors", "issue_date": "Date of Issue", "verify_url": "Verify at"},
    "lease_deed": {"issuer": "Registered at", "reg_no": "Registration No.", "institution": "Lessee",
                   "address": "Premises Address", "lease_start": "Lease Start", "lease_end": "Lease End"},
    "fdr": {"issuer": "Bank", "fdr_no": "FDR No.", "institution": "Depositor", "amount_inr": "Amount (INR)",
            "deposit_date": "Date of Deposit", "maturity_date": "Maturity Date"},
    "affidavit": {"institution": "Institution", "address": "Premises Address", "deponent": "Deponent",
                  "issue_date": "Date"},
    "faculty_list": {"institution": "Institution"},
}

DATE_FIELDS = {"issue_date", "valid_until", "lease_start", "lease_end", "deposit_date", "maturity_date"}
NUM_FIELDS = {"builtup_m2", "amount_inr", "floors"}

_ocr = None


def _ocr_engine():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    return _ocr


def parse_date(s):
    s = s.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_num(s):
    digits = re.sub(r"[^\d.]", "", s.split("sq")[0])
    try:
        return float(digits) if "." in digits else int(digits)
    except ValueError:
        return None


def load_pages(path, mime):
    """Return (pages, kind). Each page: {'text', 'lines':[{'text','bbox'}], 'size':(w,h)}."""
    pages = []
    if mime == "application/pdf":
        doc = fitz.open(path)
        for pg in doc:
            lines = []
            for b in pg.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    t = "".join(s["text"] for s in ln["spans"]).strip()
                    if t:
                        lines.append({"text": t, "bbox": list(ln["bbox"])})
            text = "\n".join(l["text"] for l in lines)
            if len(text) < 20:  # scanned PDF: OCR the rendered page
                pix = pg.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                lines = _ocr_lines(img, scale=72 / 150)
                text = "\n".join(l["text"] for l in lines)
            pages.append({"text": text, "lines": lines, "size": (pg.rect.width, pg.rect.height)})
        return pages, "pdf"
    img = Image.open(path).convert("RGB")
    lines = _ocr_lines(img, scale=1.0)
    pages.append({"text": "\n".join(l["text"] for l in lines), "lines": lines, "size": img.size})
    return pages, "image"


def _ocr_lines(img, scale):
    import numpy as np
    result, _ = _ocr_engine()(np.array(img))
    lines = []
    for box, txt, conf in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        lines.append({"text": txt, "bbox": [min(xs) * scale, min(ys) * scale, max(xs) * scale, max(ys) * scale],
                      "conf": float(conf)})
    lines.sort(key=lambda l: (round(l["bbox"][1] / 6), l["bbox"][0]))
    return lines


def classify(text):
    up = re.sub(r"[^A-Z0-9]", "", text.upper())  # OCR often drops or adds spaces
    scores = {t: sum(1 for k in kws if re.sub(r"[^A-Z0-9]", "", k) in up) for t, kws in DOC_TYPES.items()}
    best = max(scores, key=scores.get)
    return (best, scores[best]) if scores[best] else ("unknown", 0)


def extract(doc_type, pages):
    """Label-based extraction. Returns {field: {'value', 'raw', 'page', 'bbox'}}."""
    out = {}
    labels = LABELS.get(doc_type, {})
    for pi, pg in enumerate(pages):
        for ln in pg["lines"]:
            for field, label in labels.items():
                if field in out:
                    continue
                m = _label_re(label).match(ln["text"])
                if m:
                    raw = ln["text"][m.end():].lstrip(" :.-").strip()
                    if raw:
                        out[field] = {"raw": raw, "page": pi, "bbox": ln["bbox"], "value": _typed(field, raw)}
    if doc_type == "faculty_list":
        out["faculty"] = {"value": _faculty_rows(pages), "raw": "", "page": 0, "bbox": None}
    return out


def _label_re(label):
    parts = [re.escape(ch) for ch in re.sub(r"[\s.:()]", "", label)]
    return re.compile(r"\s*" + r"[\s.:()]*".join(parts) + r"[\s.:()]*", re.I)


def _typed(field, raw):
    if field in DATE_FIELDS:
        return parse_date(raw)
    if field in NUM_FIELDS:
        return parse_num(raw)
    return raw


def _faculty_rows(pages):
    rows = []
    for pg in pages:
        for ln in pg["lines"]:
            m = re.search(r"\b(FAC-[A-Z]{2}-\d{6})\b", ln["text"])
            if m:
                rows.append({"faculty_id": m.group(1), "line": ln["text"], "bbox": ln["bbox"]})
    return rows


def llm_extract(doc_type, text, wanted):
    """Fallback for unfamiliar layouts. Returns (fields, dropped_fields)."""
    if not config.USE_LLM or not wanted:
        return {}, []
    prompt = ("Extract these fields from the document text as JSON with exactly these keys: "
              + ", ".join(wanted) + ". Copy values exactly as written. Use null if absent.\n\nDOCUMENT:\n"
              + text[:3500])
    try:
        r = httpx.post(f"{config.OLLAMA_URL}/api/generate",
                       json={"model": config.OLLAMA_MODEL, "prompt": prompt, "format": "json", "stream": False,
                             "options": {"temperature": 0}}, timeout=90)
        data = json.loads(r.json().get("response", "{}"))
    except Exception:
        return {}, []
    kept, dropped = {}, []
    norm_text = re.sub(r"\s+", " ", text).lower()
    for k in wanted:
        v = data.get(k)
        if not v:
            continue
        if re.sub(r"\s+", " ", str(v)).lower() in norm_text:  # grounding check
            kept[k] = {"raw": str(v), "page": 0, "bbox": None, "value": _typed(k, str(v)), "source": "llm"}
        else:
            dropped.append(k)
    return kept, dropped


def run(path, mime):
    pages, kind = load_pages(path, mime)
    full = "\n".join(p["text"] for p in pages)
    doc_type, conf = classify(full)
    fields = extract(doc_type, pages)
    missing = [f for f in LABELS.get(doc_type, {}) if f not in fields and f != "verify_url"]
    llm_fields, dropped = ({}, [])
    if missing and doc_type != "unknown":
        llm_fields, dropped = llm_extract(doc_type, full, missing)
        fields.update(llm_fields)
    return {"doc_type": doc_type, "confidence": conf, "kind": kind, "pages": pages, "text": full,
            "fields": fields, "llm_used": bool(llm_fields or dropped), "llm_dropped": dropped}
