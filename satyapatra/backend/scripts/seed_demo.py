"""Seed the demo: 10 fictional institutions, each showing one real-world fraud pattern.

Run with the issuer sandbox up (it answers Tier 2 lookups):
  python scripts/seed_demo.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_corpus as gc  # noqa: E402
from app import audit, config, db, pipeline  # noqa: E402

GEO = config.DATA / "geo"
GEO.mkdir(exist_ok=True)
BIG = [(-180, -110, 90, 40, 14.4), (-60, -110, 70, 40, 14.4), (40, -100, 60, 45, 14.4), (-170, 20, 80, 50, 10.8),
       (-40, 30, 100, 40, 10.8), (90, 10, 60, 60, 14.4)]
SMALL = [(-120, -60, 50, 30, 7.2), (20, -40, 40, 25, 3.6), (-60, 40, 35, 20, 7.2)]

FAC_A = [f"FAC-SC-{100100 + i * 7:06d}" for i in range(14)]
FAC_B = FAC_A[:5] + [f"FAC-SC-{200300 + i * 11:06d}" for i in range(9)]

INSTITUTIONS = [
    dict(id="INS-001", name="Example Institute of Engineering", region="South-Central",
         address="Plot 14, Knowledge Park Road, Sample Nagar", center=(20.0105, 79.0120), claimed_builtup_m2=21500,
         story="Every document confirmed at source; 5 of its faculty were later also claimed by another college"),
    dict(id="INS-002", name="Sample College of Technology", region="South-Central",
         address="Survey No. 88, Lakeview Ring Road, Demo Town", center=(20.0305, 79.0420), claimed_builtup_m2=18200,
         story="Fire NOC copied from another college: seal scan reused, issuer record names someone else"),
    dict(id="INS-003", name="Demo Polytechnic", region="Western",
         address="Old Highway 6, Example District", center=(20.0505, 79.0720), claimed_builtup_m2=12400,
         story="Built-up area claim far above satellite estimate; lab photo taken elsewhere"),
    dict(id="INS-004", name="Model Institute of Management", region="Western",
         address="Sector 9, Institutional Area, Model City", center=(20.0705, 79.1020), claimed_builtup_m2=9800,
         story="Lease ends too soon; FDR confirmation still awaited from the bank"),
    dict(id="INS-005", name="Test Engineering College", region="Northern",
         address="Canal Road, Test Village", center=(20.0905, 79.1320), claimed_builtup_m2=16800,
         story="Expired fire NOC with a pasted-over validity date and a fake verification QR"),
    dict(id="INS-006", name="Placeholder Pharmacy College", region="Northern",
         address="Hill View Layout, Placeholder Pur", center=(20.1105, 79.1620), claimed_builtup_m2=8600,
         story="Clean file with digitally signed certificates"),
    dict(id="INS-007", name="Prototype Institute of Science", region="Eastern",
         address="NH-44 Service Road, Prototype Nagar", center=(20.1305, 79.1920), claimed_builtup_m2=14900,
         story="Completion certificate edited after signing; 5 faculty also declared by Example Institute"),
    dict(id="INS-008", name="Specimen School of Architecture", region="Eastern",
         address="Riverfront Lane, Specimen City", center=(20.1505, 79.2220), claimed_builtup_m2=7400,
         permitted_use="Ground & first floor - studios and classrooms; Basement - parking and storage only",
         floor_usage={"Basement": "library and reading room"},
         story="Basement used as a library although the fire NOC permits storage only; affidavit address differs"),
    dict(id="INS-009", name="Illustrative Institute of Technology", region="Southern",
         address="Temple Street Extension, Illustrative Town", center=(20.1705, 79.2520), claimed_builtup_m2=19400,
         story="Scanned fire NOC with a pasted date patch; issuer record shows it expired"),
    dict(id="INS-010", name="Reference College of Engineering", region="Southern",
         address="Airport Road, Reference Nagar", center=(20.1905, 79.2820), claimed_builtup_m2=15200,
         story="Bank says it never issued the FDR; seal does not match the fire authority's specimen"),
]


def make_docs(w, inst, victim):
    i = inst["id"]
    docs = []
    add = lambda r, t="genuine": docs.append((r["path"], t))  # noqa: E731
    if i == "INS-002":
        add(w.fire_noc(inst, "F3_seal_reuse", victim=victim), "F3_seal_reuse")
    elif i == "INS-005":
        add(w.fire_noc(inst, "F2_date_overlay"), "F2_date_overlay")
    elif i == "INS-009":
        add(w.fire_noc(inst, "F9_scan_paste"), "F9_scan_paste")
    elif i == "INS-010":
        add(w.fire_noc(inst, "F7_fake_seal"), "F7_fake_seal")
    elif i in ("INS-001",):
        pass  # created first as the victim
    else:
        add(w.fire_noc(inst, "genuine", signed=i in ("INS-006", "INS-008")))
    if i == "INS-005":
        add(w.fire_noc(inst, "F4_qr_untrusted"), "F4_qr_untrusted")
    add(w.completion(inst, "F5_post_sign_edit" if i == "INS-007" else "genuine"),
        "F5_post_sign_edit" if i == "INS-007" else "genuine")
    add(w.lease(inst, years=14 if i == "INS-004" else 33), "deficiency" if i == "INS-004" else "genuine")
    add(w.fdr(inst, "fake" if i == "INS-010" else "genuine"), "F8_fdr_denied" if i == "INS-010" else "genuine")
    add(w.affidavit(inst, address="Plot 2, Riverside Colony, Elsewhere" if i == "INS-008" else None),
        "address_mismatch" if i == "INS-008" else "genuine")
    add(w.faculty(inst, FAC_B if i == "INS-007" else ([f"FAC-SC-{300000 + int(i[-3:]) * 1000 + k:06d}" for k in range(12)]
                                                       if i != "INS-001" else FAC_A)),
        "faculty_duplicate" if i == "INS-007" else "genuine")
    add(w.photo(inst, inside=i != "INS-003", recent=i != "INS-003"), "photo_elsewhere" if i == "INS-003" else "genuine")
    return docs


def main():
    db.reset()
    pass  # issuer records accumulate; the sandbox serves both demo and evaluation records
    w = gc.World(config.DATA / "demo_docs", seed=7)
    victim = None
    for inst in INSTITUTIONS:
        inst["campus_geojson"] = json.dumps(gc.campus(inst["center"]))
        fp = gc.footprints(inst["center"], SMALL if inst["id"] == "INS-003" else BIG)
        (GEO / f"{inst['id']}.geojson").write_text(json.dumps(fp))
        with db.tx() as c:
            c.execute("INSERT INTO institutions VALUES(?,?,?,?,?,?,?,1)",
                      (inst["id"], inst["name"], inst["region"], inst["address"], inst["campus_geojson"],
                       inst["claimed_builtup_m2"], 360))
            app_id = f"EOA-2027-{inst['id'][-3:]}"
            c.execute("INSERT INTO applications VALUES(?,?,?,?,?,?,?,?)",
                      (app_id, inst["id"], "EoA", "2027-28", pipeline.now(), "queued", 0,
                       json.dumps({"floor_usage": inst.get("floor_usage", {}), "story": inst["story"]})))
        inst["app_id"] = app_id
        if inst["id"] == "INS-001":
            victim = w.fire_noc(inst, "genuine", signed=False)
            inst["_first"] = [(victim["path"], "genuine")]
    w.save()  # issuer sandbox reads records lazily, so later records are served too

    for inst in INSTITUTIONS:
        docs = inst.pop("_first", []) + make_docs(w, inst, victim)
        w.save()
        for path, truth in docs:
            pipeline.add_document(inst["app_id"], str(path), Path(path).name, truth=truth)
    w.save()

    for inst in INSTITUTIONS:
        for d in db.q("SELECT id FROM documents WHERE application_id=?", (inst["app_id"],)):
            pipeline.process_document(d["id"])
    # The bank answers its confirmation requests (Tier 3). INS-004's request is left unanswered.
    for conf in db.q("SELECT * FROM confirmations"):
        doc = db.q1("SELECT * FROM documents WHERE id=?", (conf["document_id"],))
        if doc["application_id"].endswith("004"):
            continue
        state = "no" if doc["truth"] == "F8_fdr_denied" else "yes"
        with db.tx() as c:
            c.execute("UPDATE confirmations SET state=?, answered_at=? WHERE token=?", (state, pipeline.now(), conf["token"]))
        audit.log("issuer:ISS-BANK", f"confirmation.{state}", conf["document_id"], {"reference": conf["reference"]})
        pipeline.process_document(doc["id"])
    for inst in INSTITUTIONS:
        fp = json.loads((GEO / f"{inst['id']}.geojson").read_text())
        s, r = pipeline.process_application(inst["app_id"], footprints=fp)
        print(f"{inst['app_id']}  {inst['name']:<38} {s:<24} risk {r}")


if __name__ == "__main__":
    main()
