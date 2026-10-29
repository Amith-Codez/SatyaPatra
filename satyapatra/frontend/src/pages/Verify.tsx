import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, FileText, ListChecks, ScanSearch, ScanText, ShieldCheck, Gavel, UploadCloud } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, Doc, DOC_LABEL } from "../api";
import { OUTCOME_ICON, Pill, Section } from "../ui";

const STAGES = [
  { k: "READ", label: "Read", icon: <ScanText size={14} />, idle: "Type and fields" },
  { k: "CHECK", label: "Check", icon: <ListChecks size={14} />, idle: "Handbook rules" },
  { k: "CONFIRM", label: "Confirm", icon: <ShieldCheck size={14} />, idle: "Ask the issuer" },
  { k: "DETECT", label: "Detect", icon: <ScanSearch size={14} />, idle: "Tampering signs" },
  { k: "DECIDE", label: "Decide", icon: <Gavel size={14} />, idle: "Status and risk" },
];
type Ev = { stage: string; text: string; ms: number };

export default function Verify() {
  const [over, setOver] = useState(false);
  const [docId, setDocId] = useState<string | null>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [result, setResult] = useState<Doc | null>(null);
  const [err, setErr] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const [params] = useSearchParams();
  const { data: samples } = useQuery({ queryKey: ["samples"], queryFn: () => api<{ name: string; label: string }[]>("/api/samples") });
  const auto = params.get("sample");
  useEffect(() => { if (auto) sample(auto); }, [auto]);  // deep link: /verify?sample=<file>

  useEffect(() => {
    if (!docId) return;
    let alive = true;
    const tick = async () => {
      const p = await api<{ events: Ev[]; status: string }>(`/api/documents/${docId}/progress`);
      if (!alive) return;
      setEvents(p.events);
      if (p.events.some((e) => e.stage === "DECIDE")) setResult(await api<Doc>(`/api/documents/${docId}`));
      else setTimeout(tick, 200);
    };
    tick();
    return () => { alive = false; };
  }, [docId]);

  function reset() { setEvents([]); setResult(null); setErr(""); }
  async function upload(f: File) {
    reset();
    if (!/\.(pdf|jpe?g|png)$/i.test(f.name)) { setErr("Please choose a PDF, JPG or PNG file."); return; }
    if (f.size > 25 * 1024 * 1024) { setErr("This file is larger than 25 MB. Please upload a smaller scan."); return; }
    const fd = new FormData();
    fd.append("file", f);
    try { setDocId((await api<{ document_id: string }>("/api/verify", { method: "POST", body: fd })).document_id); }
    catch { setErr("The upload did not go through. Check your connection and try again."); }
  }
  async function sample(name: string) {
    reset();
    const r = await api<{ document_id: string }>(`/api/samples/${encodeURIComponent(name)}/verify`, { method: "POST" });
    setDocId(null); setTimeout(() => setDocId(r.document_id), 0);
  }

  const done = new Set(events.map((e) => e.stage));
  const doneCount = STAGES.filter((s) => done.has(s.k)).length;
  const flags = result?.checks?.filter((c) => c.outcome !== "Verified" && c.severity !== "info") || [];

  return (
    <div className="page">
      <div className="page-head"><div><h1>Verify a document</h1>
        <p>Check one document the way an application is checked. Institutions can use this before they submit.</p></div></div>

      <div className="grid g-main">
        <div>
          <div className={`drop ${over ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); }}>
            <UploadCloud size={26} color="var(--p-600)" aria-hidden="true" />
            <h3>Drag a document here</h3>
            <p className="muted small" style={{ margin: "0 0 14px" }}>PDF, JPG or PNG up to 25 MB. Phone photos of paper work too.</p>
            <button className="btn primary" onClick={() => input.current?.click()}>Choose a file</button>
            <input ref={input} type="file" accept=".pdf,.jpg,.jpeg,.png" hidden id="file-input" aria-label="Choose a document"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            {err && <p role="alert" style={{ color: "var(--bad)", marginBottom: 0 }} className="small">{err}</p>}
          </div>
          <div className="how" aria-label="How it works">
            <div><span>1</span>Upload a fire NOC, completion certificate, lease deed, FDR, affidavit or faculty list.</div>
            <div><span>2</span>Five engines run in order, and the issuing authority is asked directly. This takes about a second.</div>
            <div><span>3</span>You get one of six statuses, with each finding marked on the page.</div>
          </div>
        </div>
        <Section title="Or try a sample" sub="synthetic documents from sandbox issuers">
          <div className="samples">
            {samples?.map((s) => (
              <button key={s.name} className="sample" onClick={() => sample(s.name)}><FileText size={16} color="var(--n-400)" /><span>{s.label}</span><span className="k">Run</span></button>
            ))}
          </div>
        </Section>
      </div>

      {(docId || events.length > 0) && (
        <Section title="Checking" sub={result ? `finished in ${events.find((e) => e.stage === "DECIDE")?.ms ?? "–"} ms` : "live"}>
          <div className="stepper" aria-live="polite">
            <span className="fill" style={{ width: `${Math.max(0, doneCount - 1) * 20}%` }} />
            {STAGES.map((s, i) => {
              const ev = events.find((e) => e.stage === s.k);
              const run = !ev && (i === 0 || done.has(STAGES[i - 1].k));
              return (
                <div key={s.k} className={`step ${ev ? "done" : run ? "run" : ""}`}>
                  <span className="dot">{ev ? <Check size={14} /> : s.icon}</span>
                  <span className="k">{s.label}</span>
                  <span className="s">{ev ? ev.text : run ? "Working…" : s.idle}</span>
                  {ev && <span className="ms">{ev.ms} ms</span>}
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {result && (
        <Section title={DOC_LABEL[result.doc_type || "unknown"]} sub={result.id} right={<Pill s={result.status} lg />}>
          <div className="evi">
            {(flags.length ? flags : result.checks?.filter((c) => c.engine === "CONFIRM") || []).map((c, i) => (
              <div className="check" key={i}><span className={`i ${OUTCOME_ICON[c.outcome] || "i-rev"}`}>{c.outcome === "Verified" ? "✓" : "!"}</span>
                <div><div className="t">{c.title}</div><div className="d">{c.detail}</div></div></div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="small muted" style={{ marginRight: "auto" }}>{flags.length ? `${flags.length} finding${flags.length > 1 ? "s" : ""}, each with evidence.` : "Confirmed by the issuer. Nothing to fix."}</span>
            <a className="btn" href={`/api/documents/${result.id}/file`} target="_blank" rel="noreferrer">Original</a>
            <Link className="btn primary" to={`/app/${result.application_id}?doc=${result.id}`}>See evidence on the page <ArrowRight size={14} /></Link>
          </div>
        </Section>
      )}
    </div>
  );
}
