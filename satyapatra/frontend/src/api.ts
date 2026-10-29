// Thin typed client for the SatyaPatra API. All calls go through /api (proxied in dev, same origin in production).
export type Status =
  | "Verified" | "Mismatch detected" | "Expired" | "Verification pending"
  | "Source unavailable" | "Manual review required" | "queued";

export interface Check {
  engine: "READ" | "CHECK" | "CONFIRM" | "DETECT" | "SEE" | string;
  code: string; title: string; outcome: string; severity: "hard" | "soft" | "info";
  weight: number; detail: string; rule_ref?: string | null;
  evidence: { page?: number; bbox?: number[] | null; tier?: number; url?: string; image_px?: boolean; [k: string]: unknown };
}
export interface Doc {
  id: string; application_id: string; filename: string; sha256: string; mime: string; doc_type: string | null;
  status: Status; risk: number | null; renders: string[]; page_sizes: [number, number][];
  fields: Record<string, { raw: string; value: unknown; page: number; bbox: number[] | null; source: string }>;
  faculty?: { faculty_id: string; line: string }[]; checks?: Check[]; flags?: number; ms?: number; issuer?: string | null;
}
export interface AppRow {
  id: string; institution: string; institution_id: string; region: string; status: Status; risk: number;
  category: string; cycle: string; top_finding: string; documents: Record<string, number>; story?: string;
}

let token: string | null = null;

async function login() {
  const r = await fetch("/api/auth/dev-login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: "officer", name: "R. Sharma (Regional Officer)" }),
  });
  token = (await r.json()).token;
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  if (!token) await login();
  const r = await fetch(path, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${token}` } });
  if (!r.ok) {
    const msg = await r.text();
    throw new Error(msg || r.statusText);
  }
  return r.json();
}

export const post = <T = any>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const DOC_LABEL: Record<string, string> = {
  fire_noc: "Fire NOC", building_completion: "Building completion", lease_deed: "Lease deed", fdr: "Fixed deposit (FDR)",
  affidavit: "Affidavit", faculty_list: "Faculty declaration", photo: "Campus photo", unknown: "Unclassified",
};
