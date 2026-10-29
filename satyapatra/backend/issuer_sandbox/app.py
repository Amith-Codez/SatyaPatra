"""Issuer sandbox: stands in for real issuers' verification portals so every tier can be shown working.

It is a separate service on its own port, reached over HTTP exactly as a real issuer would be:
  GET  /api/records/{doc_type}/{ref}   Tier 2 lookup (404 when the issuer never issued it)
  GET  /v/{ref}                        public page a genuine QR code opens
  GET  /confirm/{token}                Tier 3: the issuer's officer answers yes / no
"""
import html
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse

RECORDS = Path(__file__).resolve().parent / "records.json"
MAIN = os.environ.get("SATYA_MAIN", "http://127.0.0.1:8000")
app = FastAPI(title="Issuer sandbox (synthetic)")


def records():
    return json.loads(RECORDS.read_text()) if RECORDS.exists() else {}


@app.get("/api/records/{doc_type}/{ref}")
def lookup(doc_type: str, ref: str):
    rec = records().get(doc_type, {}).get(ref)
    if not rec:
        raise HTTPException(404, "No such record")
    return rec


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{margin:0;font:15px/1.5 Arial,Helvetica,sans-serif;background:#F2F3F5;color:#1B1F27}}
header{{background:#7A1F1F;color:#fff;padding:14px 24px}} header b{{font-size:17px}} header small{{display:block;opacity:.85}}
main{{max-width:720px;margin:28px auto;padding:0 16px}} .card{{background:#fff;border:1px solid #D9DCE1;border-radius:6px;padding:22px}}
table{{border-collapse:collapse;width:100%}} td{{padding:8px 6px;border-bottom:1px solid #EDEFF2}} td:first-child{{color:#5A6170;width:40%}}
.ok{{color:#0F6B45;font-weight:700}} .bad{{color:#A32020;font-weight:700}} button{{font:inherit;padding:10px 18px;border-radius:4px;border:1px solid #1B1F27;background:#fff;cursor:pointer;margin-right:10px}}
button.y{{background:#0F6B45;color:#fff;border-color:#0F6B45}} button.n{{background:#A32020;color:#fff;border-color:#A32020}}
.note{{font-size:12.5px;color:#5A6170;margin-top:16px}}</style></head><body>
<header><b>Issuer Verification Portal</b><small>SANDBOX - synthetic issuer used to demonstrate SatyaPatra. Not a government website.</small></header>
<main><div class="card">{body}</div><p class="note">Records here are fictional test data.</p></main></body></html>"""


@app.get("/v/{ref}", response_class=HTMLResponse)
def public_verify(ref: str):
    for kind, recs in records().items():
        if ref in recs:
            rows = "".join(f"<tr><td>{html.escape(k.replace('_', ' ').title())}</td><td>{html.escape(str(v))}</td></tr>"
                           for k, v in recs[ref].items() if k != "exists")
            return PAGE.format(title="Record found", body=f"<p class='ok'>Record found in issuer database</p><table>{rows}</table>")
    return PAGE.format(title="Not found", body=f"<p class='bad'>No record for {html.escape(ref)}</p>")


@app.get("/confirm/{token}", response_class=HTMLResponse)
def confirm_page(token: str):
    try:
        info = httpx.get(f"{MAIN}/api/confirmations/{token}", timeout=5).json()
    except Exception:
        raise HTTPException(502, "SatyaPatra is not reachable")
    if info.get("state") in ("yes", "no"):
        return PAGE.format(title="Answered", body=f"<p>Already answered: <b>{info['state']}</b>.</p>")
    body = (f"<h2 style='margin-top:0'>Did your office issue this document?</h2>"
            f"<table><tr><td>Reference</td><td><b>{html.escape(info.get('reference', ''))}</b></td></tr>"
            f"<tr><td>Submitted by</td><td>{html.escape(info.get('institution', ''))}</td></tr>"
            f"<tr><td>Requested by</td><td>AICTE approval verification (SatyaPatra)</td></tr></table><br>"
            f"<form method='post'><button class='y' name='answer' value='yes'>Yes, we issued it</button>"
            f"<button class='n' name='answer' value='no'>No, we did not</button></form>")
    return PAGE.format(title="Confirm document", body=body)


@app.post("/confirm/{token}", response_class=HTMLResponse)
def confirm_answer(token: str, answer: str = Form(...)):
    httpx.post(f"{MAIN}/api/confirmations/{token}/answer", json={"answer": answer}, timeout=10)
    return PAGE.format(title="Thank you", body=f"<p class='{'ok' if answer == 'yes' else 'bad'}'>Answer recorded: {answer}.</p>")
