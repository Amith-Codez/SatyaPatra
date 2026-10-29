import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export default function Rules() {
  const { data } = useQuery({ queryKey: ["rules"], queryFn: () => api("/api/rules") });
  const rules: any[] = data?.parsed?.rules || [];
  return (
    <div className="page">
      <div className="page-head"><div><h1>Rulebook</h1>
        <p>The handbook's requirements as editable rules, each tied to its source. When the handbook changes, officers edit this file; no code changes. Version: {data?.parsed?.version}</p></div></div>
      <table className="table">
          <thead><tr><th>Rule</th><th>What it checks</th><th>Kind</th><th>Handbook source</th></tr></thead>
          <tbody>{rules.map((r) => <tr key={r.id}><td className="mono small">{r.id}</td><td>{r.title}</td>
            <td className="small nowrap">{r.severity === "hard" ? "Hard fact" : "Warning sign"}</td><td className="small muted">{r.ref}</td></tr>)}</tbody>
      </table>
      <details className="source">
        <summary>View the rule file as stored (rules.yaml)</summary>
        <pre className="code">{data?.text}</pre>
      </details>
    </div>
  );
}
