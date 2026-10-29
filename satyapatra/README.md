# SatyaPatra (सत्यपत्र)

AI-assisted verification of AICTE approval documents — SIH 2026, PS **SIH26261** (AICTE, Smart Automation).

SatyaPatra reads every document an institution uploads, checks it against the Approval Process Handbook,
asks the issuing authority whether it really issued it, looks for tampering, compares physical claims with
open satellite data, and gives each document one of the six statuses named in the PS — with evidence.
The officer decides; every check and decision goes into a hash-chained audit ledger.

## Run it on a laptop (demo mode: SQLite, local files, in-process workers)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/sandbox_setup.py                 # sandbox issuer PKI + seal specimens
.venv/bin/uvicorn issuer_sandbox.app:app --port 8100 &     # sandbox issuer portal (Tier 2/3)
.venv/bin/python scripts/seed_demo.py                      # 10 fictional institutions
.venv/bin/python scripts/evaluate.py 15                    # 195 labelled documents -> data/eval/results.json
cd ../frontend && npm ci && npm run build && cd ../backend
.venv/bin/uvicorn app.main:app --port 8000                 # console at http://127.0.0.1:8000
```

## Run it like production (PostgreSQL, Redis workers, MinIO, Ollama)

```bash
docker compose up --build
```

The same code switches backends through environment variables: `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT`,
`SATYA_OLLAMA`, `SATYA_AUTH=1`.

## Layout

| Path | What it is |
|---|---|
| `backend/app/engines/read.py` | Classify, extract fields with page positions, OCR (RapidOCR), local-LLM fallback with grounding check |
| `backend/app/engines/check.py` | Handbook rules from `rules.yaml`, cross-document and cross-institution checks |
| `backend/app/engines/confirm.py` | Tier 1 PDF signatures (pyHanko) and QR allow-list, Tier 2 issuer portal, Tier 3 signed confirmation links |
| `backend/app/engines/detect.py` | PDF structure forensics, white-patch edits, font mismatch, ELA, reused scans, seal-specimen matching (ORB + RANSAC) |
| `backend/app/engines/see.py` | Building footprints vs claimed area (Open Buildings / OSM format, live Overpass), photo GPS and date |
| `backend/app/pipeline.py` | Runs the engines and turns findings into the six statuses and a 0-100 risk score |
| `backend/app/audit.py` | SHA-256 hash-chained audit ledger |
| `backend/issuer_sandbox/` | Stand-in issuer portal, reached over HTTP like a real one |
| `backend/scripts/` | PKI setup, synthetic document generator, demo seeding, evaluation |
| `frontend/` | Officer console (React 18, TypeScript, Vite, TanStack Query) on UX4G 3.0 tokens; design rules and sources in `frontend/DESIGN.md` |

All institutions, issuers, people and numbers in the demo are fictional.

## Adding a new kind of document

Every document type (fire NOC, lease deed, FDR …) is registered in the same five places. To add one, for example a **pollution NOC**, use a short id such as `pollution_noc` everywhere:

1. **Recognise it**: `backend/app/engines/read.py`. Add the id to `DOC_TYPES` with 2 or 3 phrases that only this document prints (its title, a unique label), and to `LABELS` with each field's printed label, e.g. `"noc_no": "Consent No."`, `"valid_until": "Valid Until"`.
2. **Say who issues it**: `backend/app/registry.py`. Add the id to an issuer's `doc_types`, or add a new issuer with its Tier 1 signing certificate or official QR domains, its Tier 2 lookup URL and reference field, and its Tier 3 registered contact. Never use contact details printed on the document itself.
3. **Write its rules**: `backend/app/rules.yaml`. Add the id to the `required_documents` list of the right category, then one rule per handbook requirement (`doc_type`, `field`, `kind`, `severity: hard` or `soft`, and the APH clause in `ref`). No code change is needed for rules.
4. **Name it on screen**: `backend/app/pipeline.py` (`LABEL`, the phrase used in findings) and `frontend/src/api.ts` (`DOC_LABEL`, the name shown in the console).
5. **Test it**: put a genuine and a forged sample in `backend/data/samples/` (named `NN__What_it_shows.pdf`), and for a measured result add a generator to `scripts/generate_corpus.py` and rerun `scripts/evaluate.py`.

Real documents: only add copies the team is allowed to share, with personal details removed. Public sources (for example, EoA letters and issuer sample formats) are preferred.
