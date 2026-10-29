"""SatyaPatra API (FastAPI). OpenAPI docs at /docs, Prometheus metrics at /metrics."""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import jwt
import yaml
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import audit, config, db, jobs, pipeline, registry, storage
from .engines import see

app = FastAPI(title="SatyaPatra API", version="1.0",
              description="AI-assisted verification of AICTE approval documents (PS SIH26261).")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception:
    pass

# ---------------------------------------------------------------- auth (OIDC in production; signed dev tokens here)
SECRET = os.environ.get("SATYA_JWT_SECRET", "dev-only-secret-change-me")
AUTH_REQUIRED = os.environ.get("SATYA_AUTH", "0") == "1"
ROLES = {"officer": "AICTE regional officer", "institution": "Institution (self-check)", "admin": "AICTE administrator"}


class Login(BaseModel):
    role: str = "officer"
    name: str = "Demo Officer"


@app.post("/api/auth/dev-login")
def dev_login(body: Login):
    if body.role not in ROLES:
        raise HTTPException(400, "Unknown role")
    tok = jwt.encode({"sub": body.name, "role": body.role, "iat": int(time.time()), "exp": int(time.time()) + 8 * 3600},
                     SECRET, algorithm="HS256")
    return {"token": tok, "role": body.role, "label": ROLES[body.role]}


def user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        if AUTH_REQUIRED:
            raise HTTPException(401, "Sign in required")
        return {"sub": "Demo Officer", "role": "officer"}
    try:
        return jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, sign in again")


def need(*roles):
    def dep(u=Depends(user)):
        if u["role"] not in roles:
            raise HTTPException(403, "Your role cannot do this")
        return u
    return dep


# ---------------------------------------------------------------- helpers
def _doc_view(d, with_checks=False):
    meta = db.unj(d.get("fields"), {}) or {}
    out = {k: d[k] for k in ("id", "application_id", "filename", "sha256", "mime", "doc_type", "status", "risk", "created_at")}
    out["renders"] = [f"/api/renders/{r['png']}" for r in meta.get("renders", [])]
    out["page_sizes"] = [[r["w"], r["h"]] for r in meta.get("renders", [])]
    out["fields"] = {k: {"raw": v.get("raw"), "value": v.get("value"), "page": v.get("page"), "bbox": v.get("bbox"),
                         "source": v.get("source", "text")}
                     for k, v in (meta.get("fields") or {}).items() if k != "faculty"}
    if "faculty" in (meta.get("fields") or {}):
        out["faculty"] = meta["fields"]["faculty"]["value"]
    out["ms"] = meta.get("ms")
    out["issuer"] = meta.get("issuer")
    if with_checks:
        out["checks"] = _checks(d["id"])
    return out


def _checks(subject):
    rows = db.q("SELECT engine,code,title,outcome,severity,weight,detail,evidence,rule_ref FROM checks WHERE document_id=? "
                "ORDER BY id", (subject,))
    for r in rows:
        r["evidence"] = db.unj(r["evidence"], {})
    return rows


def _top_finding(app_id):
    rows = db.q("SELECT c.title, c.outcome FROM checks c JOIN documents d ON d.id=c.document_id "
                "WHERE d.application_id=? AND c.outcome<>? AND c.severity<>'info' ORDER BY "
                "CASE c.outcome WHEN 'Mismatch detected' THEN 0 WHEN 'Expired' THEN 1 ELSE 2 END, c.id LIMIT 1",
                (app_id, config.VERIFIED))
    rows += db.q("SELECT title, outcome FROM checks WHERE document_id=? AND outcome<>? ORDER BY "
                 "CASE outcome WHEN 'Mismatch detected' THEN 0 ELSE 1 END LIMIT 1", (f"APP:{app_id}", config.VERIFIED))
    rows.sort(key=lambda r: pipeline.RANK.get(r["outcome"], 9) if r["outcome"] in pipeline.RANK else 3)
    return rows[0]["title"] if rows else "All documents confirmed"


# ---------------------------------------------------------------- read endpoints
@app.get("/api/health")
def health():
    return {"ok": True, "database": db.backend_name(), "storage": storage.backend_name(), "jobs": jobs.backend_name(),
            "llm": f"{config.OLLAMA_MODEL} via Ollama" if config.USE_LLM else "off", "auth": "required" if AUTH_REQUIRED else "dev"}


@app.get("/api/overview")
def overview(u=Depends(user)):
    apps = db.q("SELECT status, COUNT(*) n FROM applications WHERE id NOT LIKE 'SELF-%' GROUP BY status")
    docs = db.q("SELECT d.status, COUNT(*) n FROM documents d WHERE d.application_id NOT LIKE 'SELF-%' GROUP BY d.status")
    by_type = db.q("SELECT doc_type, status, COUNT(*) n FROM documents WHERE application_id NOT LIKE 'SELF-%' "
                   "AND doc_type IS NOT NULL GROUP BY doc_type, status")
    tiers = db.q("SELECT code, COUNT(*) n FROM checks WHERE engine='CONFIRM' GROUP BY code")
    engines = db.q("SELECT engine, COUNT(*) n FROM checks WHERE outcome<>? AND severity<>'info' GROUP BY engine",
                   (config.VERIFIED,))
    total_docs = sum(r["n"] for r in docs)
    ms = [db.unj(d["fields"], {}).get("ms") for d in db.q("SELECT fields FROM documents WHERE fields IS NOT NULL")]
    ms = sorted(m for m in ms if m)
    return {"applications": {r["status"]: r["n"] for r in apps}, "documents": {r["status"]: r["n"] for r in docs},
            "documents_total": total_docs, "by_type": by_type, "confirm_codes": {r["code"]: r["n"] for r in tiers},
            "flags_by_engine": {r["engine"]: r["n"] for r in engines},
            "median_ms": ms[len(ms) // 2] if ms else None, "audit_entries": db.q1("SELECT COUNT(*) n FROM audit")["n"]}


@app.get("/api/applications")
def applications(u=Depends(user)):
    rows = db.q("SELECT a.*, i.name, i.region FROM applications a JOIN institutions i ON i.id=a.institution_id "
                "WHERE a.id NOT LIKE 'SELF-%' AND a.id NOT LIKE 'EVAL-%' ORDER BY a.risk DESC, a.id")
    out = []
    for a in rows:
        counts = db.q("SELECT status, COUNT(*) n FROM documents WHERE application_id=? GROUP BY status", (a["id"],))
        out.append({"id": a["id"], "institution": a["name"], "institution_id": a["institution_id"], "region": a["region"],
                    "status": a["status"], "risk": a["risk"], "category": a["category"], "cycle": a["cycle"],
                    "top_finding": _top_finding(a["id"]), "documents": {c["status"]: c["n"] for c in counts},
                    "story": db.unj(a["summary"], {}).get("story")})
    return out


@app.get("/api/applications/{app_id}")
def application(app_id: str, u=Depends(user)):
    a = db.q1("SELECT * FROM applications WHERE id=?", (app_id,))
    if not a:
        raise HTTPException(404, "No such application")
    inst = db.q1("SELECT * FROM institutions WHERE id=?", (a["institution_id"],))
    docs = [_doc_view(d) for d in db.q("SELECT * FROM documents WHERE application_id=? ORDER BY doc_type", (app_id,))]
    for d in docs:
        d["flags"] = db.q1("SELECT COUNT(*) n FROM checks WHERE document_id=? AND outcome<>? AND severity<>'info'",
                           (d["id"], config.VERIFIED))["n"]
    return {"id": a["id"], "status": a["status"], "risk": a["risk"], "category": a["category"], "cycle": a["cycle"],
            "summary": db.unj(a["summary"], {}),
            "institution": {k: inst[k] for k in ("id", "name", "region", "address", "claimed_builtup_m2", "approved_intake")},
            "documents": docs, "checks": _checks(f"APP:{app_id}")}


@app.get("/api/documents/{doc_id}")
def document(doc_id: str, u=Depends(user)):
    d = db.q1("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not d:
        raise HTTPException(404, "No such document")
    return _doc_view(d, with_checks=True)


@app.get("/api/documents/{doc_id}/progress")
def progress(doc_id: str):
    d = db.q1("SELECT status FROM documents WHERE id=?", (doc_id,))
    return {"events": pipeline.PROGRESS.get(doc_id, []), "status": d["status"] if d else None}


@app.get("/api/documents/{doc_id}/file")
def original(doc_id: str, u=Depends(user)):
    d = db.q1("SELECT path, filename, mime FROM documents WHERE id=?", (doc_id,))
    if not d:
        raise HTTPException(404)
    return FileResponse(d["path"], media_type=d["mime"], filename=d["filename"])


@app.get("/api/renders/{name}")
def render(name: str):
    p = (config.RENDERS / name).resolve()
    if p.parent != config.RENDERS.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")


@app.get("/api/geo/{inst_id}")
def geo(inst_id: str, u=Depends(user)):
    inst = db.q1("SELECT * FROM institutions WHERE id=?", (inst_id,))
    if not inst:
        raise HTTPException(404)
    f = config.DATA / "geo" / f"{inst_id}.geojson"
    return {"campus": json.loads(inst["campus_geojson"]), "footprints": json.loads(f.read_text()) if f.exists() else None,
            "claimed_builtup_m2": inst["claimed_builtup_m2"],
            "check": next((c for c in _checks(f"APP:{db.q1('SELECT id FROM applications WHERE institution_id=?', (inst_id,))['id']}")
                           if c["code"] == "builtup_vs_satellite"), None)}


class LiveGeo(BaseModel):
    campus_geojson: dict
    claimed_builtup_m2: float


@app.post("/api/geo/live")
def geo_live(body: LiveGeo, u=Depends(user)):
    """Real OpenStreetMap buildings for any boundary the officer draws or pastes."""
    try:
        fp = see.live_osm_buildings(json.dumps(body.campus_geojson))
    except Exception as e:
        raise HTTPException(502, "The public OpenStreetMap servers are busy right now; try again in a minute. Stored footprints are unaffected.")
    res = see.footprint_check({"campus_geojson": json.dumps(body.campus_geojson),
                               "claimed_builtup_m2": body.claimed_builtup_m2}, fp)
    return {"footprints": fp, "check": res}


@app.get("/api/issuers")
def issuers(u=Depends(user)):
    out = registry.public_view()
    for i in out:
        i["verifications"] = db.q1("SELECT COUNT(*) n FROM documents WHERE fields LIKE ?", (f'%"issuer": "{i["id"]}"%',))["n"]
    return out


@app.get("/api/memory")
def memory(u=Depends(user)):
    seals = db.q("SELECT m1.value, m1.institution_id a, m2.institution_id b, m1.document_id da, m2.document_id dbb "
                 "FROM memory m1 JOIN memory m2 ON m1.kind='image_sha' AND m2.kind='image_sha' AND m1.value=m2.value "
                 "AND m1.institution_id < m2.institution_id")
    fac = db.q("SELECT m1.value, m1.institution_id a, m2.institution_id b FROM memory m1 JOIN memory m2 "
               "ON m1.kind='faculty' AND m2.kind='faculty' AND m1.value=m2.value AND m1.institution_id < m2.institution_id")
    names = {r["id"]: r["name"] for r in db.q("SELECT id, name FROM institutions")}
    pairs = {}
    for r in fac:
        k = (r["a"], r["b"])
        pairs.setdefault(k, {"a": r["a"], "b": r["b"], "a_name": names.get(r["a"]), "b_name": names.get(r["b"]),
                             "faculty": 0, "scans": 0})["faculty"] += 1
    for r in seals:
        k = (r["a"], r["b"])
        pairs.setdefault(k, {"a": r["a"], "b": r["b"], "a_name": names.get(r["a"]), "b_name": names.get(r["b"]),
                             "faculty": 0, "scans": 0})["scans"] += 1
    stats = db.q("SELECT kind, COUNT(*) n FROM memory GROUP BY kind")
    return {"links": [p for p in pairs.values() if not p["a"].startswith("EV")],
            "fingerprints": {r["kind"]: r["n"] for r in stats}}


@app.get("/api/audit")
def audit_log(limit: int = 60, u=Depends(user)):
    rows = db.q("SELECT * FROM audit ORDER BY seq DESC LIMIT ?", (limit,))
    for r in rows:
        r["payload"] = db.unj(r["payload"], {})
    return rows


@app.get("/api/audit/verify")
def audit_verify(u=Depends(user)):
    return audit.verify_chain()


@app.get("/api/rules")
def rules(u=Depends(user)):
    return {"text": config.RULES_FILE.read_text(), "parsed": yaml.safe_load(config.RULES_FILE.read_text())}


@app.get("/api/eval")
def evaluation():
    p = config.DATA / "eval" / "results.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ---------------------------------------------------------------- Tier 3 callbacks (called by the issuer's portal)
@app.get("/api/confirmations/{token}")
def confirmation(token: str):
    c = db.q1("SELECT * FROM confirmations WHERE token=?", (token,))
    if not c:
        raise HTTPException(404)
    d = db.q1("SELECT application_id FROM documents WHERE id=?", (c["document_id"],))
    inst = db.q1("SELECT i.name FROM applications a JOIN institutions i ON i.id=a.institution_id WHERE a.id=?",
                 (d["application_id"],))
    return {"reference": c["reference"], "state": c["state"], "institution": inst["name"] if inst else ""}


class Answer(BaseModel):
    answer: str


@app.post("/api/confirmations/{token}/answer")
def confirmation_answer(token: str, body: Answer):
    c = db.q1("SELECT * FROM confirmations WHERE token=?", (token,))
    if not c or body.answer not in ("yes", "no"):
        raise HTTPException(400)
    with db.tx() as t:
        t.execute("UPDATE confirmations SET state=?, answered_at=? WHERE token=?", (body.answer, pipeline.now(), token))
    audit.log(f"issuer:{c['issuer_id']}", f"confirmation.{body.answer}", c["document_id"], {"reference": c["reference"]})
    pipeline.process_document(c["document_id"])
    d = db.q1("SELECT application_id FROM documents WHERE id=?", (c["document_id"],))
    pipeline.process_application(d["application_id"], footprints=_footprints_for_app(d["application_id"]))
    return {"ok": True}


def _footprints_for_app(app_id):
    a = db.q1("SELECT institution_id FROM applications WHERE id=?", (app_id,))
    f = config.DATA / "geo" / f"{a['institution_id']}.geojson"
    return json.loads(f.read_text()) if f.exists() else None


# ---------------------------------------------------------------- upload / self-check
@app.post("/api/verify")
async def verify_upload(file: UploadFile = File(...), application_id: str = Form(default=""),
                        u=Depends(need("officer", "institution", "admin"))):
    if not file.filename or Path(file.filename).suffix.lower() not in (".pdf", ".jpg", ".jpeg", ".png"):
        raise HTTPException(400, "Upload a PDF, JPG or PNG")
    if application_id and not db.q1("SELECT id FROM applications WHERE id=?", (application_id,)):
        raise HTTPException(404, "No such application")
    app_id = application_id or _self_check_app()
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        if tmp.tell() > 25 * 1024 * 1024:
            raise HTTPException(413, "Files above 25 MB are not accepted")
    doc_id = pipeline.add_document(app_id, tmp.name, file.filename)
    os.unlink(tmp.name)
    jobs.submit(pipeline.process_document, doc_id)
    return {"document_id": doc_id, "application_id": app_id}


def _self_check_app():
    """Uploads without an application are checked against a 'self-check' profile (institution readiness)."""
    if not db.q1("SELECT id FROM applications WHERE id='SELF-CHECK'"):
        src = db.q1("SELECT * FROM institutions WHERE id='INS-001'")
        with db.tx() as c:
            c.execute("INSERT INTO institutions VALUES(?,?,?,?,?,?,?,1)",
                      ("INS-SELF", "Self-check workspace", "Any", src["address"] if src else "", src["campus_geojson"] if src else "{}",
                       src["claimed_builtup_m2"] if src else 0, 0))
            c.execute("INSERT INTO applications VALUES(?,?,?,?,?,?,?,?)",
                      ("SELF-CHECK", "INS-SELF", "EoA", "2027-28", pipeline.now(), "queued", 0, "{}"))
    return "SELF-CHECK"


# ---------------------------------------------------------------- officer actions (decisions stay human, and are logged)
class Action(BaseModel):
    action: str
    note: str = ""


ACTIONS = {"clarify": "Clarification requested from institution", "inspect": "Sent for physical inspection",
           "forward": "Forwarded to the next approval stage"}


@app.post("/api/applications/{app_id}/action")
def act(app_id: str, body: Action, u=Depends(need("officer", "admin"))):
    if body.action not in ACTIONS or not db.q1("SELECT id FROM applications WHERE id=?", (app_id,)):
        raise HTTPException(400, "Unknown action or application")
    h = audit.log(f"officer:{u['sub']}", f"decision.{body.action}", app_id, {"note": body.note})
    return {"ok": True, "message": ACTIONS[body.action], "hash": h}


# ---------------------------------------------------------------- sample files for the live demo
SAMPLES = config.DATA / "samples"


@app.get("/api/samples")
def samples():
    return [{"name": p.name, "label": p.stem.split("__")[-1].replace("_", " ")}
            for p in sorted(SAMPLES.glob("*")) if p.suffix in (".pdf", ".jpg")] if SAMPLES.exists() else []


@app.post("/api/samples/{name}/verify")
def verify_sample(name: str, u=Depends(need("officer", "institution", "admin"))):
    p = (SAMPLES / name).resolve()
    if p.parent != SAMPLES.resolve() or not p.exists():
        raise HTTPException(404)
    app_id = _self_check_app()
    doc_id = pipeline.add_document(app_id, str(p), name)
    pipeline.PROGRESS.pop(doc_id, None)
    with db.tx() as c:
        c.execute("UPDATE documents SET status='queued' WHERE id=?", (doc_id,))
    jobs.submit(pipeline.process_document, doc_id)
    return {"document_id": doc_id, "application_id": app_id}


# ---------------------------------------------------------------- frontend
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = config.FRONTEND_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
