"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { TrialGeoJSON } from "./ScoutingMap";

// Leaflet must not render on the server
const ScoutingMap = dynamic(() => import("./ScoutingMap"), { ssr: false });

type Site = { trial: number; site: string; state: string };

const STAGE_LABELS = ["V6", "V7", "V8", "V9", "V10"];

// (inline to avoid extra CSS file)
const s = {
  page: {
    display: "flex",
    flexDirection: "column" as const,
    height: "100dvh",
    background: "#0f1117",
    color: "#e2e8f0",
    fontFamily: "var(--font-dm-sans, system-ui, sans-serif)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 16px",
    height: 52,
    borderBottom: "1px solid #1e293b",
    flexShrink: 0,
  },
  logo: {
    fontFamily: "var(--font-fraunces, serif)",
    fontSize: 20,
    fontWeight: 700,
    color: "#f1f5f9",
    letterSpacing: "-0.3px",
  },
  navLink: {
    fontSize: 13,
    color: "#64748b",
    textDecoration: "none",
  },
  body: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
    flexDirection: "column" as const,
  },
  summaryBar: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "8px 16px",
    background: "#111827",
    borderBottom: "1px solid #1e293b",
    flexShrink: 0,
    flexWrap: "wrap" as const,
  },
  mapArea: {
    flex: 1,
    position: "relative" as const,
    overflow: "hidden",
  },
  controls: {
    background: "#111827",
    borderBottom: "1px solid #1e293b",
    padding: "12px 16px 16px",
    flexShrink: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 12,
  },
  label: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    color: "#64748b",
    marginBottom: 4,
  },
  select: {
    background: "#1e293b",
    border: "1px solid #334155",
    borderRadius: 8,
    color: "#e2e8f0",
    fontSize: 14,
    padding: "8px 10px",
    width: "100%",
    appearance: "none" as const,
    cursor: "pointer",
  },
  stageRow: {
    display: "flex",
    gap: 6,
  },
  stageBtn: (active: boolean) => ({
    flex: 1,
    padding: "7px 0",
    borderRadius: 7,
    border: "1px solid",
    borderColor: active ? "#0d9488" : "#334155",
    background: active ? "#0d948820" : "transparent",
    color: active ? "#0d9488" : "#94a3b8",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.15s",
  }),
  toggleRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  toggleLabel: {
    fontSize: 13,
    color: "#cbd5e1",
    lineHeight: 1.4,
  },
  toggleSub: {
    fontSize: 11,
    color: "#64748b",
    display: "block",
    marginTop: 2,
  },
  toggle: (on: boolean) => ({
    position: "relative" as const,
    width: 40,
    height: 22,
    borderRadius: 11,
    background: on ? "#0d9488" : "#334155",
    cursor: "pointer",
    border: "none",
    padding: 0,
    flexShrink: 0,
    transition: "background 0.2s",
  }),
  toggleKnob: (on: boolean) => ({
    position: "absolute" as const,
    top: 3,
    left: on ? 21 : 3,
    width: 16,
    height: 16,
    borderRadius: "50%",
    background: "#f1f5f9",
    transition: "left 0.2s",
  }),
  badge: (fusion: boolean) => ({
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    padding: "3px 8px",
    borderRadius: 20,
    background: fusion ? "#0d948830" : "#1e40af30",
    color: fusion ? "#0d9488" : "#60a5fa",
    border: `1px solid ${fusion ? "#0d948850" : "#3b82f650"}`,
  }),
  defBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontSize: 13,
    color: "#f59e0b",
    fontWeight: 600,
  },
  sufBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontSize: 13,
    color: "#0d9488",
    fontWeight: 600,
  },
  dot: (color: string) => ({
    width: 10,
    height: 10,
    borderRadius: "50%",
    background: color,
    display: "inline-block",
  }),
};

export default function Home() {
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedTrial, setSelectedTrial] = useState<number | null>(null);
  const [geoData, setGeoData] = useState<TrialGeoJSON | null>(null);
  const [nStages, setNStages] = useState(5); // 1–5; default all stages (V10)
  const [useFusion, setUseFusion] = useState(true);
  const [loading, setLoading] = useState(false);

  // Load site list on mount
  useEffect(() => {
    fetch("/api/sites")
      .then((r) => r.json())
      .then((data: Site[]) => {
        setSites(data);
        if (data.length > 0) setSelectedTrial(data[0].trial);
      });
  }, []);

  // Load GeoJSON when selected trial changes
  useEffect(() => {
    if (selectedTrial === null) return;
    setLoading(true);
    fetch(`/api/predictions/${selectedTrial}`)
      .then((r) => r.json())
      .then((data: TrialGeoJSON) => {
        setGeoData(data);
        setLoading(false);
      });
  }, [selectedTrial]);

  // Summary counts from current predictions
  const { deficient, total } = (() => {
    if (!geoData) return { deficient: 0, total: 0 };
    const modelKey = useFusion ? "fusion" : "remote";
    const predKey = `${modelKey}_${nStages}_pred`;
    const features = geoData.features;
    return {
      total: features.length,
      deficient: features.filter((f) => f.properties[predKey] === 1).length,
    };
  })();

  const stageLabel = STAGE_LABELS.slice(0, nStages).join(" + ");
  const currentStageLabel = STAGE_LABELS[nStages - 1];

  return (
    <div style={s.page}>
      {/* ── Header ── */}
      <header style={s.header}>
        <span style={s.logo}>🌽 N Scout</span>
        <Link href="/about" style={s.navLink}>
          About
        </Link>
      </header>

      <div style={s.body}>
        {/* ── Summary bar ── */}
        <div style={s.summaryBar}>
          <span style={s.defBadge}>
            <span style={s.dot("#f59e0b")} />
            {deficient} deficient
          </span>
          <span style={{ color: "#334155" }}>·</span>
          <span style={s.sufBadge}>
            <span style={s.dot("#0d9488")} />
            {total - deficient} sufficient
          </span>
          <span style={{ color: "#334155" }}>·</span>
          <span style={{ fontSize: 12, color: "#64748b" }}>
            {total} plots · using {stageLabel}
          </span>
          <span style={{ marginLeft: "auto", ...s.badge(useFusion) }}>
            {useFusion ? "Satellite + Soil & Weather" : "Satellite only"}
          </span>
        </div>

        {/* Controls panel */}
        <div style={s.controls}>
          {/* Site selector */}
          <div>
            <div style={s.label}>Trial site</div>
            <select
              style={s.select}
              value={selectedTrial ?? ""}
              onChange={(e) => setSelectedTrial(Number(e.target.value))}
            >
              {sites.map((site) => (
                <option key={site.trial} value={site.trial}>
                  {site.state}, {site.site}
                </option>
              ))}
            </select>
          </div>

          {/* Stage stepper */}
          <div>
            <div style={s.label}>
              I&apos;m at growth stage{" "}
              <span style={{ color: "#e2e8f0" }}>{currentStageLabel}</span>
              <span style={{ color: "#475569", fontWeight: 400, marginLeft: 6 }}>
                · using imagery from {stageLabel}
              </span>
            </div>
            <div style={s.stageRow}>
              {STAGE_LABELS.map((stage, i) => {
                const stageN = i + 1;
                const isActive = stageN === nStages;
                return (
                  <button
                    key={stage}
                    style={s.stageBtn(isActive)}
                    onClick={() => setNStages(stageN)}
                    aria-pressed={isActive}
                  >
                    {stage}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Soil & weather toggle */}
          <div style={s.toggleRow}>
            <div style={s.toggleLabel}>
              Include soil &amp; weather data
              <span style={s.toggleSub}>
                {useFusion
                  ? "Using PRNT soil nitrate + growing-season weather records"
                  : "Satellite imagery only — toggle on for higher accuracy"}
              </span>
            </div>
            <button
              style={s.toggle(useFusion)}
              onClick={() => setUseFusion((v) => !v)}
              aria-pressed={useFusion}
              aria-label="Toggle soil and weather data"
            >
              <div style={s.toggleKnob(useFusion)} />
            </button>
          </div>
        </div>

        {/* Map */}
        <div style={s.mapArea}>
          {loading && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "#0f1117cc",
                zIndex: 1000,
                fontSize: 14,
                color: "#64748b",
              }}
            >
              Loading field data…
            </div>
          )}
          {geoData && !loading && (
            <ScoutingMap data={geoData} nStages={nStages} useFusion={useFusion} />
          )}
        </div>
      </div>

      {/* Disclaimer footer */}
      <footer
        style={{
          flexShrink: 0,
          padding: "6px 16px",
          borderTop: "1px solid #1e293b",
          background: "#0a0e18",
          fontSize: 10,
          color: "#334155",
          textAlign: "center" as const,
          lineHeight: 1.5,
        }}
      >
        <strong style={{ color: "#475569" }}>Proof of concept.</strong> Predictions shown include plots used during model training and are not an independent validation &mdash; for demonstration only.
        Test-set honest performance: AUC&nbsp;0.634 (Satellite only) / AUC&nbsp;0.904 (Satellite + Soil &amp; Weather).
      </footer>
    </div>
  );
}
