"""Measure SatyaPatra on a labelled test set: genuine documents plus 8 forgery types.

  python scripts/evaluate.py [per_group]

Uses its own database (data/eval/eval.db) so the demo data is untouched.
Writes data/eval/results.json with per-group catch rates, false-alarm rate and timings.
"""
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "data" / "eval"
EVAL.mkdir(parents=True, exist_ok=True)
(EVAL / "eval.db").unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{EVAL / 'eval.db'}"
os.environ["SATYA_USE_LLM"] = "0"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_corpus as gc  # noqa: E402
from app import config, db, pipeline  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 15
GROUPS = [
    ("genuine", "Fire NOC, genuine PDF"), ("genuine_signed", "Fire NOC, genuine, digitally signed"),
    ("genuine_scan", "Fire NOC, genuine, scanned (JPEG)"), ("genuine_completion", "Completion certificate, genuine, signed"),
    ("genuine_lease", "Lease deed, genuine"),
    ("F1_fake_number", "Fake NOC number, official-looking"), ("F2_date_overlay", "Validity date pasted over"),
    ("F3_seal_reuse", "Another college's NOC re-badged (seal scan reused)"),
    ("F4_qr_untrusted", "QR code to a fake verification site"), ("F5_post_sign_edit", "Edited after the issuer signed it"),
    ("F6_expired", "Genuine but expired"), ("F7_fake_seal", "Counterfeit seal + fake number"),
    ("F9_scan_paste", "Scanned NOC with a pasted date patch"),
]


def main():
    w = gc.World(EVAL / "docs", seed=91)
    rows = []
    for k in range(N):
        inst = dict(id=f"EV-{k:03d}", name=f"Evaluation Institute {k:03d}", region="Test",
                    address=f"Test Plot {k + 1}, Evaluation Road, Testpur", center=(21.0 + k * 0.01, 80.0),
                    claimed_builtup_m2=10000 + 300 * k)
        inst["campus_geojson"] = json.dumps(gc.campus(inst["center"]))
        app_id = f"EVAL-{k:03d}"
        with db.tx() as c:
            c.execute("INSERT INTO institutions VALUES(?,?,?,?,?,?,?,1)", (inst["id"], inst["name"], "Test",
                      inst["address"], inst["campus_geojson"], inst["claimed_builtup_m2"], 120))
            c.execute("INSERT INTO applications VALUES(?,?,?,?,?,?,?,?)",
                      (app_id, inst["id"], "EoA", "2027-28", pipeline.now(), "queued", 0, "{}"))
        victim = w.fire_noc(dict(inst, id=inst["id"] + "v", name=inst["name"] + " Victim",
                                 address="Victim Lane " + str(k)), "genuine")
        # the victim's own NOC is filed by a different institution first
        vid = f"EV-V{k:03d}"
        with db.tx() as c:
            c.execute("INSERT INTO institutions VALUES(?,?,?,?,?,?,?,1)", (vid, victim["name"], "Test", victim["address"],
                      inst["campus_geojson"], 10000, 120))
            c.execute("INSERT INTO applications VALUES(?,?,?,?,?,?,?,?)",
                      (f"EVAL-V{k:03d}", vid, "EoA", "2027-28", pipeline.now(), "queued", 0, "{}"))
        w.save()
        pipeline.process_document(pipeline.add_document(f"EVAL-V{k:03d}", str(victim["path"]), victim["path"].name, "victim"))
        made = {
            "genuine": w.fire_noc(inst, "genuine")["path"],
            "genuine_signed": w.fire_noc(inst, "genuine", signed=True)["path"],
            "genuine_scan": w.fire_noc(inst, "genuine", fmt="jpg")["path"],
            "genuine_completion": w.completion(inst)["path"],
            "genuine_lease": w.lease(inst)["path"],
            "F1_fake_number": w.fire_noc(inst, "F1_fake_number")["path"],
            "F2_date_overlay": w.fire_noc(inst, "F2_date_overlay")["path"],
            "F3_seal_reuse": w.fire_noc(inst, "F3_seal_reuse", victim=victim)["path"],
            "F4_qr_untrusted": w.fire_noc(inst, "F4_qr_untrusted")["path"],
            "F5_post_sign_edit": w.completion(inst, "F5_post_sign_edit")["path"],
            "F6_expired": w.fire_noc(inst, "F6_expired", signed=k % 2 == 0)["path"],
            "F7_fake_seal": w.fire_noc(inst, "F7_fake_seal")["path"],
            "F9_scan_paste": w.fire_noc(inst, "F9_scan_paste")["path"],
        }
        w.save()
        for group, path in made.items():
            doc_id = pipeline.add_document(app_id, str(path), Path(path).name, truth=group)
            t0 = time.perf_counter()
            status, risk = pipeline.process_document(doc_id)
            ms = (time.perf_counter() - t0) * 1000
            codes = [c["code"] for c in db.q("SELECT code,outcome FROM checks WHERE document_id=?", (doc_id,))
                     if c["outcome"] != config.VERIFIED]
            rows.append({"group": group, "status": status, "risk": risk, "ms": round(ms), "codes": codes,
                         "kind": "scan" if str(path).endswith(".jpg") else "pdf"})
        print(f"institution {k + 1}/{N} done", flush=True)

    summary = []
    for g, label in GROUPS:
        rs = [r for r in rows if r["group"] == g]
        genuine = g.startswith("genuine")
        if genuine:
            good = sum(r["status"] == config.VERIFIED for r in rs)
            metric = "verified"
        elif g == "F6_expired":
            good = sum(r["status"] == config.EXPIRED for r in rs)
            metric = "marked expired"
        else:
            good = sum(r["status"] in (config.MISMATCH, config.REVIEW, config.EXPIRED) for r in rs)
            metric = "caught"
        caught_hard = sum(r["status"] in (config.MISMATCH, config.EXPIRED) for r in rs)
        codes = {}
        for r in rs:
            for c in set(r["codes"]):
                codes[c] = codes.get(c, 0) + 1
        summary.append({"group": g, "label": label, "n": len(rs), "ok": good, "metric": metric,
                        "rate": round(good / len(rs), 3) if rs else None, "hard": caught_hard,
                        "signals": dict(sorted(codes.items(), key=lambda x: -x[1])),
                        "median_ms": statistics.median([r["ms"] for r in rs]) if rs else None})
    forged = [r for r in rows if not r["group"].startswith("genuine")]
    genuine = [r for r in rows if r["group"].startswith("genuine")]
    out = {
        "documents": len(rows), "forged": len(forged), "genuine": len(genuine),
        "catch_rate": round(sum(r["status"] != config.VERIFIED for r in forged) / len(forged), 3),
        "false_alarm_rate": round(sum(r["status"] != config.VERIFIED for r in genuine) / len(genuine), 3),
        "median_ms_pdf": statistics.median([r["ms"] for r in rows if r["kind"] == "pdf"]),
        "median_ms_scan": statistics.median([r["ms"] for r in rows if r["kind"] == "scan"]),
        "groups": summary,
    }
    (EVAL / "results.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "groups"}, indent=1))
    for s in summary:
        print(f"{s['label']:<52} {s['ok']}/{s['n']} {s['metric']:<15} median {s['median_ms']} ms")


if __name__ == "__main__":
    main()
