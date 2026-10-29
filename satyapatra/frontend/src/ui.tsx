import {
  Building2, FileBadge2, FileCheck2, FileSignature, Flame, Image as ImageIcon, Landmark, ListChecks,
  Satellite, ScanSearch, ScanText, ShieldCheck, Users,
} from "lucide-react";
import type { ReactNode } from "react";

const STATUS_CLASS: Record<string, string> = {
  "Verified": "s-ok", "Mismatch detected": "s-bad", "Expired": "s-exp", "Manual review required": "s-rev",
  "Verification pending": "s-pend", "Source unavailable": "s-na", queued: "s-q",
};

/** Plain-language meaning of each PS status, shown on hover and in the queue's legend. */
export const STATUS_HELP: Record<string, string> = {
  "Verified": "The issuer confirmed it, or every cross-check passed. Nothing to do.",
  "Mismatch detected": "A hard fact failed: the issuer has no record, the record differs, or the file changed after signing. Open the evidence.",
  "Expired": "The document is genuine but its validity date has passed. Ask for a renewed copy.",
  "Manual review required": "Soft warning signs added up. A person should look at the highlighted evidence.",
  "Verification pending": "We asked the issuer and are waiting for the answer. It moves to manual review after the issuer's deadline.",
  "Source unavailable": "The issuer's system did not answer. We retry automatically; this is never treated as forgery.",
};

export const statusTone = (s: string) => STATUS_CLASS[s] || "s-q";

export function Pill({ s, lg = false }: { s: string; lg?: boolean }) {
  return <span className={`st ${statusTone(s)} ${lg ? "lg" : ""}`} title={STATUS_HELP[s]}>{s === "queued" ? "Checking" : s}</span>;
}

const RISK_COLOR = (r: number) => (r >= 80 ? "var(--bad)" : r >= 50 ? "var(--exp)" : r >= 25 ? "var(--s-600)" : "var(--n-500)");

export function Risk({ value }: { value: number | null }) {
  const v = value ?? 0;
  return <span className="num" style={{ color: RISK_COLOR(v), fontWeight: 500 }} title={`Risk ${v} of 100`}>{v}</span>;
}

export function Dial({ value, size = 76 }: { value: number; size?: number }) {
  const r = size / 2 - 5, c = 2 * Math.PI * r, off = c * (1 - value / 100);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Risk ${value} of 100`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--n-150)" strokeWidth="5" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={RISK_COLOR(value)} strokeWidth="5" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={off} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" fontSize="20" fontWeight="500" fill="var(--n-900)" fontFamily="Noto Sans Display">{value}</text>
    </svg>
  );
}

export const ENGINE_META: Record<string, { label: string; icon: ReactNode; blurb: string }> = {
  READ: { label: "Read", icon: <ScanText size={14} />, blurb: "Classify, OCR, extract" },
  CHECK: { label: "Check", icon: <ListChecks size={14} />, blurb: "Handbook rules" },
  CONFIRM: { label: "Confirm", icon: <ShieldCheck size={14} />, blurb: "Ask the issuer" },
  DETECT: { label: "Detect", icon: <ScanSearch size={14} />, blurb: "Tampering signs" },
  SEE: { label: "See", icon: <Satellite size={14} />, blurb: "Physical reality" },
};

export function DocIcon({ t }: { t: string | null }) {
  const p = { size: 16 };
  switch (t) {
    case "fire_noc": return <Flame {...p} />;
    case "building_completion": return <Building2 {...p} />;
    case "lease_deed": return <FileSignature {...p} />;
    case "fdr": return <Landmark {...p} />;
    case "affidavit": return <FileBadge2 {...p} />;
    case "faculty_list": return <Users {...p} />;
    case "photo": return <ImageIcon {...p} />;
    default: return <FileCheck2 {...p} />;
  }
}

export function Logo({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="12" fill="none" stroke="#fff" strokeWidth="2.6" />
      <path d="M11.2 16.4l3.3 3.3 6.4-7.2" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="25.5" cy="6.5" r="3.4" fill="#E89C30" stroke="#4A2BC2" strokeWidth="1.2" />
    </svg>
  );
}

/** A titled section. Unboxed by default: separation comes from space and hairlines. */
export function Section({ title, sub, right, children, boxed = false }: { title?: string; sub?: string; right?: ReactNode; children: ReactNode; boxed?: boolean }) {
  return (
    <section className="section">
      {title && <div className="section-h"><h2>{title}</h2>{sub && <span className="sub">{sub}</span>}{right && <div className="right">{right}</div>}</div>}
      {boxed ? <div className="panel"><div className="panel-b">{children}</div></div> : children}
    </section>
  );
}

export const OUTCOME_ICON: Record<string, string> = {
  "Verified": "i-ok", "Mismatch detected": "i-bad", "Expired": "i-exp", "Manual review required": "i-rev",
  "Verification pending": "i-pend", "Source unavailable": "i-na", flag: "i-rev",
};
