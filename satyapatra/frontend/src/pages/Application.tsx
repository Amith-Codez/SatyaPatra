import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, CheckCircle2, Clock, ExternalLink, MapPinned } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, Check, Doc, DOC_LABEL, post } from "../api";
import { Dial, DocIcon, ENGINE_META, OUTCOME_ICON, Pill, Section } from "../ui";

const ORDER = ["CONFIRM", "CHECK", "DETECT", "SEE", "READ"];
const TIER = ["", "Tier 1 · cryptographic", "Tier 2 · issuer portal", "Tier 3 · issuer confirms"];
const DECISIONS: Record<string, { title: string; body: string; cta: string }> = {
  clarify: { title: "Request clarification", body: "The institution is asked to explain or re-submit. The request and your note are added to the audit ledger.", cta: "Send request" },
  inspect: { title: "Send for physical inspection", body: "An inspection visit is scheduled for the flagged items. The decision and your note are added to the audit ledger.", cta: "Send for inspection" },
  forward: { title: "Forward to the next stage", body: "The application moves on to the next approval stage. Your decision is added to the audit ledger.", cta: "Forward" },
};

function nextStep(status: string) {
  if (status === "Mismatch detected") return { tone: "bad", icon: <AlertTriangle size={17} />, t: "A document failed a hard check", d: "Open the red items below. Request clarification, or send for inspection if the issuer's record contradicts the file.", go: "inspect" };
  if (status === "Manual review required") return { tone: "", icon: <AlertTriangle size={17} color="var(--s-600)" />, t: "Some warning signs need a look", d: "Review the highlighted evidence. If it is explained, forward; if not, ask the institution.", go: "clarify" };
  if (status === "Verification pending") return { tone: "", icon: <Clock size={17} color="var(--p-600)" />, t: "Waiting for an issuer to answer", d: "Nothing to do yet. The file moves to manual review if the issuer misses its deadline.", go: "" };
  return { tone: "", icon: <CheckCircle2 size={17} color="var(--ok)" />, t: "Every document is confirmed", d: "You can forward this application to the next stage.", go: "forward" };
}

export default function Application() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const { data: app } = useQuery({ queryKey: ["app", id], queryFn: () => api(`/api/applications/${id}`) });
  const [sel, setSel] = useState<string | null>(params.get("doc"));
  const [tab, setTab] = useState<"docs" | "app" | "geo">((params.get("tab") as "docs" | "app" | "geo") || "docs");
  const [dialog, setDialog] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [toast, setToast] = useState<{ m: string; h: string } | null>(null);

  useEffect(() => {
    if (app && !sel) setSel([...app.documents].sort((a: Doc, b: Doc) => (b.risk ?? 0) - (a.risk ?? 0))[0]?.id ?? null);
  }, [app, sel]);
  useEffect(() => {
    if (!dialog) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && setDialog(null);
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [dialog]);

  if (!app) return <div className="page"><div className="empty">Loading application…</div></div>;
  const ns = nextStep(app.status);
  const flagged = (app.documents as Doc[]).filter((d) => d.status !== "Verified").length;

  async function confirm() {
    const r = await post(`/api/applications/${id}/action`, { action: dialog, note });
    setDialog(null); setNote("");
    setToast({ m: r.message, h: r.hash });
    qc.invalidateQueries({ queryKey: ["audit"] });
    setTimeout(() => setToast(null), 6000);
  }

  return (
    <div className="page">
      <Link className="back" to="/queue"><ArrowLeft size={14} />Risk queue</Link>
      <div className="app-head">
        <div>
          <span className="mono muted">{app.id} · {app.category} {app.cycle} · {app.institution.region} region</span>
          <h1>{app.institution.name}</h1>
          <div className="meta"><span>{app.institution.address}</span><span>Claimed built-up {Number(app.institution.claimed_builtup_m2).toLocaleString("en-IN")} m²</span>
            <span>{app.documents.length} documents, {flagged} flagged</span></div>
        </div>
        <div className="side-r"><Pill s={app.status} lg /><Dial value={app.risk ?? 0} /></div>
      </div>

      <div className={`next ${ns.tone}`} role="status">
        <span className="ic">{ns.icon}</span>
        <div><b>{ns.t}</b><p>{ns.d}{app.summary?.story ? ` Case: ${app.summary.story}.` : ""}</p></div>
        <div className="acts">
          {(["clarify", "inspect", "forward"] as const).map((k) => (
            <button key={k} className={`btn${ns.go === k ? " primary" : ""}`} onClick={() => setDialog(k)}>{DECISIONS[k].title.replace(" physical", "").replace(" to the next stage", "")}</button>))}
        </div>
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "docs"} className={tab === "docs" ? "on" : ""} onClick={() => setTab("docs")}>Documents and evidence</button>
        <button role="tab" aria-selected={tab === "app"} className={tab === "app" ? "on" : ""} onClick={() => setTab("app")}>Checks across the application</button>
        <button role="tab" aria-selected={tab === "geo"} className={tab === "geo" ? "on" : ""} onClick={() => setTab("geo")}>Satellite and photos</button>
      </div>

      {tab === "docs" && (
        <div className="workbench">
          <nav className="doclist" aria-label="Documents">
            {app.documents.map((d: Doc) => (
              <button key={d.id} className={sel === d.id ? "on" : ""} aria-current={sel === d.id} onClick={() => setSel(d.id)}>
                <span className="ic"><DocIcon t={d.doc_type} /></span>
                <span><b>{DOC_LABEL[d.doc_type || "unknown"]}</b><div className="stl"><Pill s={d.status} /></div></span>
              </button>
            ))}
          </nav>
          {sel && <DocWork id={sel} />}
        </div>
      )}
      {tab === "app" && <AppChecks checks={app.checks} />}
      {tab === "geo" && <Geo instId={app.institution.id} photos={app.documents.filter((d: Doc) => d.doc_type === "photo")} />}

      {dialog && (
        <div className="scrim" onMouseDown={() => setDialog(null)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-t" onMouseDown={(e) => e.stopPropagation()}>
            <h2 id="dlg-t">{DECISIONS[dialog].title}</h2>
            <p>{DECISIONS[dialog].body}</p>
            <label htmlFor="dlg-note">Note for the record (optional)</label>
            <textarea id="dlg-note" autoFocus value={note} onChange={(e) => setNote(e.target.value)} placeholder="For example: fire NOC number not found on the issuer portal" />
            <div className="acts"><button className="btn ghost" onClick={() => setDialog(null)}>Cancel</button>
              <button className="btn primary" onClick={confirm}>{DECISIONS[dialog].cta}</button></div>
          </div>
        </div>
      )}
      {toast && <div className="toast" role="status">{toast.m}. Recorded in the audit ledger.<span className="h">{toast.h}</span></div>}
    </div>
  );
}

function DocWork({ id }: { id: string }) {
  const { data: d } = useQuery({ queryKey: ["doc", id], queryFn: () => api<Doc>(`/api/documents/${id}`) });
  const [page, setPage] = useState(0);
  const [hot, setHot] = useState<number | null>(null);
  useEffect(() => setPage(0), [id]);
  const checks = d?.checks || [];
  const marked = useMemo(() => checks.map((c, i) => ({ c, i })).filter(({ c }) => c.evidence?.bbox && c.outcome !== "Verified" && c.severity !== "info"), [checks]);
  if (!d) return <div className="empty">Loading document…</div>;
  const [pw, ph] = d.page_sizes[page] || [1, 1];
  const num = (i: number) => marked.findIndex((m) => m.i === i) + 1;
  const groups = ORDER.map((e) => ({ e, items: checks.map((c, i) => ({ c, i })).filter(({ c }) => c.engine === e) })).filter((g) => g.items.length);

  return (
    <>
      <div>
        <div className="viewer">
          {d.renders[page] && <img src={d.renders[page]} alt={`Page ${page + 1} of ${d.filename}`} />}
          {marked.filter(({ c }) => (c.evidence.page ?? 0) === page).map(({ c, i }) => {
            const [x0, y0, x1, y1] = c.evidence.bbox as number[];
            return (
              <div key={i} className={`mark ${c.severity === "soft" ? "soft" : ""} ${hot === i ? "hot" : ""}`} onMouseEnter={() => setHot(i)} onMouseLeave={() => setHot(null)}
                style={{ left: `${(100 * x0) / pw}%`, top: `${(100 * y0) / ph}%`, width: `${(100 * (x1 - x0)) / pw}%`, height: `${(100 * (y1 - y0)) / ph}%` }}>
                <span className="n">{num(i)}</span>
              </div>
            );
          })}
          {d.renders.length > 1 && (
            <div className="pager"><button onClick={() => setPage(Math.max(0, page - 1))} aria-label="Previous page">‹</button>Page {page + 1} of {d.renders.length}
              <button onClick={() => setPage(Math.min(d.renders.length - 1, page + 1))} aria-label="Next page">›</button></div>
          )}
        </div>
        <div className="doc-meta"><span className="mono">SHA-256 {d.sha256.slice(0, 16)}…</span><span>Checked in {d.ms} ms</span>
          <a href={`/api/documents/${d.id}/file`} target="_blank" rel="noreferrer">Original file <ExternalLink size={12} style={{ verticalAlign: -1 }} /></a></div>
      </div>
      <div className="evi">
        <div className="evi-h"><h2>{DOC_LABEL[d.doc_type || "unknown"]}</h2><span style={{ marginLeft: "auto" }}><Pill s={d.status} /></span></div>
        {groups.map((g) => (
          <div key={g.e}>
            <div className="grp">{ENGINE_META[g.e]?.icon}{ENGINE_META[g.e]?.label} · {ENGINE_META[g.e]?.blurb}</div>
            {g.items.map(({ c, i }) => (
              <div key={i} className={`check ${hot === i ? "hot" : ""}`} onMouseEnter={() => setHot(i)} onMouseLeave={() => setHot(null)}>
                <span className={`i ${c.severity === "info" ? "i-info" : OUTCOME_ICON[c.outcome] || "i-rev"}`}>{num(i) > 0 ? num(i) : c.outcome === "Verified" ? "✓" : "!"}</span>
                <div>
                  <div className="t">{c.title}</div>
                  <div className="d">{c.detail}</div>
                  <div className="m">
                    {c.evidence?.tier ? <span className="tag">{TIER[c.evidence.tier as number]}</span> : null}
                    {c.severity === "hard" && c.outcome !== "Verified" ? <span className="tag">Hard fact</span> : null}
                    {c.severity === "soft" && c.outcome !== "Verified" ? <span className="tag">Warning sign, +{c.weight} risk</span> : null}
                    {c.rule_ref ? <span className="tag">{c.rule_ref}</span> : null}
                    {typeof c.evidence?.url === "string" && c.evidence.url.startsWith("http://127.0.0.1") ?
                      <span className="tag"><a href={c.evidence.url as string} target="_blank" rel="noreferrer">Issuer record</a></span> : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ))}
        {d.fields && Object.keys(d.fields).length > 0 && (
          <details style={{ paddingTop: 12 }}>
            <summary className="small" style={{ cursor: "pointer", fontWeight: 500 }}>Fields read from the document ({Object.keys(d.fields).length})</summary>
            <table className="table" style={{ marginTop: 8 }}><tbody>
              {Object.entries(d.fields).map(([k, v]) => <tr key={k}><td className="muted small">{k.replace(/_/g, " ")}</td><td className="small">{v.raw}</td></tr>)}
            </tbody></table>
          </details>
        )}
      </div>
    </>
  );
}

function AppChecks({ checks }: { checks: Check[] }) {
  return (
    <div className="evi" style={{ maxWidth: 820 }}>
      {checks.map((c, i) => (
        <div className="check" key={i}>
          <span className={`i ${OUTCOME_ICON[c.outcome] || "i-rev"}`}>{c.outcome === "Verified" ? "✓" : "!"}</span>
          <div><div className="t" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>{c.title}<Pill s={c.outcome} /></div>
            <div className="d">{c.detail}</div>
            <div className="m"><span className="tag">{ENGINE_META[c.engine]?.label ?? c.engine}</span>{c.rule_ref && <span className="tag">{c.rule_ref}</span>}</div></div>
        </div>
      ))}
    </div>
  );
}

function Geo({ instId, photos }: { instId: string; photos: Doc[] }) {
  const { data: g } = useQuery({ queryKey: ["geo", instId], queryFn: () => api(`/api/geo/${instId}`) });
  if (!g) return <div className="empty">Loading map…</div>;
  const ring: number[][] = g.campus.coordinates[0];
  const feats = g.footprints?.features || [];
  const all = [...ring, ...feats.flatMap((f: any) => f.geometry.coordinates[0])];
  const xs = all.map((p) => p[0]), ys = all.map((p) => p[1]);
  const [minx, maxx, miny, maxy] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const W = 640, H = 400, pad = 36, s = Math.min((W - 2 * pad) / (maxx - minx), (H - 2 * pad) / (maxy - miny));
  const P = (p: number[]) => `${pad + (p[0] - minx) * s},${H - pad - (p[1] - miny) * s}`;
  const c = g.check;
  return (
    <div className="grid g-main">
      <div>
        <div className="viewer" style={{ background: "#EEF1EA" }}>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block" }} role="img" aria-label="Campus boundary and building footprints">
            <defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#E0E6DA" strokeWidth="1" /></pattern></defs>
            <rect width={W} height={H} fill="url(#grid)" />
            <polygon points={ring.map(P).join(" ")} fill="rgba(74,43,194,.06)" stroke="var(--p-600)" strokeWidth="2" strokeDasharray="7 5" />
            {feats.map((f: any, i: number) => <polygon key={i} points={f.geometry.coordinates[0].map(P).join(" ")} fill="#3F4656" />)}
          </svg>
        </div>
        <div className="doc-meta"><span>■ Building footprint (Open Buildings format; synthetic for this demo)</span><span style={{ color: "var(--p-600)" }}>┅ Boundary from the application</span></div>
      </div>
      <div className="grid" style={{ gap: 28 }}>
        <Section title="Built-up area vs satellite" right={c && <Pill s={c.outcome} />}>
          {c ? (<>
            <div className="legend">
              <div><i style={{ background: "var(--n-900)" }} /><span>Claimed in the application</span><b>{Number(c.evidence.claimed_m2).toLocaleString("en-IN")} m²</b></div>
              <div><i style={{ background: "#3F4656" }} /><span>Footprint of {c.evidence.buildings} buildings</span><b>{Number(c.evidence.footprint_m2).toLocaleString("en-IN")} m²</b></div>
              <div><i style={{ background: "var(--n-300)" }} /><span>Estimated floor area</span><b>{Number(c.evidence.estimated_m2).toLocaleString("en-IN")} m²</b></div>
              <div><i style={{ background: c.outcome === "Verified" ? "var(--ok)" : "var(--bad)" }} /><span>Claimed ÷ estimated</span><b>{c.evidence.ratio}×</b></div>
            </div>
            <p className="small muted" style={{ margin: 0 }}>Only gaps above 1.6× are flagged, and only to plan an inspection. Floors come from building height (3.6 m each).</p>
          </>) : <p className="muted">No satellite check for this application.</p>}
        </Section>
        <Section title="Campus photos" sub="location and date in the photo">
          {photos.map((p) => <PhotoRow key={p.id} id={p.id} />)}
          {!photos.length && <p className="muted">No photos uploaded.</p>}
        </Section>
        <p className="small muted" style={{ display: "flex", gap: 6, margin: 0 }}><MapPinned size={14} />Officers can pull live OpenStreetMap buildings for any boundary through the API.</p>
      </div>
    </div>
  );
}

function PhotoRow({ id }: { id: string }) {
  const { data: d } = useQuery({ queryKey: ["doc", id], queryFn: () => api<Doc>(`/api/documents/${id}`) });
  const c = d?.checks?.find((x) => x.code === "photo_location");
  if (!d) return null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "88px minmax(0,1fr)", gap: 12, alignItems: "start" }}>
      <img src={d.renders[0]} alt="Campus lab photo" style={{ width: 88, borderRadius: 6 }} />
      <div><div style={{ fontWeight: 500 }}>{c?.title}</div><div className="small muted">{c?.detail}</div><div style={{ marginTop: 4 }}><Pill s={d.status} /></div></div>
    </div>
  );
}
