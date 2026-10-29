"""CONFIRM engine: ask the authority that issued the document.

Tier 1  cryptographic: PDF digital signature chained to the issuer's CA; QR only if it opens an
        allow-listed official domain.
Tier 2  issuer portal lookup by reference number, fields compared one by one.
Tier 3  one-click confirmation request to the issuer's registered contact (HMAC-signed token).
Hard facts from this engine decide the status. A network error never counts as a mismatch.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

import cv2
import fitz
import httpx
import numpy as np
from rapidfuzz import fuzz

from .. import config, db
from ..registry import for_doc

SECRET = hashlib.sha256(b"satyapatra-sandbox-hmac").digest()


def res(code, title, outcome, detail, tier, evidence=None, severity="hard"):
    return {"engine": "CONFIRM", "code": code, "title": title, "outcome": outcome, "detail": detail,
            "severity": severity, "weight": 0, "evidence": {"tier": tier, **(evidence or {})}}


def signature_check(path, issuer):
    """Returns (result or None, number_of_signed_revisions)."""
    ca = (issuer.get("tier1") or {}).get("signing_ca")
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko_certvalidator import ValidationContext
        from pyhanko.keys import load_cert_from_pemder
    except Exception:
        return None, 0
    with open(path, "rb") as fh:
        try:
            r = PdfFileReader(fh)
            sigs = r.embedded_signatures
        except Exception:
            return None, 0
        if not sigs:
            return None, 0
        if not ca:
            return res("sig_unknown_ca", "Signed, but the registry has no certificate for this issuer", config.REVIEW,
                       "The signature cannot be tied to a registered issuer.", 1), len(sigs)
        vc = ValidationContext(trust_roots=[load_cert_from_pemder(ca)], allow_fetching=False)
        st = validate_pdf_signature(sigs[-1], vc)
        signer = st.signing_cert.subject.native.get("common_name", "unknown") if st.signing_cert else "unknown"
        if st.bottom_line and st.coverage.name in ("ENTIRE_FILE", "ENTIRE_REVISION") and \
                (st.modification_level is None or st.modification_level.name in ("NONE", "LTA_UPDATES")):
            if st.coverage.name == "ENTIRE_FILE":
                return res("sig_valid", "Digital signature valid and file untouched since signing", config.VERIFIED,
                           f"Signed by {signer}; chain verified to the issuer's registered certificate.", 1,
                           {"signer": signer}), len(sigs)
        if st.intact and st.valid and st.trusted:
            return res("sig_modified", "File was changed after the issuer signed it", config.MISMATCH,
                       f"Signature by {signer} is genuine but covers only an earlier version; "
                       f"content was added afterwards (coverage: {st.coverage.name.lower().replace('_', ' ')}).",
                       1, {"signer": signer}), len(sigs)
        return res("sig_invalid", "Digital signature does not verify", config.MISMATCH,
                   f"Signer: {signer}. Integrity intact: {st.intact}; trusted chain: {st.trusted}.", 1), len(sigs)


def qr_check(path, mime, issuer):
    """Decode QR codes on the page. Trusted only if the URL's host is on the issuer's allow-list."""
    imgs = []  # (page, image, scale from image pixels to page units)
    if mime == "application/pdf":
        for pi, pg in enumerate(fitz.open(path)):
            pix = pg.get_pixmap(dpi=200)
            imgs.append((pi, np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3], 72 / 200))
    else:
        imgs.append((0, cv2.imread(path), 1.0))
    det = cv2.QRCodeDetector()
    allowed = set((issuer.get("tier1") or {}).get("qr_domains", [])) if issuer else set()
    for pi, img, sc in imgs:
        try:
            ok, decoded, pts, _ = det.detectAndDecodeMulti(img)
        except Exception:
            continue
        for k, url in enumerate(decoded if ok else []):
            if not url:
                continue
            q = pts[k]
            bbox = [float(q[:, 0].min() * sc), float(q[:, 1].min() * sc), float(q[:, 0].max() * sc), float(q[:, 1].max() * sc)]
            host = urlparse(url).netloc or url
            if host in allowed:
                return {"url": url, "trusted": True, "page": pi, "bbox": bbox}, None
            return {"url": url, "trusted": False}, res(
                "qr_untrusted", "QR code points to a website the issuer does not use", config.MISMATCH,
                f"The QR opens {host}. The registry lists only {', '.join(sorted(allowed)) or 'no QR domains'} "
                "for this issuer. Fake verification pages are how forged certificates pass a quick scan.",
                1, {"url": url, "page": pi, "bbox": bbox})
    return None, None


def _norm(s):
    """Compare text the way a person would: ignore case, spacing and punctuation (OCR drops spaces)."""
    import re
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def tier2_lookup(issuer, fields):
    t2 = issuer.get("tier2")
    if not t2:
        return None
    ref_f = fields.get(t2["ref_field"]) or {}
    ref = ref_f.get("raw")
    where = {"page": ref_f.get("page"), "bbox": ref_f.get("bbox")}
    if not ref:
        return res("t2_no_ref", "No reference number to look up", config.REVIEW,
                   "The document's reference number could not be read.", 2)
    url = t2["lookup"].format(ref=ref.replace("/", "-"))
    try:
        r = httpx.get(url, timeout=6)
    except Exception as e:
        return res("t2_unavailable", "Issuer portal did not respond", config.UNAVAILABLE,
                   f"{issuer['short']} portal unreachable ({type(e).__name__}). Retried later; never counted as a mismatch.",
                   2, {"url": url})
    if r.status_code == 404:
        return res("t2_not_found", f"{issuer['short']} has no record of {ref}", config.MISMATCH,
                   f"Looked up {ref} on the issuer's portal: no such record exists.", 2, {"url": url, "ref": ref, **where})
    if r.status_code != 200:
        return res("t2_unavailable", "Issuer portal returned an error", config.UNAVAILABLE,
                   f"HTTP {r.status_code}. Retried later.", 2, {"url": url})
    rec = r.json()
    diffs = []
    for k, v in rec.items():
        if k in ("reference", "issuer") or k not in fields:
            continue
        mine = fields[k].get("value") if fields[k].get("value") is not None else fields[k].get("raw")
        if isinstance(v, (int, float)) and isinstance(mine, (int, float)):
            same = abs(v - mine) <= max(1, abs(v) * 0.001)
        else:
            same = fuzz.ratio(_norm(v), _norm(mine)) >= 92
        if not same:
            diffs.append({"field": k, "document": mine, "issuer": v})
    if diffs:
        d = "; ".join(f"{x['field'].replace('_', ' ')}: document says \"{x['document']}\", issuer says \"{x['issuer']}\""
                      for x in diffs[:3])
        f0 = fields.get(diffs[0]["field"]) or {}
        return res("t2_fields_differ", "Issuer's record differs from the document", config.MISMATCH, d, 2,
                   {"url": url, "diffs": diffs, "page": f0.get("page"), "bbox": f0.get("bbox")})
    return res("t2_match", f"Confirmed by {issuer['short']} portal", config.VERIFIED,
               f"Record {ref} exists and every field matches ({len(rec) - 2} compared).", 2, {"url": url})


def make_token(document_id, issuer_id):
    nonce = secrets.token_hex(8)
    sig = hmac.new(SECRET, f"{document_id}:{issuer_id}:{nonce}".encode(), "sha256").hexdigest()[:16]
    return f"{nonce}.{sig}"


def tier3_request(issuer, fields, document_id):
    t3 = issuer.get("tier3")
    ref = (fields.get(t3.get("ref_field", "")) or {}).get("raw", "") if t3 else ""
    existing = db.q1("SELECT * FROM confirmations WHERE document_id=?", (document_id,))
    if existing:
        tok, state = existing["token"], existing["state"]
    else:
        tok, state = make_token(document_id, issuer["id"]), "pending"
        with db.tx() as c:
            c.execute("INSERT INTO confirmations VALUES(?,?,?,?,?,?,NULL)",
                      (tok, document_id, issuer["id"], ref, state, datetime.now(timezone.utc).isoformat()))
    link = f"{config.ISSUER_BASE}/confirm/{tok}"
    if state == "yes":
        return res("t3_confirmed", f"{issuer['short']} confirmed it issued {ref}", config.VERIFIED,
                   f"Answered on the issuer's registered channel ({t3['contact']}).", 3, {"token": tok})
    if state == "no":
        return res("t3_denied", f"{issuer['short']} says it did not issue {ref}", config.MISMATCH,
                   f"Denied on the issuer's registered channel ({t3['contact']}).", 3, {"token": tok})
    return res("t3_pending", f"Confirmation requested from {issuer['short']}", config.PENDING,
               f"Signed one-time link sent to {t3['contact']}; answer due within {issuer['sla_days']} days, "
               "after which the file goes to manual review.", 3, {"token": tok, "link": link})


def run(path, mime, doc_type, fields, document_id):
    issuer = for_doc(doc_type)
    if not issuer:
        return [], None, 0
    results = []
    sig, signed_revs = (None, 0)
    if mime == "application/pdf":
        sig, signed_revs = signature_check(path, issuer)
    if sig:
        results.append(sig)
    qr, qr_bad = qr_check(path, mime, issuer)
    if qr_bad:
        results.append(qr_bad)
    elif qr and qr.get("trusted"):
        results.append(res("qr_trusted", "QR opens the issuer's official domain", config.VERIFIED,
                           f"QR leads to {urlparse(qr['url']).netloc}, which the registry lists for this issuer.", 1,
                           {"url": qr["url"], "page": qr["page"], "bbox": qr["bbox"]}, severity="info"))
    hard_done = sig and sig["code"] == "sig_valid"
    if not hard_done and issuer.get("tier2"):
        results.append(tier2_lookup(issuer, fields))
    elif not hard_done and issuer.get("tier3"):
        results.append(tier3_request(issuer, fields, document_id))
    return results, issuer, signed_revs
