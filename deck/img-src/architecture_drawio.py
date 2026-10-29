"""Build the SatyaPatra flow diagram as an editable draw.io file.

usage (inside deck/):  ../satyapatra/backend/.venv/bin/python img-src/architecture_drawio.py
writes img-src/architecture.drawio (open it at app.diagrams.net) and img-src/architecture.url
(the same diagram as a #R link that opens straight in the draw.io editor).
Icons are the Lucide set the console uses, read from the frontend's node_modules.
"""
import base64
import re
import urllib.parse
import zlib
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

HERE = Path(__file__).resolve().parent
ICONS = HERE.parents[1] / "satyapatra/frontend/node_modules/lucide-react/dist/esm/icons"
W, H = 1400, 850
FONT = "Helvetica"

# role colours (fill, stroke, text) in the style of the reference flowchart
INST = ("#CFE2F3", "#3D85C6", "#0B2A4A")
OFFICER = ("#3C78D8", "#1C4587", "#FFFFFF")
ENGINE = ("#8E7CC3", "#4C3A8C", "#FFFFFF")
DECIDE = ("#5E4AA8", "#3A2A7A", "#FFFFFF")
DATA = ("#F3F3F3", "#8C8C8C", "#262626")
ISSUER = ("#F9CB9C", "#B45F06", "#3D1F00")
STEP = ("#FFD966", "#BF9000", "#3D2E00")
FORWARD = ("#B6D7A8", "#38761D", "#173D0B")
INSPECT = ("#F9CB9C", "#B45F06", "#3D1F00")
CLARIFY = ("#FFE599", "#BF9000", "#3D2E00")

cells, n = [], [1]


def nid():
    n[0] += 1
    return f"c{n[0]}"


def icon_uri(name, color):
    src = (ICONS / f"{name}.js").read_text()
    body = "".join(f"<{tag} " + " ".join(f'{k}="{v}"' for k, v in re.findall(r'(\w+): "([^"]*)"', attrs) if k != "key") + "/>"
                   for tag, attrs in re.findall(r'\[\s*"(\w+)",\s*\{([^}]*)\}\s*\]', src))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" '
           f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
    return "data:image/svg+xml," + base64.b64encode(svg.encode()).decode()


def vertex(x, y, w, h, value, style):
    i = nid()
    cells.append(f'<mxCell id="{i}" value={quoteattr(value)} style="{style}" vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    return i


def label(title, sub=None, tsize=17, ssize=13):
    t = f'<b style="font-size:{tsize}px">{escape(title)}</b>'
    return t + (f'<br><span style="font-size:{ssize}px">{escape(sub)}</span>' if sub else "")


def node(x, y, w, h, title, sub, colors, icon=None, rounded=True, tsize=17, ssize=13):
    fill, stroke, font = colors
    style = (f"rounded={1 if rounded else 0};arcSize=12;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
             f"strokeWidth=2;fontColor={font};fontFamily={FONT};align={'left' if icon else 'center'};verticalAlign=middle;"
             f"spacingLeft={46 if icon else 6};spacingRight=6;")
    i = vertex(x, y, w, h, label(title, sub, tsize, ssize), style)
    if icon:
        vertex(x + 13, y + (h - 24) / 2, 24, 24, "", f"shape=image;image={icon_uri(icon, font)};aspect=fixed;imageAspect=0;")
    return i


def text(x, y, w, h, value, size=12, color="#333333", bold=False, align="center", bg=True):
    style = (f"text;html=1;whiteSpace=wrap;fontFamily={FONT};fontSize={size};fontColor={color};align={align};verticalAlign=middle;"
             f"{'fontStyle=1;' if bold else ''}{'labelBackgroundColor=#FFFFFF;' if bg else ''}")
    return vertex(x, y, w, h, escape(value), style)


def edge(src, dst, pts=(), exit=None, entry=None, dashed=False, both=False, color="#3A3A3A"):
    i = nid()
    style = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeWidth=2;strokeColor={color};endArrow=block;endFill=1;endSize=7;"
             f"{'dashed=1;dashPattern=6 4;' if dashed else ''}{'startArrow=block;startFill=1;startSize=7;' if both else ''}")
    if exit:
        style += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
    if entry:
        style += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    p = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts)
    cells.append(f'<mxCell id="{i}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
                 f'<mxGeometry relative="1" as="geometry">{f"<Array as=\"points\">{p}</Array>" if p else ""}</mxGeometry></mxCell>')


# ---------------------------------------------------------------- top: start and sign-in
start = vertex(668, 2, 64, 64, "<b>START</b>", f"ellipse;whiteSpace=wrap;html=1;fillColor=#8BC48A;strokeColor=#2E7D32;strokeWidth=2;"
                                              f"fontColor=#10381A;fontFamily={FONT};fontSize=14;")
signin = node(580, 86, 240, 60, "Role-based sign-in", "JWT roles · government SSO", STEP, "log-in")
edge(start, signin)
vertex(300, 70, 26, 26, "", f"shape=image;image={icon_uri('school', '#0B2A4A')};aspect=fixed;")
text(330, 70, 150, 26, "Institution sign-in", 13, "#0B2A4A", True, "left", bg=False)
vertex(1030, 70, 26, 26, "", f"shape=image;image={icon_uri('badge-check', '#1C4587')};aspect=fixed;")
text(1060, 70, 150, 26, "AICTE officer sign-in", 13, "#1C4587", True, "left", bg=False)

# ---------------------------------------------------------------- institution column
upload = node(20, 186, 230, 84, "Uploads documents", "fire NOC · lease deed · FDR · affidavit · faculty list · campus photos",
              INST, "cloud-upload")
status = node(20, 716, 230, 80, "Sees the result", "6 PS statuses, evidence marked on the page", INST, "eye")
edge(signin, upload, [(135, 116)], exit=(0, 0.5), entry=(0.5, 0))
edge(status, upload, exit=(0.9, 0), entry=(0.9, 1))
vertex(234, 380, 24, 250, "re-submits the corrected file", f"text;html=1;horizontal=0;fontFamily={FONT};fontSize=12;fontColor=#333333;align=center;verticalAlign=middle;")

# colour key
vertex(20, 318, 178, 206, "", "rounded=1;arcSize=6;fillColor=#FFFFFF;strokeColor=#D0D0D0;strokeWidth=1;")
text(32, 326, 150, 20, "COLOUR KEY", 12, "#555555", True, "left", bg=False)
for k, (name, (fill, stroke, _)) in enumerate([("Institution", INST), ("AICTE officer", OFFICER), ("Verification engine", ENGINE),
                                               ("Knowledge & data", DATA), ("Issuing authority", ISSUER), ("Decision step", STEP)]):
    y = 352 + k * 27
    vertex(32, y + 2, 18, 18, "", f"rounded=1;arcSize=20;fillColor={fill};strokeColor={stroke};strokeWidth=2;")
    text(58, y, 135, 22, name, 13, "#262626", False, "left", bg=False)

# ---------------------------------------------------------------- API and the five engines
queue = node(300, 192, 260, 72, "API + job queue", "beside the AICTE portal · FastAPI · Redis workers · original kept by SHA-256", DATA, "server-cog")
edge(upload, queue)
text(252, 202, 46, 18, "upload", 12, bg=False)
vertex(290, 282, 280, 476, "", "rounded=1;arcSize=4;fillColor=#F5F2FC;strokeColor=#8E7CC3;strokeWidth=2;dashed=1;dashPattern=8 5;")
text(300, 287, 200, 20, "VERIFICATION PIPELINE", 12, "#4C3A8C", True, "left", bg=False)
eng = {}
for k, (key, title, sub, ic) in enumerate([
        ("read", "READ", "classify · OCR · fields", "scan-text"),
        ("check", "CHECK", "APH 2024-27 handbook rules", "list-checks"),
        ("confirm", "CONFIRM", "ask the issuer, 3 tiers", "shield-check"),
        ("detect", "DETECT", "tampering and reuse signs", "scan-search"),
        ("see", "SEE", "satellite area · photo GPS", "satellite"),
        ("decide", "DECIDE", "6 statuses · risk 0-100", "scale")]):
    eng[key] = node(310, 312 + k * 72, 240, 58, title, sub, DECIDE if key == "decide" else ENGINE, ic)
edge(queue, eng["read"], exit=(0.8462, 1), entry=(0.875, 0))
keys = list(eng)
for a, b in zip(keys, keys[1:]):
    edge(eng[a], eng[b])
text(296, 735, 268, 20, "every document · median 0.14 s per PDF", 12, "#4C3A8C", bg=False)

# ---------------------------------------------------------------- what each engine consults
ai = node(610, 312, 250, 58, "Local AI · Llama 3.2 3B", "only for unfamiliar layouts; every value grounded", DATA, "cpu")
rules = node(610, 384, 250, 58, "Rulebook (YAML)", "each rule cites its APH clause", DATA, "book-open-check")
issuers = node(610, 456, 250, 58, "Issuing authorities", "signature / QR · portal lookup · confirm link", ISSUER, "landmark")
memory = node(610, 528, 250, 58, "Cross-college memory", "same seal or faculty at 2 colleges", DATA, "link")
geo = node(610, 600, 250, 58, "Open Buildings · OSM", "footprints vs claimed built-up area", DATA, "globe")
edge(eng["read"], ai, dashed=True, both=True, color="#7F7F7F")
edge(rules, eng["check"], dashed=True, color="#7F7F7F")
edge(eng["confirm"], issuers, both=True, color="#B45F06")
edge(eng["detect"], memory, dashed=True, both=True, color="#7F7F7F")
edge(geo, eng["see"], dashed=True, color="#7F7F7F")

# ---------------------------------------------------------------- the database
db = vertex(650, 676, 170, 112, '<br><b style="font-size:15px">SYSTEM DATABASE</b><br><span style="font-size:12px">PostgreSQL · evidence · statuses</span>',
            f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=12;fillColor=#FFFFFF;strokeColor=#434343;strokeWidth=2;"
            f"fontColor=#262626;fontFamily={FONT};verticalAlign=middle;")
vertex(723, 692, 24, 24, "", f"shape=image;image={icon_uri('database', '#262626')};aspect=fixed;")
edge(eng["decide"], db, exit=(1, 0.5), entry=(0, 0.23))
text(566, 676, 80, 18, "write result", 12, bg=False)
edge(db, status, exit=(0, 0.84), entry=(1, 0.675))
text(380, 776, 230, 18, "read status, findings and evidence", 12, bg=False)
ledger = node(860, 748, 190, 56, "Audit ledger", "SHA-256 hash chain", DATA, "scroll-text")
edge(db, ledger, exit=(1, 0.89), entry=(0, 0.5))

# ---------------------------------------------------------------- officer column
queue_ui = node(1170, 186, 210, 84, "Officer risk queue", "riskiest first · search · filters", OFFICER, "layout-dashboard")
review = node(1170, 330, 210, 76, "Reviews evidence", "numbered boxes on the page + issuer's record", OFFICER, "search")
edge(signin, queue_ui, [(1275, 116)], exit=(1, 0.5), entry=(0.5, 0))
edge(queue_ui, review)
edge(db, review, [(905, 702), (905, 368)], exit=(1, 0.23), entry=(0, 0.5))
text(915, 348, 245, 18, "retrieve the ranked queue + evidence", 12)
decide = vertex(1210, 438, 130, 94, '<b style="font-size:15px">Officer<br>decides</b>',
                f"rhombus;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#1C4587;strokeWidth=2;fontColor=#1C4587;fontFamily={FONT};")
edge(review, decide)
chips = [node(930, 584, 140, 56, "Request clarification", None, CLARIFY, tsize=14),
         node(1085, 584, 140, 56, "Send for inspection", None, INSPECT, tsize=14),
         node(1240, 584, 140, 56, "Forward to next stage", None, FORWARD, tsize=14)]
for c, cx in zip(chips, (1000, 1155, 1310)):
    edge(decide, c, [(1275, 560), (cx, 560)], exit=(0.5, 1), entry=(0.5, 0))
recorded = node(1047, 684, 216, 56, "Decision recorded", "officer's note + time", STEP, "clipboard-check")
for c, cx in zip(chips, (1000, 1155, 1310)):
    edge(c, recorded, [(cx, 664), (1155, 664)], exit=(0.5, 1), entry=(0.5, 0))
edge(recorded, ledger, [(955, 712)], exit=(0, 0.5), entry=(0.5, 0))
text(962, 686, 92, 18, "append", 12, bg=False)
end = vertex(1310, 684, 56, 56, "<b>END</b>", f"ellipse;whiteSpace=wrap;html=1;fillColor=#E06666;strokeColor=#990000;strokeWidth=2;"
                                           f"fontColor=#FFFFFF;fontFamily={FONT};fontSize=13;")
edge(recorded, end)
text(1262, 744, 136, 18, "next approval stage", 12, bg=False)
edge(recorded, status, [(1155, 830), (135, 830)], exit=(0.5, 1), entry=(0.5, 1))
text(470, 820, 360, 20, "clarification request → the institution answers", 12)

xml = (f'<mxfile host="app.diagrams.net"><diagram id="satyapatra-flow" name="SatyaPatra flow">'
       f'<mxGraphModel dx="{W}" dy="{H}" grid="1" gridSize="10" guides="1" page="1" pageWidth="{W}" pageHeight="{H}" background="#FFFFFF">'
       f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>')
(HERE / "architecture.drawio").write_text(xml)
model = xml[xml.index("<mxGraphModel"):xml.index("</diagram>")]
c = zlib.compressobj(9, zlib.DEFLATED, -15)
packed = base64.b64encode(c.compress(urllib.parse.quote(model, safe="~()*!.'").encode()) + c.flush()).decode()
(HERE / "architecture.url").write_text("https://app.diagrams.net/?splash=0#R" + urllib.parse.quote(packed, safe=""))
print("cells", n[0], "xml", len(xml), "url", len(packed))
