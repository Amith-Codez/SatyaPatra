import { useQuery } from "@tanstack/react-query";
import { Check, Minus } from "lucide-react";
import { api, DOC_LABEL } from "../api";

export default function Issuers() {
  const { data } = useQuery({ queryKey: ["issuers"], queryFn: () => api<any[]>("/api/issuers") });
  const yes = (b: boolean) => (b ? <Check size={16} color="var(--ok)" aria-label="Yes" /> : <Minus size={16} color="var(--n-500)" aria-label="No" />);
  return (
    <div className="page">
      <div className="page-head"><div><h1>Issuer trust registry</h1>
        <p>The official ways to confirm each issuer's documents. Only AICTE administrators can edit this list. Contact details printed on an uploaded document are never trusted.</p></div></div>
      <div className="stats" style={{ gridTemplateColumns: "repeat(3, minmax(0,1fr))" }}>
        <div className="stat"><span className="label">Tier 1 · instant</span><span className="foot" style={{ fontSize: 13, color: "var(--n-700)" }}>Digital signature traced to the issuer's certificate, or a QR code that opens an allow-listed official domain.</span></div>
        <div className="stat"><span className="label">Tier 2 · seconds</span><span className="foot" style={{ fontSize: 13, color: "var(--n-700)" }}>The reference number is looked up on the issuer's own portal and every field compared.</span></div>
        <div className="stat"><span className="label">Tier 3 · hours to days</span><span className="foot" style={{ fontSize: 13, color: "var(--n-700)" }}>A signed one-time "Did you issue this?" link to the issuer's registered contact. No answer by the deadline means manual review.</span></div>
      </div>
      <table className="table">
        <thead><tr><th>Issuer</th><th>Documents</th><th>Signature (T1)</th><th>Official QR domains (T1)</th><th>Portal (T2)</th><th>Registered contact (T3)</th><th className="r">Deadline</th><th className="r">Checked</th></tr></thead>
        <tbody>
          {data?.map((i) => (
            <tr key={i.id}>
              <td className="inst"><b>{i.name}</b><span className="mono">{i.id} · sandbox</span></td>
              <td className="small">{i.doc_types.map((t: string) => DOC_LABEL[t]).join(", ")}</td>
              <td>{yes(i.signing)}</td><td className="mono small">{i.qr_domains.join(", ") || "–"}</td><td>{yes(i.tier2)}</td>
              <td className="mono small">{i.tier3 || "–"}</td><td className="r num">{i.sla_days} days</td><td className="r num">{i.verifications}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
