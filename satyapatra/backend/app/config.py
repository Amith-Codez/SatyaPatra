"""Central settings for the SatyaPatra verification service."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
RENDERS = DATA / "renders"
PKI = ROOT / "pki"
DB_PATH = DATA / "satyapatra.db"
RULES_FILE = ROOT / "app" / "rules.yaml"
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"

for p in (DATA, UPLOADS, RENDERS):
    p.mkdir(parents=True, exist_ok=True)

# Issuer sandbox (stands in for a real issuer's verification portal)
ISSUER_BASE = os.environ.get("SATYA_ISSUER_BASE", "http://127.0.0.1:8100")

# Local LLM (Ollama) used only as a fallback extractor for unfamiliar layouts
OLLAMA_URL = os.environ.get("SATYA_OLLAMA", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("SATYA_OLLAMA_MODEL", "llama3.2:3b")
USE_LLM = os.environ.get("SATYA_USE_LLM", "1") == "1"

# Statuses, worded exactly as in PS SIH26261
VERIFIED = "Verified"
MISMATCH = "Mismatch detected"
EXPIRED = "Expired"
PENDING = "Verification pending"
UNAVAILABLE = "Source unavailable"
REVIEW = "Manual review required"
STATUS_ORDER = [MISMATCH, EXPIRED, REVIEW, PENDING, UNAVAILABLE, VERIFIED]

# Soft-signal weights (add up to a 0-100 risk score). Hard facts set the status directly.
WEIGHTS = {
    "pdf_overlay_edit": 35,
    "field_font_mismatch": 25,
    "post_issue_edit": 15,
    "editor_software": 8,
    "incremental_saves": 6,
    "ela_hotspot": 25,
    "scan_reused": 40,
    "specimen_mismatch": 30,
    "qr_untrusted": 45,
    "llm_ungrounded": 10,
}
REVIEW_THRESHOLD = 30   # soft score at or above this -> Manual review required
