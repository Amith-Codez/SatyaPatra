import { useQuery } from "@tanstack/react-query";
import { ChevronRight, HelpCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, AppRow } from "../api";
import { Pill, Risk, STATUS_HELP } from "../ui";

const FILTERS = ["All", "Mismatch detected", "Manual review required", "Verified"];

export default function Queue() {
  const [f, setF] = useState("All");
  const [q, setQ] = useState("");
  const [help, setHelp] = useState(false);
  const { data: apps } = useQuery({ queryKey: ["apps"], queryFn: () => api<AppRow[]>("/api/applications") });
  const rows = useMemo(() => (apps || []).filter((a) => (f === "All" || a.status === f) &&
    `${a.institution} ${a.id} ${a.region} ${a.top_finding}`.toLowerCase().includes(q.trim().toLowerCase())), [apps, f, q]);
  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Risk queue</h1><p>Every application, riskiest first. Open one to see each check and where the evidence sits on the page.</p></div>
        <div className="actions"><button className="btn ghost" onClick={() => setHelp(!help)} aria-expanded={help}><HelpCircle size={15} />What the statuses mean</button></div>
      </div>
      {help && (
        <div className="help" role="region" aria-label="Status meanings">
          {Object.entries(STATUS_HELP).map(([k, v]) => <div key={k}><Pill s={k} /><span>{v}</span></div>)}
        </div>
      )}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <label className="sr" htmlFor="queue-search">Search applications</label>
        <input id="queue-search" className="input" placeholder="Search institution, ID or finding" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="seg" role="group" aria-label="Filter by status">
          {FILTERS.map((x) => <button key={x} className={f === x ? "on" : ""} aria-pressed={f === x} onClick={() => setF(x)}>
            {x} <span className="muted num">{x === "All" ? apps?.length ?? 0 : apps?.filter((a) => a.status === x).length ?? 0}</span></button>)}
        </div>
      </div>
      <div>
        <div className="list-h"><span>Institution</span><span>What we found</span><span>Status</span><span className="r">Risk</span><span /></div>
        <div className="list">
          {rows.map((a) => (
            <Link key={a.id} className="row" to={`/app/${a.id}`}>
              <span className="who"><b>{a.institution}</b><span className="mono">{a.id}</span> <span>· {a.region}</span></span>
              <span className="what">{a.top_finding}<div className="small muted">{a.story}</div></span>
              <span><Pill s={a.status} /></span>
              <span className="risk"><Risk value={a.risk} /></span>
              <ChevronRight size={16} className="chev" />
            </Link>
          ))}
          {!rows.length && <div className="empty">No applications match. Clear the search or choose "All".</div>}
        </div>
      </div>
    </div>
  );
}
