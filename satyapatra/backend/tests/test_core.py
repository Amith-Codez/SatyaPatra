"""Core guarantees, run with:  DATABASE_URL=sqlite:///data/test.db pytest -q"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'test.db'}")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app import audit, config, db  # noqa: E402
from app.engines import detect  # noqa: E402
from app.pipeline import decide  # noqa: E402


def r(outcome, severity="hard", weight=0, engine="CONFIRM"):
    return {"engine": engine, "outcome": outcome, "severity": severity, "weight": weight}


def test_hard_fact_wins_over_everything():
    status, risk = decide([r(config.VERIFIED), r(config.MISMATCH)])
    assert status == config.MISMATCH and risk >= 90


def test_soft_signals_alone_never_mark_a_forgery():
    status, _ = decide([r(config.VERIFIED), r("flag", "soft", 35, "DETECT"), r("flag", "soft", 25, "DETECT")])
    assert status == config.REVIEW


def test_network_failure_is_not_a_mismatch():
    status, _ = decide([r(config.UNAVAILABLE)])
    assert status == config.UNAVAILABLE


def test_unconfirmed_document_is_not_auto_verified():
    status, _ = decide([r(config.VERIFIED, "info", engine="READ")])
    assert status == config.REVIEW


def test_audit_chain_detects_tampering():
    db.reset()
    for i in range(5):
        audit.log("test", "event", f"S{i}", {"i": i})
    assert audit.verify_chain()["ok"]
    with db.tx() as c:
        c.execute("UPDATE audit SET payload=? WHERE seq=3", ('{"i": 999}',))
    res = audit.verify_chain()
    assert not res["ok"] and res["broken_at"] == 3


def test_seal_specimen_separates_genuine_from_counterfeit():
    import docgen
    from PIL import Image
    pki = ROOT / "pki"
    if not (pki / "ISS-FIRE-seal.png").exists():
        return
    genuine = [detect.seal_match(str(pki / "ISS-FIRE-seal.png"), docgen.scan(Image.open(pki / "ISS-FIRE-seal.png"), s))
               for s in range(1, 6)]
    fake = [detect.seal_match(str(pki / "ISS-FIRE-seal.png"), docgen.scan(Image.open(pki / "FAKE-FIRE-seal.png"), s))
            for s in range(1, 6)]
    assert min(genuine) > detect.SEAL_MIN_INLIERS > max(fake)
