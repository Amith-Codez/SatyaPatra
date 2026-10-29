import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Section } from "../ui";

export default function Memory() {
  const { data } = useQuery({ queryKey: ["memory"], queryFn: () => api("/api/memory") });
  const links: any[] = data?.links || [];
  const nodes = Array.from(new Set(links.flatMap((l) => [l.a, l.b])));
  const name = (id: string) => links.find((l) => l.a === id)?.a_name || links.find((l) => l.b === id)?.b_name || id;
  const W = 640, H = 280, cx = W / 2, cy = H / 2 - 10;
  const pos = (i: number) => [cx + 210 * Math.cos((2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI), cy + 70 * Math.sin((2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI)];
  const fp = data?.fingerprints || {};
  return (
    <div className="page">
      <div className="page-head"><div><h1>Cross-institution memory</h1>
        <p>One officer sees one file. SatyaPatra remembers every file, so the same scanned seal or full-time faculty member at two institutions is linked.</p></div></div>
      <div className="stats">
        <div className="stat"><span className="label">Seal and image fingerprints</span><span className="value">{(fp.image_sha || 0) + (fp.image_phash || 0)}</span></div>
        <div className="stat"><span className="label">Faculty identities (salted hashes)</span><span className="value">{fp.faculty || 0}</span></div>
        <div className="stat"><span className="label">Document fingerprints</span><span className="value">{fp.doc_sha || 0}</span></div>
        <div className="stat alert"><span className="label">Links found</span><span className="value">{links.length}</span></div>
      </div>
      <div className="grid g-main">
        <Section title="Who shares what" sub="each line is evidence an officer can open">
          <div className="panel">
            <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block" }} role="img" aria-label="Institutions linked by shared seals or faculty">
              {links.map((l, i) => {
                const [x1, y1] = pos(nodes.indexOf(l.a)), [x2, y2] = pos(nodes.indexOf(l.b));
                return <g key={i}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--bad)" strokeWidth={1.5 + l.faculty / 3 + l.scans} strokeOpacity=".5" />
                  <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 8} textAnchor="middle" fontSize="12" fill="var(--bad)">
                    {[l.faculty ? `${l.faculty} faculty` : "", l.scans ? `${l.scans} seal scan` : ""].filter(Boolean).join(" · ")}</text></g>;
              })}
              {nodes.map((n, i) => {
                const [x, y] = pos(i);
                return <g key={n}><circle cx={x} cy={y} r="6" fill="#fff" stroke="var(--n-900)" strokeWidth="2" />
                  <text x={x} y={y + 24} textAnchor="middle" fontSize="12.5" fontWeight="500" fill="var(--n-900)">{name(n)}</text>
                  <text x={x} y={y + 39} textAnchor="middle" fontSize="11" fill="var(--n-500)" fontFamily="Noto Sans Mono">{n}</text></g>;
              })}
            </svg>
          </div>
        </Section>
        <Section title="Why this matters">
          <p style={{ margin: 0, color: "var(--n-700)" }}>In July 2024, 353 full-time faculty were found on the payrolls of 2 to 11 Tamil Nadu engineering colleges at once. A check of one file cannot see that; a memory across files can.</p>
          <p className="small muted" style={{ margin: 0 }}>Faculty IDs are stored only as salted SHA-256 hashes, so matches are found without keeping personal data readable.</p>
        </Section>
      </div>
      <table className="table">
        <thead><tr><th>Institution A</th><th>Institution B</th><th className="r">Shared full-time faculty</th><th className="r">Identical seal scans</th></tr></thead>
        <tbody>{links.map((l, i) => <tr key={i}>
          <td className="inst"><b>{l.a_name}</b><span className="mono">{l.a}</span></td>
          <td className="inst"><b>{l.b_name}</b><span className="mono">{l.b}</span></td><td className="r num">{l.faculty}</td><td className="r num">{l.scans}</td></tr>)}
          {!links.length && <tr><td colSpan={4} className="empty">No shared seals or faculty found yet.</td></tr>}</tbody>
      </table>
      <p className="small muted" style={{ margin: 0 }}>Open the linked applications from the <Link to="/queue">risk queue</Link>.</p>
    </div>
  );
}
