"""CHECK engine: the APH rulebook, applied to each document and then across the whole application."""
import hashlib
import re
from datetime import date

import yaml
from rapidfuzz import fuzz

from .. import config, db

SALT = b"satyapatra-faculty-salt"


def rules():
    return yaml.safe_load(open(config.RULES_FILE))


def r(rule, outcome, detail, evidence=None):
    return {"engine": "CHECK", "code": rule["id"], "title": rule["title"], "outcome": outcome,
            "severity": rule.get("severity", "hard"), "weight": 0 if rule.get("severity") == "hard" else 20,
            "detail": detail, "evidence": evidence or {}, "rule_ref": rule.get("ref")}


def _years_between(a, b):
    return (b - a).days / 365.25


def document_rules(doc_type, fields, institution, today=None):
    today = today or date.today()
    out = []
    for rule in rules()["rules"]:
        if rule.get("doc_type") != doc_type:
            continue
        f = fields.get(rule.get("field", ""), {})
        v, ev = f.get("value"), {"page": f.get("page"), "bbox": f.get("bbox")}
        k = rule["kind"]
        if v is None:
            out.append(r(rule, config.REVIEW, f"Could not read \"{rule['field'].replace('_', ' ')}\" on the document.", ev))
            continue
        if k == "not_expired":
            d = date.fromisoformat(v)
            out.append(r(rule, config.EXPIRED if d < today else config.VERIFIED,
                         f"{'Expired' if d < today else 'Valid'}: {rule['field'].replace('_', ' ')} is {d:%d %b %Y}.", ev))
        elif k == "min_years_remaining":
            yrs = _years_between(today, date.fromisoformat(v))
            ok = yrs >= rule["years"]
            out.append(r(rule, config.VERIFIED if ok else config.MISMATCH,
                         f"{yrs:.1f} years left (needs {rule['years']}).", ev))
        elif k == "min_amount":
            ok = v >= rule["min"]
            out.append(r(rule, config.VERIFIED if ok else config.MISMATCH,
                         f"Rs {v:,.0f} deposited (needs at least Rs {rule['min']:,.0f}).", ev))
        elif k == "match_application":
            claimed = institution.get(rule["app_field"])
            if claimed:
                gap = abs(v - claimed) / claimed
                out.append(r(rule, config.VERIFIED if gap <= rule["tolerance"] else config.REVIEW,
                             f"Certificate says {v:,.0f} m²; application claims {claimed:,.0f} m² ({gap:.0%} apart).", ev))
    return out


def faculty_hash(fid):
    return hashlib.sha256(SALT + fid.encode()).hexdigest()


def application_rules(app, docs, institution):
    """Rules that need several documents at once."""
    out = []
    by_type = {d["doc_type"]: d for d in docs}
    book = rules()
    for rule in book["rules"]:
        k = rule["kind"]
        if k == "required_documents":
            need = book["required_documents"].get(app["category"], [])
            missing = [t for t in need if t not in by_type]
            out.append(r(rule, config.MISMATCH if missing else config.VERIFIED,
                         ("Missing: " + ", ".join(m.replace('_', ' ') for m in missing)) if missing
                         else f"All {len(need)} required documents present.", {"missing": missing}))
        elif k == "address_consistency":
            ref = institution["address"]
            bad = []
            for d in docs:
                a = (d["fields"].get("address") or {}).get("raw")
                if a and fuzz.ratio(re.sub(r"[^a-z0-9]", "", a.lower()), re.sub(r"[^a-z0-9]", "", ref.lower())) < 90:
                    bad.append({"document": d["id"], "doc_type": d["doc_type"], "address": a,
                                "page": d["fields"]["address"].get("page"), "bbox": d["fields"]["address"].get("bbox")})
            out.append(r(rule, config.MISMATCH if bad else config.VERIFIED,
                         (f"{bad[0]['doc_type'].replace('_', ' ').title()} gives \"{bad[0]['address']}\"; "
                          f"the institution's registered address is \"{ref}\".") if bad
                         else "Same premises address on every document.", {"conflicts": bad}))
        elif k == "permitted_use":
            noc = by_type.get("fire_noc")
            usage = db.unj(app.get("summary"), {}).get("floor_usage", {})
            if noc and usage:
                permitted = (noc["fields"].get("permitted_use") or {}).get("raw", "").lower()
                clashes = []
                for floor, use in usage.items():
                    seg = next((s for s in permitted.split(";") if floor.lower() in s), "")
                    if seg and use.lower() not in seg and "storage" in seg:
                        clashes.append(f"{floor}: declared as {use}, NOC permits \"{seg.strip()}\"")
                out.append(r(rule, config.MISMATCH if clashes else config.VERIFIED,
                             "; ".join(clashes) if clashes else "Every teaching floor is permitted in the fire NOC.",
                             {"document": noc["id"], "page": (noc["fields"].get("permitted_use") or {}).get("page"),
                              "bbox": (noc["fields"].get("permitted_use") or {}).get("bbox")}))
        elif k == "faculty_unique":
            fl = by_type.get("faculty_list")
            if not fl:
                continue
            dupes, first_claim = [], True
            mine = db.q1("SELECT MIN(id) AS id FROM memory WHERE kind='faculty' AND document_id=?", (fl["id"],))
            for row in (fl["fields"].get("faculty") or {}).get("value", []):
                h = faculty_hash(row["faculty_id"])
                hit = db.q("SELECT institution_id, MIN(id) AS id FROM memory WHERE kind='faculty' AND value=? "
                           "AND institution_id<>? GROUP BY institution_id", (h, institution["id"]))
                if hit:
                    dupes.append({"faculty_id": row["faculty_id"], "also_at": [x["institution_id"] for x in hit],
                                  "bbox": row["bbox"]})
                    if mine and mine["id"] and any(x["id"] < mine["id"] for x in hit):
                        first_claim = False
            if not dupes:
                out.append(r(rule, config.VERIFIED, "No faculty member is declared full-time anywhere else.",
                             {"document": fl["id"]}))
            else:
                # The later declaration is the mismatch; the earlier one is reviewed, since either could be wrong.
                outcome = config.REVIEW if first_claim else config.MISMATCH
                who = ", ".join(sorted({a for d in dupes for a in d["also_at"]}))
                out.append(r(rule, outcome,
                             f"{len(dupes)} full-time faculty also declared by {who} "
                             f"({'declared there later; both files reviewed' if first_claim else 'declared there first'}). "
                             f"Example: {dupes[0]['faculty_id']}.",
                             {"document": fl["id"], "duplicates": dupes}))
    return out
