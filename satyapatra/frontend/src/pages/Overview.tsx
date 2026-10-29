import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, AppRow } from "../api";
import { Pill, Risk, Section } from "../ui";

const ACTION_TEXT: Record<string, string> = {
  "document.uploaded": "Document received", "document.verified": "Document checked", "application.assessed": "Application assessed",
  "confirmation.yes": "Issuer confirmed a document", "confirmation.no": "Issuer denied a document",
  "decision.clarify": "Clarification requested", "decision.inspect": "Sent for inspection", "decision.forward": "Forwarded to next stage",
};

function useGuide() {
  const [open, setOpen] = useState(() => { try { return localStorage.getItem("sp-guide") !== "closed"; } catch { return true; } });
  const close = () => { setOpen(false); try { localStorage.setItem("sp-guide", "closed"); } catch { /* ignore */ } };
  return [open, close] as const;
}

export default function Overview() {
  const [guide, closeGuide] = useGuide();
  const { data: ov } = useQuery({ queryKey: ["overview"], queryFn: () => api("/api/overview") });
  const { data: apps } = useQuery({ queryKey: ["apps"], queryFn: () => api<AppRow[]>("/api/applications") });
  const { data: feed } = useQuery({ queryKey: ["audit"], queryFn: () => api<any[]>("/api/audit?limit=8") });
  const { data: ev } = useQuery({ queryKey: ["eval"], queryFn: () => api("/api/eval") });
  const docs = ov?.documents || {};
  const total = ov?.documents_total || 0;
  const verified = docs["Verified"] || 0;
  const needDecision = apps?.filter((a) => a.status !== "Verified") || [];
  const cc = ov?.confirm_codes || {};
  const tiers = [
    { k: "Digital signature valid", n: cc.sig_valid || 0, c: "#4A2BC2" },
    { k: "Issuer portal confirmed", n: cc.t2_match || 0, c: "#7B63E0" },
    { k: "Issuer answered yes", n: cc.t3_confirmed || 0, c: "#B7A9F2" },
  ];
  const tierTotal = Math.max(1, tiers.reduce((s, t) => s + t.n, 0));

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Overview</h1><p>Approval cycle 2027-28 · South-Central region · {apps?.length ?? 0} applications</p></div>
        <div className="actions"><Link className="btn primary" to="/verify">Verify a document <ArrowRight size={14} /></Link></div>
      </div>

      {guide && (
        <div className="guide" role="note" aria-label="How SatyaPatra works">
          <div className="step"><span className="n">1</span><div><b>Institutions upload</b>Fire NOC, lease, FDR, affidavit, faculty list, photos.</div></div>
          <div className="step"><span className="n">2</span><div><b>Five engines check each file</b>Rules, the issuer itself, tampering signs and the campus on a map.</div></div>
          <div className="step"><span className="n">3</span><div><b>You decide</b>Riskiest files come first, with the proof marked on the page.</div></div>
          <button className="x" onClick={closeGuide} aria-label="Dismiss the guide">Got it</button>
        </div>
      )}

      <div className="stats">
        <div className="stat"><span className="label">Documents checked</span><span className="value">{total}</span><span className="foot">across {apps?.length ?? 0} applications</span></div>
        <div className="stat"><span className="label">Confirmed at source</span><span className="value">{total ? Math.round((100 * verified) / total) : 0}<small>%</small></span><span className="foot">{verified} documents verified</span></div>
        <div className="stat alert"><span className="label">Need your decision</span><span className="value">{needDecision.length}</span><span className="foot">applications with findings</span></div>
        <div className="stat"><span className="label">Median check time</span><span className="value">{ov?.median_ms ? (ov.median_ms / 1000).toFixed(2) : "–"}<small>s</small></span><span className="foot">per document, on CPU</span></div>
      </div>

      <div className="grid g-main">
        <Section title="Needs your decision" sub="riskiest first" right={<Link to="/queue">Open risk queue</Link>}>
          <div>
            <div className="list-h"><span>Institution</span><span>What we found</span><span>Status</span><span className="r">Risk</span><span /></div>
            <div className="list">
              {needDecision.slice(0, 6).map((a) => (
                <Link key={a.id} className="row" to={`/app/${a.id}`}>
                  <span className="who"><b>{a.institution}</b><span className="mono">{a.id}</span> <span>· {a.region}</span></span>
                  <span className="what">{a.top_finding}</span>
                  <span><Pill s={a.status} /></span>
                  <span className="risk"><Risk value={a.risk} /></span>
                  <ChevronRight size={16} className="chev" />
                </Link>
              ))}
              {apps && !needDecision.length && <div className="empty">Nothing needs a decision. Every application is confirmed.</div>}
            </div>
          </div>
        </Section>

        <div className="grid" style={{ gap: 32 }}>
          <Section title="How documents were confirmed" sub="by the issuer, not by us">
            <div className="bar" aria-hidden="true">{tiers.map((t) => <i key={t.k} style={{ width: `${(100 * t.n) / tierTotal}%`, background: t.c }} />)}</div>
            <div className="legend">{tiers.map((t) => <div key={t.k}><i style={{ background: t.c }} /><span>{t.k}</span><b>{t.n}</b></div>)}</div>
          </Section>
          <Section title="Measured accuracy" right={<Link to="/accuracy">Details</Link>}>
            {ev?.documents ? (
              <div className="legend">
                <div><i style={{ background: "var(--ok)" }} /><span>Forgeries caught</span><b>{Math.round(ev.catch_rate * ev.forged)} of {ev.forged}</b></div>
                <div><i style={{ background: "var(--n-300)" }} /><span>False alarms on genuine files</span><b>{Math.round(ev.false_alarm_rate * ev.genuine)} of {ev.genuine}</b></div>
                <div><i style={{ background: "var(--p-600)" }} /><span>Median time, PDF</span><b>{(ev.median_ms_pdf / 1000).toFixed(2)} s</b></div>
                <span className="small muted">Labelled synthetic test set; the pilot measures real-world rates.</span>
              </div>
            ) : <p className="muted">Run scripts/evaluate.py to measure.</p>}
          </Section>
          <Section title="Recent activity" right={<Link to="/ledger">Audit ledger</Link>}>
            <div className="feed">
              {feed?.slice(0, 5).map((e) => (
                <div className="ev" key={e.seq}>
                  <span>{ACTION_TEXT[e.action] ?? e.action} <span className="mono muted">{e.subject}</span><br /><span className="h">#{e.seq} · {e.hash.slice(0, 16)}…</span></span>
                  <span className="small muted">{e.ts.slice(11, 16)}</span>
                </div>
              ))}
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}
