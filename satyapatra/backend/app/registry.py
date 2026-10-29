"""Issuer Trust Registry: who issues which document, and the official ways to confirm it.

Edited only by AICTE administrators. Contact details printed on an uploaded document are never used.
The entries below point to the local issuer sandbox, which stands in for real issuer portals.
"""
from .config import ISSUER_BASE, PKI

HOST = ISSUER_BASE.split("://", 1)[1]

ISSUERS = [
    {"id": "ISS-FIRE", "name": "Sample State Fire & Emergency Services", "short": "State Fire Services",
     "doc_types": ["fire_noc"], "match": "Fire & Emergency",
     "tier1": {"signing_ca": str(PKI / "issuer-ca.pem"), "qr_domains": [HOST]},
     "tier2": {"lookup": f"{ISSUER_BASE}/api/records/fire_noc/{{ref}}", "ref_field": "noc_no"},
     "tier3": {"contact": "noc-verification@fire.issuer.sandbox"}, "sla_days": 3},
    {"id": "ISS-MUNI", "name": "Sample Municipal Corporation", "short": "Municipal Corporation",
     "doc_types": ["building_completion"], "match": "Municipal",
     "tier1": {"signing_ca": str(PKI / "issuer-ca.pem"), "qr_domains": [HOST]},
     "tier2": {"lookup": f"{ISSUER_BASE}/api/records/building_completion/{{ref}}", "ref_field": "cert_no"},
     "tier3": {"contact": "building-cert@municipal.issuer.sandbox"}, "sla_days": 5},
    {"id": "ISS-REG", "name": "Sample Sub-Registrar Office", "short": "Sub-Registrar",
     "doc_types": ["lease_deed"], "match": "Sub-Registrar",
     "tier1": {"qr_domains": [HOST]},
     "tier2": {"lookup": f"{ISSUER_BASE}/api/records/lease_deed/{{ref}}", "ref_field": "reg_no"},
     "tier3": {"contact": "records@subregistrar.issuer.sandbox"}, "sla_days": 7},
    {"id": "ISS-BANK", "name": "Sample National Bank", "short": "Sample National Bank",
     "doc_types": ["fdr"], "match": "National Bank",
     "tier1": {"qr_domains": []}, "tier2": None,
     "tier3": {"contact": "fdr-confirm@bank.issuer.sandbox", "ref_field": "fdr_no"}, "sla_days": 5},
]

SELF_DECLARED = {"affidavit", "faculty_list"}


def for_doc(doc_type, issuer_text=""):
    for iss in ISSUERS:
        if doc_type in iss["doc_types"]:
            return iss
    return None


def public_view():
    out = []
    for i in ISSUERS:
        out.append({"id": i["id"], "name": i["name"], "doc_types": i["doc_types"], "sla_days": i["sla_days"],
                    "tier1": bool(i["tier1"] and (i["tier1"].get("signing_ca") or i["tier1"].get("qr_domains"))),
                    "signing": bool(i["tier1"] and i["tier1"].get("signing_ca")),
                    "qr_domains": (i["tier1"] or {}).get("qr_domains", []),
                    "tier2": bool(i["tier2"]), "tier3": i["tier3"]["contact"] if i.get("tier3") else None})
    return out
