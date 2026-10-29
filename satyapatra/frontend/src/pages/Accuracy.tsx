import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

const SIGNAL: Record<string, string> = {
  t2_not_found: "Issuer has no record", t2_fields_differ: "Issuer record differs", qr_untrusted: "QR to unofficial site",
  sig_modified: "Changed after signing", pdf_overlay_edit: "White patch over text", incremental_saves: "Saved again after creation",
  scan_reused: "Seal scan reused", specimen_mismatch: "Seal unlike specimen", "R-VAL-01": "Validity date rule",
  field_font_mismatch: "Font differs on key field", ela_hotspot: "Pasted image region",
};

export default function Accuracy() {
  const { data: ev } = useQuery({ queryKey: ["eval"], queryFn: () => api("/api/eval") });
  if (!ev?.groups) return <div className="page"><div className="empty">No measurement yet. Run scripts/evaluate.py.</div></div>;
  return (
    <div className="page">
      <div className="page-head"><div><h1>Measured accuracy</h1>
        <p>{ev.documents} labelled documents from our test harness: {ev.genuine} genuine and {ev.forged} forged, across 8 forgery types modelled on reported cases. Synthetic data, as the PS allows; real-world rates will be lower and are measured in the pilot.</p></div></div>
      <div className="stats">
        <div className="stat"><span className="label">Forgeries caught</span><span className="value" style={{ color: "var(--ok)" }}>{Math.round(ev.catch_rate * ev.forged)}<small>/ {ev.forged}</small></span></div>
        <div className="stat"><span className="label">False alarms on genuine files</span><span className="value">{Math.round(ev.false_alarm_rate * ev.genuine)}<small>/ {ev.genuine}</small></span></div>
        <div className="stat"><span className="label">Median time, PDF</span><span className="value">{(ev.median_ms_pdf / 1000).toFixed(2)}<small>s</small></span></div>
        <div className="stat"><span className="label">Median time, phone scan</span><span className="value">{(ev.median_ms_scan / 1000).toFixed(2)}<small>s</small></span></div>
      </div>
      <table className="table">
        <thead><tr><th>Test group</th><th>Result</th><th>Signals that fired (documents)</th><th className="r">Median</th></tr></thead>
        <tbody>{ev.groups.map((g: any) => (
          <tr key={g.group}>
            <td>{g.label}</td>
            <td><span className={`st ${g.ok === g.n ? "s-ok" : "s-rev"}`}>{g.ok} of {g.n} {g.metric}</span></td>
            <td className="small">{Object.entries(g.signals).map(([k, n]) => <span key={k} className="tag">{SIGNAL[k] || k} ({String(n)})</span>)}
              {!Object.keys(g.signals).length && <span className="muted">none, correctly</span>}</td>
            <td className="r num">{g.median_ms} ms</td>
          </tr>))}
        </tbody>
      </table>
    </div>
  );
}
