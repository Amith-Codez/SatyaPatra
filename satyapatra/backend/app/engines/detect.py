"""DETECT engine: signs that a document was altered, and scans reused across institutions.

Every finding carries evidence (page + box, or the measured value) so an officer can see why.
These are SOFT signals: they raise a risk score and can send a document to manual review,
but on their own they never mark a document as forged.
"""
import hashlib
import io
import re
from collections import Counter
from datetime import datetime

import fitz
import cv2
import imagehash
import numpy as np
from PIL import Image, ImageChops

from .. import config, db

EDITORS = re.compile(r"photoshop|gimp|canva|ilovepdf|smallpdf|pixlr|paint|sejda|pdfescape", re.I)
KEY_FIELDS = ("valid_until", "noc_no", "amount_inr", "maturity_date", "lease_end", "builtup_m2", "cert_no")


def finding(code, title, detail, evidence=None, weight=None, outcome="flag"):
    return {"engine": "DETECT", "code": code, "title": title, "detail": detail, "outcome": outcome,
            "severity": "soft", "weight": config.WEIGHTS.get(code, 0) if weight is None else weight,
            "evidence": evidence or {}}


def _pdf_date(s):
    if not s:
        return None
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})", s)
    return datetime(int(m[1]), int(m[2]), int(m[3])).date() if m else None


def pdf_forensics(path, fields, signed_revisions=0):
    out = []
    raw = open(path, "rb").read()
    doc = fitz.open(path)
    meta = doc.metadata or {}
    producer = f"{meta.get('producer', '')} {meta.get('creator', '')}".strip()

    if EDITORS.search(producer):
        out.append(finding("editor_software", "Saved by an image or PDF editor",
                           f"PDF producer is \"{producer}\". Genuine issuer files come from the issuer's system.",
                           {"producer": producer}))

    created, modified = _pdf_date(meta.get("creationDate")), _pdf_date(meta.get("modDate"))
    issue = (fields.get("issue_date") or fields.get("deposit_date") or {}).get("value")
    if modified and issue and modified.isoformat() > issue and created and modified > created:
        out.append(finding("post_issue_edit", "File changed after the issue date",
                           f"Created {created}, modified {modified}; the document says it was issued {issue}.",
                           {"created": str(created), "modified": str(modified), "issued": issue}))

    eof = raw.count(b"%%EOF")
    extra = eof - 1 - signed_revisions
    if extra > 0:
        out.append(finding("incremental_saves", "Edited and saved again after it was made",
                           f"{extra} later revision(s) appended to the file.", {"revisions": eof}))

    # A white box painted over printed text, with new text on top: the classic manual edit.
    for pi, pg in enumerate(doc):
        spans = [s for b in pg.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]
                 if s["text"].strip()]
        for d in pg.get_drawings():
            fill = d.get("fill")
            if not fill or min(fill) < 0.97 or d.get("type") not in ("f", "fs"):
                continue
            r = d["rect"]
            if r.width < 15 or r.height < 6 or r.width > pg.rect.width * 0.8:
                continue
            covered = [s for s in spans if fitz.Rect(s["bbox"]).intersects(r)]
            if covered:
                fonts_here = Counter((s["font"], round(s["size"])) for s in spans).most_common(1)[0][0]
                on_top = [s["text"].strip() for s in covered if (s["font"], round(s["size"])) != fonts_here]
                hidden = [s["text"].strip() for s in covered if (s["font"], round(s["size"])) == fonts_here]
                detail = ("A white box was painted over printed text and new text written on top. "
                          + (f"Hidden underneath: \"{' '.join(hidden)[:70]}\". " if hidden else "")
                          + (f"Shown on top: \"{' '.join(on_top)[:40]}\"." if on_top else ""))
                out.append(finding("pdf_overlay_edit", "White patch painted over text", detail,
                                   {"page": pi, "bbox": [r.x0, r.y0, r.x1, r.y1], "hidden": hidden, "on_top": on_top}))
                break

        # Key field printed in a different font from the rest of the page
        fonts = Counter((s["font"], round(s["size"])) for s in spans)
        body_font = fonts.most_common(1)[0][0] if fonts else None
        for f in KEY_FIELDS:
            fv = fields.get(f)
            if not fv or fv.get("page") != pi or not fv.get("raw"):
                continue
            for s in spans:
                if fv["raw"][:6] and fv["raw"][:6] in s["text"]:
                    if body_font and (s["font"], round(s["size"])) != body_font and s["font"] != "Helvetica-Bold":
                        out.append(finding("field_font_mismatch", "Key value printed in a different font",
                                           f"\"{s['text'].strip()}\" uses {s['font']} {s['size']:.1f}pt; "
                                           f"the page uses {body_font[0]} {body_font[1]}pt.",
                                           {"page": pi, "bbox": list(s["bbox"])}))
                    break
    return out


def embedded_images(path):
    """Yield (page, bbox, PIL image, sha256 of raw bytes) for each image placed on the pages."""
    doc = fitz.open(path)
    for pi, pg in enumerate(doc):
        for info in pg.get_images(full=True):
            xref = info[0]
            try:
                data = doc.extract_image(xref)["image"]
                rects = pg.get_image_rects(xref)
                im = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                continue
            bbox = list(rects[0]) if rects else None
            yield pi, bbox, im, hashlib.sha256(data).hexdigest()


def ela_hotspot(img, quality=90, block=32):
    """Error level analysis: re-save as JPEG and find a block that changes far more than the rest."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    diff = np.asarray(ImageChops.difference(img, Image.open(buf)).convert("L"), dtype=np.float32)
    h, w = diff.shape
    scores = []
    for y in range(0, h - block, block):
        for x in range(0, w - block, block):
            scores.append((diff[y:y + block, x:x + block].mean(), x, y))
    if not scores:
        return None
    vals = np.array([s[0] for s in scores])
    med = np.median(vals)
    mad = max(np.median(np.abs(vals - med)), 0.35)
    best = max(scores)
    z = (best[0] - med) / mad
    return {"z": float(z), "bbox": [best[1], best[2], best[1] + block, best[2] + block], "size": [w, h]} if z > 12 else None


SEAL_MIN_INLIERS = 120
_orb = cv2.ORB_create(1500)
_spec_cache = {}


def _feat(im):
    g = cv2.cvtColor(np.array(im.convert("RGB").resize((400, 400))), cv2.COLOR_RGB2GRAY)
    return _orb.detectAndCompute(g, None)


def seal_match(specimen_path, im):
    """Rotation-tolerant comparison of a seal against the issuer's registered specimen.
    ORB keypoints + ratio test + RANSAC; returns the number of geometrically consistent matches."""
    if specimen_path not in _spec_cache:
        m = Image.open(specimen_path).convert("RGBA")
        bg = Image.new("RGB", m.size, (250, 249, 244))
        bg.paste(m, (0, 0), m)
        _spec_cache[specimen_path] = _feat(bg)
    ka, da = _spec_cache[specimen_path]
    kb, db_ = _feat(im)
    if da is None or db_ is None:
        return 0
    ms = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db_, k=2)
    good = [p[0] for p in ms if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < 8:
        return len(good)
    src = np.float32([ka[g.queryIdx].pt for g in good])
    dst = np.float32([kb[g.trainIdx].pt for g in good])
    _, mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=6)
    return int(mask.sum()) if mask is not None else 0


def _is_qr(im):
    """QR codes and barcodes are pure black-and-white; scanned ink stamps never are."""
    g = np.asarray(im.convert("L"), dtype=np.uint8)
    mid = np.logical_and(g > 40, g < 215).mean()
    return mid < 0.04


def image_forensics(path, mime, institution_id, document_id, issuer_specimen=None):
    out, memory_rows = [], []
    if mime == "application/pdf":
        imgs = list(embedded_images(path))
    else:
        im = Image.open(path).convert("RGB")
        imgs = [(0, [0, 0, im.width, im.height], im, hashlib.sha256(open(path, "rb").read()).hexdigest())]
        hot = ela_hotspot(im)
        if hot:
            out.append(finding("ela_hotspot", "One area compresses differently from the rest",
                               f"One region's compression error is {hot['z']:.0f} times the page's normal variation, "
                               "a sign that a patch was pasted in.", {"page": 0, "bbox": hot["bbox"], "image_px": True}))

    seen = set()
    for pi, bbox, im, sha in imgs:
        if im.width < 40 or im.height < 40 or sha in seen or _is_qr(im):
            continue
        seen.add(sha)
        ph = str(imagehash.phash(im))
        memory_rows.append(("image_sha", sha, institution_id, document_id, f"page {pi}"))
        memory_rows.append(("image_phash", ph, institution_id, document_id, f"page {pi}"))
        # Reused scan: the exact same image bytes already filed by ANOTHER institution.
        other = db.q("SELECT DISTINCT institution_id, document_id FROM memory WHERE kind='image_sha' AND value=? "
                     "AND institution_id<>?", (sha, institution_id))
        if other and im.width < 600:  # small images = seals/signatures; full-page photos are handled by SEE
            out.append(finding("scan_reused", "Same scanned seal found on another institution's file",
                               f"Pixel-identical to an image in {other[0]['document_id']} "
                               f"({other[0]['institution_id']}). Two real scans never match exactly.",
                               {"page": pi, "bbox": bbox, "matches": other[:3]}))
        if issuer_specimen and im.width < 600 and abs(im.width - im.height) < im.width * 0.25:
            inliers = seal_match(issuer_specimen, im)
            if inliers < SEAL_MIN_INLIERS:
                out.append(finding("specimen_mismatch", "Seal does not match the issuer's registered specimen",
                                   f"Only {inliers} matching features with the registered seal "
                                   f"(genuine scans of this seal match on {SEAL_MIN_INLIERS}+; typically 450+).",
                                   {"page": pi, "bbox": bbox, "inliers": inliers}))
    return out, memory_rows
