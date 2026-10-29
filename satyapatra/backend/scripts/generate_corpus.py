"""Builds the synthetic world SatyaPatra is demonstrated and measured on.

  python scripts/generate_corpus.py demo   -> 10 fictional institutions, each showing one real-world fraud pattern
  python scripts/generate_corpus.py eval   -> a labelled test set (genuine + 9 forgery types) in data/eval/

All institutions, issuers, numbers and people are fictional. Issuer records go to
issuer_sandbox/records.json, which the sandbox issuer portal serves.
"""
import io
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import piexif
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docgen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PKI = ROOT / "pki"
RECORDS = ROOT / "issuer_sandbox" / "records.json"
ISSUER = "http://127.0.0.1:8100"
TODAY = date.today()
FIRE = "Sample State Fire & Emergency Services"
MUNI = "Sample Municipal Corporation"
REG = "Sample Sub-Registrar Office"
BANK = "Sample National Bank"
MASTERS = {k: Image.open(PKI / f"{k}-seal.png") for k in ("ISS-FIRE", "ISS-MUNI", "ISS-REG", "ISS-BANK", "NOTARY", "FAKE-FIRE")}


def d(x):
    return x.strftime("%d-%m-%Y")


def load_records():
    if RECORDS.exists():
        return json.loads(RECORDS.read_text())
    return {"fire_noc": {}, "building_completion": {}, "lease_deed": {}, "fdr": {}}


def key(ref):
    return ref.replace("/", "-")


class World:
    def __init__(self, outdir, seed):
        self.out = Path(outdir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.rnd = random.Random(seed)
        self.records = load_records()
        self.counter = seed * 1000

    def n(self):
        self.counter += self.rnd.randint(3, 41)
        return self.counter

    # ---------------------------------------------------------------- fire NOC
    def fire_noc(self, inst, variant="genuine", signed=False, victim=None, fmt="pdf"):
        ref = f"FS/2026/{self.n():05d}"
        issued = TODAY - timedelta(days=self.rnd.randint(40, 200))
        valid = issued + timedelta(days=365)
        permitted = inst.get("permitted_use", "Ground & first floor - classrooms and labs; Basement - parking and storage only")
        name, addr = inst["name"], inst["address"]
        rec_name, rec_addr = name, addr
        seal = docgen.scan(MASTERS["ISS-FIRE"], seed=self.rnd.randint(1, 10**9))
        qr = f"{ISSUER}/v/{key(ref)}"
        register = True
        shown_valid = valid

        if variant == "F1_fake_number":
            register = False
        elif variant == "F2_date_overlay":
            valid = TODAY - timedelta(days=self.rnd.randint(20, 120))      # truly expired
            issued = valid - timedelta(days=365)
            shown_valid = valid
        elif variant == "F3_seal_reuse":
            ref, rec_name, rec_addr = victim["ref"], victim["name"], victim["address"]
            seal = victim["seal"]
            qr = f"{ISSUER}/v/{key(ref)}"
            register = False  # record already exists under the victim
            issued, valid = victim["issued"], victim["valid"]
            shown_valid = valid
        elif variant == "F4_qr_untrusted":
            register = False
            qr = f"http://verify-firenoc-portal.in/v/{key(ref)}"
        elif variant == "F6_expired":
            issued = TODAY - timedelta(days=self.rnd.randint(400, 600))
            valid = issued + timedelta(days=365)
            shown_valid = valid
        elif variant == "F7_fake_seal":
            register = False
            seal = docgen.scan(MASTERS["FAKE-FIRE"], seed=self.rnd.randint(1, 10**9))
        elif variant == "F9_scan_paste":
            valid = TODAY - timedelta(days=self.rnd.randint(20, 120))
            issued = valid - timedelta(days=365)
            shown_valid = valid

        lines = [f"Issued by: {FIRE} (Sandbox)", f"NOC No.: {ref}", f"Name of Institution: {name}",
                 f"Premises Address: {addr}", f"Date of Issue: {d(issued)}", f"Valid Until: {d(shown_valid)}",
                 f"Permitted Use: {permitted}"]
        sig = docgen.signature_img("dfo", seed=self.rnd.randint(1, 10**9))
        base = self.out / f"{inst['id']}_fire_noc_{variant}_{ref.split('/')[-1]}.pdf"
        docgen.build_pdf(base, "fire_noc", FIRE, lines, seal=seal, sig=sig, qr_url=qr)
        if register:
            self.records["fire_noc"][key(ref)] = {"reference": ref, "issuer": FIRE, "institution": rec_name,
                                                  "address": rec_addr, "issue_date": issued.isoformat(),
                                                  "valid_until": valid.isoformat(), "permitted_use": permitted}
        path = base
        if variant == "F2_date_overlay":
            new_valid = TODAY + timedelta(days=self.rnd.randint(150, 300))
            docgen.overlay_edit(base, base, d(valid), d(new_valid), fontname="Times-Roman", fontsize=10.8)
        elif signed and variant in ("genuine", "F6_expired"):
            path = base.with_name(base.stem + "_signed.pdf")
            docgen.sign_pdf(base, path, PKI / "ISS-FIRE.key", PKI / "ISS-FIRE.pem", PKI / "issuer-ca.pem")
            base.unlink()
        if fmt == "jpg" or variant == "F9_scan_paste":
            path = self._to_scan(path, paste=(variant == "F9_scan_paste"), old=d(valid),
                                 new=d(TODAY + timedelta(days=self.rnd.randint(150, 300))))
        return {"path": path, "ref": ref, "name": name, "address": addr, "seal": seal, "issued": issued, "valid": valid}

    def _to_scan(self, pdf, paste=False, old=None, new=None):
        import fitz
        doc = fitz.open(pdf)
        pg = doc[0]
        hit = pg.search_for(old) if paste else []
        pix = pg.get_pixmap(dpi=150)
        im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        if paste and hit:
            r = hit[0]
            s = 150 / 72
            box = (int(r.x0 * s) - 2, int(r.y0 * s) - 2, int(r.x1 * s) + 30, int(r.y1 * s) + 3)
            patch = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (255, 255, 255))
            dr = ImageDraw.Draw(patch)
            try:
                f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Times New Roman.ttf", 22)
            except Exception:
                f = ImageFont.load_default()
            dr.text((2, 0), new, fill=(25, 25, 25), font=f)
            b = io.BytesIO()
            patch.save(b, "JPEG", quality=55)
            im.paste(Image.open(b), box[:2])
        out = Path(str(pdf).rsplit(".", 1)[0] + "_scan.jpg")
        im.save(out, "JPEG", quality=88)
        Path(pdf).unlink()
        return out

    # ---------------------------------------------------------------- building completion
    def completion(self, inst, variant="genuine"):
        ref = f"BCC/2025/{self.n():05d}"
        issued = TODAY - timedelta(days=self.rnd.randint(300, 900))
        area = inst["claimed_builtup_m2"] if variant != "area_differs" else inst["claimed_builtup_m2"] * 0.62
        lines = [f"Issued by: {MUNI} (Sandbox)", f"Certificate No.: {ref}", f"Owner: {inst['name']}",
                 f"Premises Address: {inst['address']}", f"Total Built-up Area: {area:,.0f} sq m",
                 f"Number of Floors: {inst.get('floors', 4)}", f"Date of Issue: {d(issued)}"]
        base = self.out / f"{inst['id']}_completion_{variant}_{ref.split('/')[-1]}.pdf"
        docgen.build_pdf(base, "building_completion", MUNI, lines,
                         seal=docgen.scan(MASTERS["ISS-MUNI"], seed=self.rnd.randint(1, 10**9)),
                         sig=docgen.signature_img("ee", self.rnd.randint(1, 10**9)), qr_url=f"{ISSUER}/v/{key(ref)}")
        self.records["building_completion"][key(ref)] = {"reference": ref, "issuer": MUNI, "institution": inst["name"],
                                                         "address": inst["address"], "builtup_m2": round(area),
                                                         "issue_date": issued.isoformat()}
        signed = base.with_name(base.stem + "_signed.pdf")
        docgen.sign_pdf(base, signed, PKI / "ISS-MUNI.key", PKI / "ISS-MUNI.pem", PKI / "issuer-ca.pem")
        base.unlink()
        if variant == "F5_post_sign_edit":
            docgen.overlay_edit(signed, signed, f"{area:,.0f} sq m", f"{area * 1.6:,.0f} sq m",
                                fontname="Helvetica", fontsize=10.5)
        return {"path": signed, "ref": ref}

    # ---------------------------------------------------------------- lease, FDR, affidavit, faculty
    def lease(self, inst, years=33):
        ref = f"REG/{TODAY.year - 2}/{self.n():06d}"
        start = TODAY - timedelta(days=730)
        end = start + timedelta(days=int(365.25 * years))
        lines = [f"Registered at: {REG} (Sandbox)", f"Registration No.: {ref}", "Lessor: Fictional Land Trust",
                 f"Lessee: {inst['name']}", f"Premises Address: {inst['address']}", f"Lease Start: {d(start)}",
                 f"Lease End: {d(end)}"]
        p = self.out / f"{inst['id']}_lease_{key(ref)}.pdf"
        docgen.build_pdf(p, "lease_deed", REG, lines, seal=docgen.scan(MASTERS["ISS-REG"], self.rnd.randint(1, 10**9)),
                         sig=docgen.signature_img("sr", self.rnd.randint(1, 10**9)), qr_url=f"{ISSUER}/v/{key(ref)}")
        self.records["lease_deed"][key(ref)] = {"reference": ref, "issuer": REG, "institution": inst["name"],
                                                "address": inst["address"], "lease_end": end.isoformat()}
        return {"path": p, "ref": ref}

    def fdr(self, inst, variant="genuine", amount=1_000_000):
        ref = f"FDR{self.n():08d}"
        dep = TODAY - timedelta(days=200)
        mat = dep + timedelta(days=365 * 5)
        lines = [f"Bank: {BANK} (Sandbox), Institutional Branch", f"FDR No.: {ref}", f"Depositor: {inst['name']}",
                 f"In favour of: Member Secretary, AICTE (pledged)", f"Amount (INR): Rs {amount:,}",
                 f"Date of Deposit: {d(dep)}", f"Maturity Date: {d(mat)}"]
        p = self.out / f"{inst['id']}_fdr_{variant}_{ref}.pdf"
        docgen.build_pdf(p, "fdr", BANK, lines, seal=docgen.scan(MASTERS["ISS-BANK"], self.rnd.randint(1, 10**9)),
                         sig=docgen.signature_img("bm", self.rnd.randint(1, 10**9)))
        self.records["fdr"][ref] = {"reference": ref, "issuer": BANK, "institution": inst["name"],
                                    "amount_inr": amount, "exists": variant == "genuine"}
        return {"path": p, "ref": ref}

    def affidavit(self, inst, address=None):
        lines = ["Deponent: Chairperson of the Managing Society", f"Institution: {inst['name']}",
                 f"Premises Address: {address or inst['address']}", f"Date: {d(TODAY - timedelta(days=30))}",
                 "I solemnly affirm that the information submitted to AICTE is true and correct."]
        p = self.out / f"{inst['id']}_affidavit.pdf"
        docgen.build_pdf(p, "affidavit", "Notarised Affidavit", lines,
                         seal=docgen.scan(MASTERS["NOTARY"], self.rnd.randint(1, 10**9)),
                         sig=docgen.signature_img("np", self.rnd.randint(1, 10**9)))
        return {"path": p}

    def faculty(self, inst, ids):
        rows = [{"name": f"Faculty Member {i + 1:02d}", "id": fid, "role": "Assistant Professor" if i % 3 else "Professor",
                 "joined": f"{2015 + i % 9}"} for i, fid in enumerate(ids)]
        p = self.out / f"{inst['id']}_faculty.pdf"
        docgen.build_pdf(p, "faculty_list", "Institution Declaration", [f"Institution: {inst['name']}",
                         "Declared under the AICTE faculty norms (synthetic data)."], rows=rows)
        return {"path": p}

    def photo(self, inst, inside=True, recent=True, label="Computer lab"):
        im = Image.new("RGB", (1280, 853), (196, 204, 214))
        dr = ImageDraw.Draw(im)
        for r in range(4):
            for c in range(6):
                x, y = 90 + c * 190, 300 + r * 120
                dr.rectangle([x, y, x + 130, y + 70], fill=(40, 46, 58))
                dr.rectangle([x + 10, y + 8, x + 120, y + 60], fill=(70, 120, 170))
                dr.rectangle([x + 40, y + 72, x + 90, y + 82], fill=(90, 90, 90))
        dr.rectangle([0, 0, 1280, 220], fill=(225, 228, 232))
        lat, lon = inst["center"]
        if not inside:
            lat, lon = lat + 0.031, lon - 0.024
        when = (TODAY - timedelta(days=40)) if recent else date(2023, 2, 11)

        def dms(v):
            v = abs(v)
            dd = int(v)
            mm = int((v - dd) * 60)
            ss = round(((v - dd) * 60 - mm) * 60 * 100)
            return ((dd, 1), (mm, 1), (ss, 100))
        ex = {"GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N", piexif.GPSIFD.GPSLatitude: dms(lat),
                      piexif.GPSIFD.GPSLongitudeRef: b"E", piexif.GPSIFD.GPSLongitude: dms(lon)},
              "Exif": {piexif.ExifIFD.DateTimeOriginal: when.strftime("%Y:%m:%d 10:24:00").encode()}}
        p = self.out / f"{inst['id']}_photo_{label.replace(' ', '_').lower()}.jpg"
        im.save(p, "JPEG", quality=90, exif=piexif.dump(ex))
        return {"path": p}

    def save(self):
        RECORDS.parent.mkdir(exist_ok=True)
        RECORDS.write_text(json.dumps(self.records, indent=1))


def campus(center, w=0.0042, h=0.0030):
    lat, lon = center
    return {"type": "Polygon", "coordinates": [[[lon - w / 2, lat - h / 2], [lon + w / 2, lat - h / 2],
                                                [lon + w / 2, lat + h / 2], [lon - w / 2, lat + h / 2], [lon - w / 2, lat - h / 2]]]}


def footprints(center, blocks):
    """Synthetic building footprints in Open Buildings format: (dx, dy, w_m, h_m, height_m)."""
    lat, lon = center
    feats = []
    for dx, dy, wm, hm, ht in blocks:
        x0, y0 = lon + dx / 111_320 / 0.9397, lat + dy / 110_540
        x1, y1 = x0 + wm / 111_320 / 0.9397, y0 + hm / 110_540
        feats.append({"type": "Feature", "properties": {"height_m": ht, "source": "synthetic (Open Buildings format)"},
                      "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}})
    return {"type": "FeatureCollection", "features": feats}
