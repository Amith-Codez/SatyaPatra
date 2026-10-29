"""Runs READ -> CHECK -> DETECT -> CONFIRM per document, then application-wide CHECK and SEE,
and turns every finding into one of the six statuses named in PS SIH26261.

Decision rule (simple on purpose, so an officer can explain it):
  1. Any HARD finding sets the status directly (worst wins): Mismatch > Expired > Manual review >
     Verification pending > Source unavailable.
  2. SOFT findings add their weights into a 0-100 risk score. A score of 30+ means Manual review.
  3. Otherwise the document is Verified only if a source confirmed it or it is self-declared and
     every cross-check passed.
"""
import json
import mimetypes
import time
from datetime import datetime, timezone
from pathlib import Path

import fitz
import logging

logging.getLogger("pyhanko").setLevel(logging.CRITICAL)

from . import audit, config, db, storage
from .config import STATUS_ORDER
from .engines import check, confirm, detect, read, see
from .registry import SELF_DECLARED

RANK = {s: i for i, s in enumerate(STATUS_ORDER)}
LABEL = {"fire_noc": "a fire NOC", "building_completion": "a building completion certificate", "lease_deed": "a lease deed",
         "fdr": "a fixed deposit receipt", "affidavit": "an affidavit", "faculty_list": "a faculty declaration",
         "unknown": "an unrecognised document"}
PROGRESS = {}  # document_id -> list of {stage, text, ms}; read by the upload screen


def _progress(doc_id, stage, text, t0):
    PROGRESS.setdefault(doc_id, []).append({"stage": stage, "text": text, "ms": int((time.perf_counter() - t0) * 1000)})


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def render_pages(path, mime, doc_id):
    out = []
    if mime == "application/pdf":
        for i, pg in enumerate(fitz.open(path)):
            p = config.RENDERS / f"{doc_id}-{i}.png"
            pg.get_pixmap(dpi=110).save(p)
            out.append({"png": p.name, "w": pg.rect.width, "h": pg.rect.height})
    else:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        p = config.RENDERS / f"{doc_id}-0.png"
        im.thumbnail((1400, 1400))
        im.save(p)
        w, h = Image.open(path).size
        out.append({"png": p.name, "w": w, "h": h})
    return out


def decide(results, self_declared=False):
    hard = [r for r in results if r["severity"] == "hard" and r["outcome"] != config.VERIFIED]
    soft_score = min(100, sum(r.get("weight", 0) for r in results
                              if r["severity"] == "soft" and r["outcome"] != config.VERIFIED))
    confirmed = any(r["engine"] == "CONFIRM" and r["outcome"] == config.VERIFIED and r["severity"] == "hard"
                    for r in results)
    if hard:
        status = min((r["outcome"] for r in hard), key=lambda s: RANK[s])
        hard_risk = {config.MISMATCH: 95, config.EXPIRED: 70, config.REVIEW: 55,
                     config.PENDING: 25, config.UNAVAILABLE: 30}.get(status, 50)
        return status, max(hard_risk, soft_score)
    if soft_score >= config.REVIEW_THRESHOLD:
        return config.REVIEW, soft_score
    if confirmed or self_declared:
        return config.VERIFIED, soft_score
    return config.REVIEW, max(soft_score, 40)


def save_checks(document_id, results):
    with db.tx() as c:
        c.execute("DELETE FROM checks WHERE document_id=?", (document_id,))
        for r in results:
            c.execute("INSERT INTO checks(document_id,engine,code,title,outcome,severity,weight,detail,evidence,rule_ref,created_at)"
                      " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (document_id, r["engine"], r["code"], r["title"], r["outcome"], r["severity"], r.get("weight", 0),
                       r["detail"], db.j(r.get("evidence", {})), r.get("rule_ref"), now()))


def process_document(document_id):
    t0 = time.perf_counter()
    d = db.q1("SELECT * FROM documents WHERE id=?", (document_id,))
    app = db.q1("SELECT * FROM applications WHERE id=?", (d["application_id"],))
    inst = db.q1("SELECT * FROM institutions WHERE id=?", (app["institution_id"],))
    path, mime = d["path"], d["mime"]

    PROGRESS[document_id] = []
    rd = read.run(path, mime)
    fields = rd["fields"]
    _progress(document_id, "READ", f"Read as {LABEL.get(rd['doc_type'], rd['doc_type'])}: {len(fields)} fields"
              f"{' via OCR' if rd['kind'] == 'image' else ''}", t0)
    results = [{"engine": "READ", "code": "classified", "title": f"Read as {LABEL.get(rd['doc_type'], rd['doc_type'])}",
                "outcome": config.VERIFIED, "severity": "info", "weight": 0,
                "detail": f"{len(fields)} fields extracted from {len(rd['pages'])} page(s)"
                          f"{' with OCR' if rd['kind'] == 'image' else ''}"
                          f"{'; local LLM helped with missing fields' if rd['llm_used'] else ''}.",
                "evidence": {"fields": list(fields)}}]
    if rd["llm_dropped"]:
        results.append({"engine": "READ", "code": "llm_ungrounded", "severity": "soft",
                        "weight": config.WEIGHTS["llm_ungrounded"], "outcome": config.REVIEW,
                        "title": "Some AI-suggested values were not found in the document",
                        "detail": "Dropped: " + ", ".join(rd["llm_dropped"]) + ". Only text present on the page is used.",
                        "evidence": {}})

    is_photo = rd["doc_type"] == "unknown" and mime.startswith("image/") and len(rd["text"]) < 40
    if is_photo:
        rd["doc_type"] = "photo"
        results[0]["title"] = "Read as a campus photo"
        results.append(see.photo_check(path, inst))
    elif rd["doc_type"] == "unknown":
        results.append({"engine": "READ", "code": "unknown_type", "severity": "hard", "weight": 0,
                        "outcome": config.REVIEW, "title": "Document type not recognised",
                        "detail": "Sent to an officer to classify.", "evidence": {}})

    rule_res = check.document_rules(rd["doc_type"], fields, inst)
    results += rule_res
    _progress(document_id, "CHECK", f"{len(rule_res)} handbook rule{'' if len(rule_res) == 1 else 's'} applied", t0)
    conf, issuer, signed_revs = confirm.run(path, mime, rd["doc_type"], fields, document_id)
    results += conf
    _progress(document_id, "CONFIRM", (conf[-1]["title"] if conf else "Self-declared: no issuer to ask"), t0)
    if mime == "application/pdf":
        results += detect.pdf_forensics(path, fields, signed_revs)
    img_findings, mem_rows = ([], []) if is_photo else detect.image_forensics(
        path, mime, inst["id"], document_id, issuer_specimen=_specimen(issuer))
    results += img_findings
    n_flags = sum(1 for r in results if r["engine"] == "DETECT")
    _progress(document_id, "DETECT", f"{n_flags} tampering sign(s) found" if n_flags else "No tampering signs", t0)

    # Remember this file's fingerprints for future cross-institution checks
    mem_rows.append(("doc_sha", d["sha256"], inst["id"], document_id, rd["doc_type"]))
    if rd["doc_type"] == "faculty_list":
        for row in (fields.get("faculty") or {}).get("value", []):
            mem_rows.append(("faculty", check.faculty_hash(row["faculty_id"]), inst["id"], document_id, ""))
    with db.tx() as c:
        c.execute("DELETE FROM memory WHERE document_id=?", (document_id,))
        for m in mem_rows:
            c.execute("INSERT INTO memory(kind,value,institution_id,document_id,note) VALUES(?,?,?,?,?)", m)

    status, risk = decide(results, self_declared=rd["doc_type"] in SELF_DECLARED or is_photo)
    pages = render_pages(path, mime, document_id)
    ms = int((time.perf_counter() - t0) * 1000)
    slim = {k: {kk: vv for kk, vv in v.items()} for k, v in fields.items()}
    with db.tx() as c:
        c.execute("UPDATE documents SET doc_type=?, pages=?, fields=?, status=?, risk=? WHERE id=?",
                  (rd["doc_type"], len(pages), db.j({"fields": slim, "renders": pages, "ms": ms,
                                                       "issuer": issuer["id"] if issuer else None}),
                   status, risk, document_id))
    save_checks(document_id, results)
    _progress(document_id, "DECIDE", f"{status} (risk {risk})", t0)
    audit.log("system", "document.verified", document_id,
              {"status": status, "risk": risk, "checks": len(results), "ms": ms, "sha256": d["sha256"]})
    return status, risk


def _specimen(issuer):
    if not issuer:
        return None
    p = config.PKI / f"{issuer['id']}-seal.png"
    return str(p) if p.exists() else None


def process_application(app_id, footprints=None):
    app = db.q1("SELECT * FROM applications WHERE id=?", (app_id,))
    inst = db.q1("SELECT * FROM institutions WHERE id=?", (app["institution_id"],))
    docs = db.q("SELECT * FROM documents WHERE application_id=?", (app_id,))
    for d in docs:
        if d["status"] in (None, "queued"):
            process_document(d["id"])
    docs = db.q("SELECT * FROM documents WHERE application_id=?", (app_id,))
    parsed = [{**d, "fields": db.unj(d["fields"], {}).get("fields", {})} for d in docs if d["doc_type"]]
    app_results = check.application_rules(app, [p for p in parsed if p["doc_type"] != "photo"], inst)
    if footprints:
        app_results.append(see.footprint_check(inst, footprints))
    save_checks(f"APP:{app_id}", app_results)
    doc_statuses = [d["status"] for d in docs]
    app_status, app_risk = decide(app_results + [
        {"engine": "DOC", "severity": "hard", "outcome": s, "weight": 0} for s in doc_statuses if s != config.VERIFIED
    ], self_declared=True)
    app_risk = max([app_risk] + [d["risk"] or 0 for d in docs])
    with db.tx() as c:
        c.execute("UPDATE applications SET status=?, risk=? WHERE id=?", (app_status, app_risk, app_id))
    audit.log("system", "application.assessed", app_id, {"status": app_status, "risk": app_risk})
    return app_status, app_risk


def add_document(app_id, src_path, filename, truth=None):
    ext = Path(filename).suffix.lower()
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    path, sha = storage.put(src_path, ext)
    doc_id = "DOC-" + sha[:10].upper()
    with db.tx() as c:
        c.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        c.execute("INSERT INTO documents(id,application_id,filename,path,sha256,mime,status,created_at,truth)"
                  " VALUES(?,?,?,?,?,?,?,?,?)", (doc_id, app_id, filename, path, sha, mime, "queued", now(), truth))
    audit.log("institution", "document.uploaded", doc_id, {"filename": filename, "sha256": sha, "application": app_id})
    return doc_id
