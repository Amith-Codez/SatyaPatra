# SatyaPatra · SIH 2026 · PS SIH26261 (AICTE)

Every AICTE approval document confirmed with the authority that issued it, with the proof marked on the page.

## What is in this folder

| Path | What it is |
|---|---|
| `deck/SatyaPatra_SIH26261_Idea.pdf` | **The file to upload**: the 6-slide idea deck on the official SIH 2026 template |
| `deck/SatyaPatra_SIH26261_Idea.pptx` | The same deck, editable (fill in [Team Name], [Team ID] and the three links on slide 2) |
| `deck/build_deck.py` | Builds the .pptx from `SIH2026-official-template.pptx`, the images in `img/` and `../satyapatra/backend/data/eval/results.json` |
| `deck/img-src/` → `deck/img/` | Diagram sources (HTML) and their renders; `render.sh` re-renders one |
| `deck/cdp_clip.py`, `deck/cdp_shot.py` | Capture screenshots from the running console for the slides |
| `deck/kn2pdf.sh` | Exports the .pptx to PDF with Keynote |
| `satyapatra/` | The working prototype; see `satyapatra/README.md` to run it |
| `satyapatra/frontend/DESIGN.md` | Why the console looks and behaves the way it does, with sources |
| `satyapatra-sih2026.html` | Strategy site: research, real cases, judge Q&A (published as a private Claude artifact) |

The plain-language builder's guide, covering every engine, colour, judge question and the presentation plan, is a separate Claude Doc: "SatyaPatra: The Complete Builder's Guide".

## Rebuild the deck after changing the app

First, start the prototype (see `satyapatra/README.md`) so the console runs on http://localhost:8000. Then run these from `deck/`:

```bash
PY=../satyapatra/backend/.venv/bin/python
$PY cdp_clip.py "http://localhost:8000/app/EOA-2027-005?doc=DOC-341E51FAF5" img/shot_evidence.png ".workbench" 4 12
$PY cdp_clip.py "http://localhost:8000/verify?sample=04__Fire_NOC_with_fake_QR_site.pdf" img/shot_verify.png ".page > .section" 7 12
$PY cdp_clip.py "http://localhost:8000/app/EOA-2027-003?tab=geo" img/shot_geo.png ".g-main" 6 12
$PY build_deck.py
./kn2pdf.sh "$PWD/SatyaPatra_SIH26261_Idea.pptx" "$PWD/SatyaPatra_SIH26261_Idea.pdf"
```

Notes on the steps above:

- **Evidence crop.** The slide uses only the document and its findings, so crop `img/shot_evidence.png` to drop the document list on the left. At 2400 px wide, that means keeping x ≥ 520 and y ≤ 1270.
- **Document IDs.** `DOC-…` IDs change if the demo database is re-seeded. If that happens, open the application in the console and copy the new ID.

## Ground rules kept throughout

- All institutions and issuers in the demo are fictional sandbox entities.
- Every number in the deck comes from `data/eval/results.json` or a measured run.
- Accuracy figures are from 195 synthetic labelled documents; real-world rates are measured in the pilot.
