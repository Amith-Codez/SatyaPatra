import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, Building, CornerDownLeft, FileSearch, FlaskConical, Gauge, Inbox, Link2, ScrollText, Search, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, AppRow } from "./api";
import { Logo } from "./ui";
import Overview from "./pages/Overview";
import Queue from "./pages/Queue";
import Application from "./pages/Application";
import Verify from "./pages/Verify";
import Memory from "./pages/Memory";
import Issuers from "./pages/Issuers";
import Ledger from "./pages/Ledger";
import Rules from "./pages/Rules";
import Accuracy from "./pages/Accuracy";

type Lang = "en" | "hi";
const L = (en: string, hi: string) => ({ en, hi });
const NAV = [
  { to: "/", label: L("Overview", "अवलोकन"), icon: <Gauge size={16} />, end: true },
  { to: "/queue", label: L("Risk queue", "जोखिम कतार"), icon: <Inbox size={16} /> },
  { to: "/verify", label: L("Verify a document", "दस्तावेज़ सत्यापन"), icon: <UploadCloud size={16} /> },
];
const NAV2 = [
  { to: "/memory", label: L("Cross-institution memory", "संस्थान-पार स्मृति"), icon: <Link2 size={16} /> },
  { to: "/issuers", label: L("Issuer trust registry", "जारीकर्ता रजिस्ट्री"), icon: <Building size={16} /> },
  { to: "/rules", label: L("Rulebook (APH)", "नियम पुस्तिका (APH)"), icon: <BookOpenCheck size={16} /> },
  { to: "/ledger", label: L("Audit ledger", "ऑडिट लेजर"), icon: <ScrollText size={16} /> },
  { to: "/accuracy", label: L("Measured accuracy", "मापी गई सटीकता"), icon: <FlaskConical size={16} /> },
];
const TITLES: Record<string, string> = {
  "": "Overview", queue: "Risk queue", verify: "Verify a document", memory: "Cross-institution memory",
  issuers: "Issuer trust registry", rules: "Rulebook", ledger: "Audit ledger", accuracy: "Measured accuracy", app: "Application",
};
const ZOOMS = [0.9, 1, 1.12];

export default function App() {
  const loc = useLocation();
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem("sp-lang") as Lang) || "en");
  const [zoom, setZoom] = useState(1);
  const [palette, setPalette] = useState(false);
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: () => api("/api/health") });
  const { data: apps } = useQuery({ queryKey: ["apps"], queryFn: () => api<AppRow[]>("/api/applications") });
  const flagged = apps?.filter((a) => a.status !== "Verified").length;
  const seg = loc.pathname.split("/")[1] || "";

  useEffect(() => { document.documentElement.style.setProperty("--zoom", String(ZOOMS[zoom])); }, [zoom]);
  useEffect(() => { try { localStorage.setItem("sp-lang", lang); } catch { /* storage may be blocked */ } }, [lang]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); }
      if (e.key === "Escape") setPalette(false);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  return (
    <>
      <a className="skip" href="#main">Skip to main content</a>
      <div className="govbar" role="banner">
        <span className="tri" aria-hidden="true"><i /><i /><i /></span>
        <span>Government of India</span><span className="sep full">|</span>
        <span className="full">All India Council for Technical Education</span>
        <div className="right">
          <span className="full" style={{ opacity: .7, marginRight: 4 }}>Text size</span>
          {["A−", "A", "A+"].map((t, i) => (
            <button key={t} className={zoom === i ? "on" : ""} aria-pressed={zoom === i} aria-label={`Text size ${t}`} onClick={() => setZoom(i)}>{t}</button>
          ))}
          <span className="sep">|</span>
          <button className={lang === "en" ? "on" : ""} aria-pressed={lang === "en"} onClick={() => setLang("en")}>English</button>
          <button className={lang === "hi" ? "on" : ""} aria-pressed={lang === "hi"} onClick={() => setLang("hi")} lang="hi">हिन्दी</button>
        </div>
      </div>
      <div className="shell">
        <aside className="side" aria-label="Navigation">
          <div className="ws">
            <span className="logo"><Logo /></span>
            <div><b>SatyaPatra</b><span lang="hi">सत्यपत्र · AICTE South-Central</span></div>
          </div>
          <button className="search" onClick={() => setPalette(true)} aria-label="Search applications and pages">
            <Search size={15} />{lang === "hi" ? "खोजें" : "Search or jump to"}<kbd>⌘K</kbd>
          </button>
          <nav className="nav">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}>{n.icon}<span lang={lang}>{n.label[lang]}</span>
                {n.to === "/queue" && flagged ? <span className="count">{flagged}</span> : null}
              </NavLink>
            ))}
            <div className="nav-label" lang={lang}>{lang === "hi" ? "विश्वास अवसंरचना" : "Trust infrastructure"}</div>
            {NAV2.map((n) => <NavLink key={n.to} to={n.to}>{n.icon}<span lang={lang}>{n.label[lang]}</span></NavLink>)}
          </nav>
          <div className="side-foot" aria-label="System status">
            <span className="live"><span className="dot" />{health ? "All engines online" : "Connecting…"}</span>
            <span>{health?.database?.split(" ")[0] ?? "…"} · {health?.jobs?.split(" ")[0] ?? "…"} · local AI {health?.llm?.split(" ")[0] ?? "off"}</span>
            <span>No data leaves this server</span>
          </div>
        </aside>
        <div className="main">
          <header className="topbar">
            <div className="crumbs">Approval cycle 2027-28 <span>/</span> <b>{TITLES[seg] ?? ""}</b></div>
            <div className="spacer" />
            <span className="env">Sandbox data · <b>synthetic institutions</b></span>
            <div className="who"><span className="avatar">RS</span>R. Sharma · Regional Officer</div>
          </header>
          <main id="main" tabIndex={-1}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/queue" element={<Queue />} />
              <Route path="/app/:id" element={<Application />} />
              <Route path="/verify" element={<Verify />} />
              <Route path="/memory" element={<Memory />} />
              <Route path="/issuers" element={<Issuers />} />
              <Route path="/rules" element={<Rules />} />
              <Route path="/ledger" element={<Ledger />} />
              <Route path="/accuracy" element={<Accuracy />} />
            </Routes>
          </main>
        </div>
      </div>
      {palette && <Palette apps={apps || []} lang={lang} onClose={() => setPalette(false)} />}
    </>
  );
}

function Palette({ apps, lang, onClose }: { apps: AppRow[]; lang: Lang; onClose: () => void }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const items = useMemo(() => {
    const pages = [...NAV, ...NAV2].map((n) => ({ key: n.to, label: n.label[lang], hint: "Page", go: n.to, icon: n.icon }));
    const rows = apps.map((a) => ({ key: a.id, label: `${a.institution}`, hint: `${a.id} · ${a.status}`, go: `/app/${a.id}`, icon: <FileSearch size={16} /> }));
    const all = [...pages, ...rows];
    const t = q.trim().toLowerCase();
    return t ? all.filter((x) => `${x.label} ${x.hint}`.toLowerCase().includes(t)) : all;
  }, [q, apps, lang]);
  const pick = (k: number) => { const it = items[k]; if (it) { nav(it.go); onClose(); } };
  return (
    <div className="scrim" onMouseDown={onClose} role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="palette" onMouseDown={(e) => e.stopPropagation()}>
        <input id="palette-input" autoFocus placeholder="Search applications, institutions or pages" value={q}
          onChange={(e) => { setQ(e.target.value); setI(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(x + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(x - 1, 0)); }
            if (e.key === "Enter") pick(i);
          }} />
        <ul role="listbox">
          {items.slice(0, 12).map((it, k) => (
            <li key={it.key} role="option" aria-selected={k === i} className={k === i ? "on" : ""} onMouseEnter={() => setI(k)} onClick={() => pick(k)}>
              {it.icon}{it.label}<span className="k">{it.hint}</span>
            </li>
          ))}
          {!items.length && <li>No matches</li>}
        </ul>
        <div className="foot"><span>↑↓ to move</span><span><CornerDownLeft size={11} style={{ verticalAlign: -1 }} /> to open</span><span>Esc to close</span></div>
      </div>
    </div>
  );
}
