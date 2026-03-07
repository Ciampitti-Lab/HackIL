"use client";

import Image from "next/image";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

// One curated image per class, cherry-picked from the test split to show clear, representative images.
// Confidence values from proximal_sensing.csv. 
type Sample = {
  slug: string;
  label: string;
  short: string;
  color: string;
  file: string;
  predicted: string;
  confidence: number;
  correct: boolean;
  desc: string;
};

const LABEL: Record<string, string> = {
  "ALL Present": "All Present",
  NAB:  "Nitrogen Absent",
  PAB:  "Phosphorus Absent",
  KAB:  "Potassium Absent",
  ZNAB: "Zinc Absent",
  ALLAB:"All Absent",
};

const COLOR: Record<string, string> = {
  "ALL Present": "#0d9488",
  NAB:  "#f59e0b",
  PAB:  "#a78bfa",
  KAB:  "#fb923c",
  ZNAB: "#38bdf8",
  ALLAB:"#f87171",
};

const SAMPLES: Sample[] = [
  {
    slug: "NAB",  label: "Nitrogen Absent",   short: "N deficient",     color: "#f59e0b",
    file: "IMG20230319153500_01.jpg",
    predicted: "NAB", confidence: 1.000, correct: true,
    desc: "Yellowing progresses from leaf tip inward along the midrib.",
  },
  {
    slug: "ALL_Present", label: "All Present", short: "Healthy",         color: "#0d9488",
    file: "0532_3.jpg",
    predicted: "ALL Present", confidence: 0.996, correct: true,
    desc: "Uniform dark-green leaf — no nutrient stress detected.",
  },
  {
    slug: "KAB",  label: "Potassium Absent",  short: "K deficient",     color: "#fb923c",
    file: "0560_0_1.jpg",
    predicted: "KAB", confidence: 0.995, correct: true,
    desc: "Scorch-like browning along leaf margins, starting with older leaves.",
  },
  {
    slug: "PAB",  label: "Phosphorus Absent", short: "P deficient",     color: "#a78bfa",
    file: "1685_4.jpg",
    predicted: "PAB", confidence: 0.995, correct: true,
    desc: "Purplish-red discoloration on leaf undersides and margins.",
  },
  {
    slug: "ZNAB", label: "Zinc Absent",       short: "Zn deficient",    color: "#38bdf8",
    file: "1076_2.jpg",
    predicted: "PAB", confidence: 0.685, correct: false,
    desc: "Pale striping between veins on new leaves — can resemble P deficiency.",
  },
  {
    slug: "ALLAB",label: "All Absent",        short: "Multi-deficient", color: "#f87171",
    file: "0820_4.jpg",
    predicted: "ALLAB", confidence: 0.996, correct: true,
    desc: "Severe multi-nutrient stress — combined yellowing, browning, striping.",
  },
];

export default function ProximalPage() {
  return (
    <Suspense fallback={<div style={{ background: "#0f1117", minHeight: "100dvh" }} />}>
      <ProximalContent />
    </Suspense>
  );
}

function ProximalContent() {
  const params = useSearchParams();
  const field  = params.get("field") ?? null;
  const plot   = params.get("plot")  ?? null;
  const lat    = params.get("lat")   ?? null;
  const lng    = params.get("lng")   ?? null;

  const [selected, setSelected] = useState<Sample | null>(null);

  const predColor = selected ? (COLOR[selected.predicted] ?? "#94a3b8") : "#94a3b8";
  const predLabel = selected ? (LABEL[selected.predicted] ?? selected.predicted) : "";
  const confPct   = selected ? Math.round(selected.confidence * 100) : 0;

  return (
    <div style={{ minHeight: "100dvh", background: "#0f1117", color: "#e2e8f0", fontFamily: "var(--font-dm-sans, system-ui, sans-serif)", display: "flex", flexDirection: "column" }}>

      {/* Header */}
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", height: 52, borderBottom: "1px solid #1e293b", flexShrink: 0 }}>
        <span style={{ fontFamily: "var(--font-fraunces, serif)", fontSize: 20, fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.3px" }}>
          🌽 N Scout
        </span>
        <Link href="/" style={{ fontSize: 13, color: "#64748b", textDecoration: "none" }}>
          ← Back to map
        </Link>
      </header>

      <main style={{ flex: 1, padding: "24px 16px 48px", maxWidth: 720, margin: "0 auto", width: "100%" }}>

        {/* Title + location */}
        <h1 style={{ fontFamily: "var(--font-fraunces, serif)", fontSize: 26, fontWeight: 700, color: "#f1f5f9", marginBottom: 4, marginTop: 0 }}>
          Targeted Leaf Scouting
        </h1>
        {(field || plot) ? (
          <div style={{ fontSize: 13, color: "#64748b", marginBottom: 6 }}>
            {field && <span style={{ color: "#94a3b8" }}>{field}</span>}
            {plot  && <span> &middot; Plot <strong style={{ color: "#cbd5e1" }}>{plot}</strong></span>}
            {lat && lng && (
              <span style={{ color: "#475569" }}>
                {" "}&middot; {Number(lat) > 0 ? `${lat}°N` : `${Math.abs(Number(lat))}°S`},{" "}
                {Number(lng) < 0 ? `${Math.abs(Number(lng))}°W` : `${lng}°E`}
              </span>
            )}
          </div>
        ) : null}
        <p style={{ fontSize: 13, color: "#475569", marginBottom: 28, marginTop: 4, lineHeight: 1.6 }}>
          Tap a leaf image below to run it through the MobileNetV3 classifier. One sample per nutrient class, cherry-picked from the test split.
        </p>

        {/* 6-image grid (one row) */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8, marginBottom: 24 }}>
          {SAMPLES.map(s => {
            const active = selected?.file === s.file;
            return (
              <button
                key={s.file}
                onClick={() => setSelected(active ? null : s)}
                style={{ position: "relative", aspectRatio: "1", borderRadius: 10, overflow: "hidden", border: `2px solid ${active ? s.color : "#1e293b"}`, cursor: "pointer", padding: 0, background: "#111827", transition: "border-color 0.15s" }}
              >
                <Image
                  src={`/proximal-samples/${s.slug}/${s.file}`}
                  alt={s.label}
                  fill
                  style={{ objectFit: "cover" }}
                  sizes="120px"
                  unoptimized
                />
                {active && <div style={{ position: "absolute", inset: 0, background: `${s.color}18`, pointerEvents: "none" }} />}
              </button>
            );
          })}
        </div>

        {/* Result panel */}
        {selected ? (
          <div style={{ background: "#111827", border: `1px solid ${predColor}40`, borderRadius: 12, padding: "20px 18px", marginBottom: 32 }}>
            {/* image + info side by side on wider screens, stacked otherwise */}
            <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>

              {/* Small preview */}
              <div style={{ position: "relative", width: 80, height: 80, borderRadius: 8, overflow: "hidden", flexShrink: 0, border: `1px solid ${selected.color}40` }}>
                <Image src={`/proximal-samples/${selected.slug}/${selected.file}`} alt={selected.label} fill style={{ objectFit: "cover" }} sizes="80px" unoptimized />
              </div>

              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.09em", color: "#475569", marginBottom: 8 }}>
                  Model Prediction
                </div>

                {/* Predicted class */}
                <div style={{ fontSize: 20, fontWeight: 700, color: predColor, marginBottom: 2, fontFamily: "var(--font-fraunces, serif)" }}>
                  {predLabel}
                </div>
                <div style={{ fontSize: 11, color: "#64748b", marginBottom: 14 }}>Predicted nutrient status</div>

                {/* Confidence */}
                <div style={{ fontSize: 11, color: "#64748b", marginBottom: 5 }}>
                  Confidence: <strong style={{ color: "#cbd5e1" }}>{confPct}%</strong>
                </div>
                <div style={{ background: "#0f1117", borderRadius: 6, height: 7, overflow: "hidden", marginBottom: 14 }}>
                  <div style={{ height: "100%", width: `${confPct}%`, background: predColor, borderRadius: 6 }} />
                </div>

                {/* Correct/incorrect */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 12px", borderRadius: 8, background: selected.correct ? "#0d948818" : "#f8717118", border: `1px solid ${selected.correct ? "#0d948840" : "#f8717140"}` }}>
                  <span style={{ fontSize: 16 }}>{selected.correct ? "✓" : "✗"}</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: selected.correct ? "#0d9488" : "#f87171" }}>
                      {selected.correct ? "Correct" : "Misclassified"}
                    </div>
                    <div style={{ fontSize: 11, color: "#64748b" }}>Actual: {selected.label}</div>
                  </div>
                </div>

                {/* Symptom description */}
                <p style={{ fontSize: 12, color: "#64748b", marginTop: 12, lineHeight: 1.6, marginBottom: 0 }}>
                  {selected.desc}
                  {!selected.correct && (
                    <span style={{ color: "#475569" }}>{" "}This edge case is one of 4 misclassifications on 882 test images (98.5% overall accuracy).</span>
                  )}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "20px 0 32px", fontSize: 13, color: "#334155" }}>
            Tap an image above to see the prediction
          </div>
        )}

        {/* Coming soon camera */}
        <div style={{ border: "1px dashed #1e293b", borderRadius: 12, padding: "24px 20px", display: "flex", flexDirection: "column", alignItems: "center", gap: 10, background: "#0a0e18" }}>
          <div style={{ fontSize: 32, opacity: 0.2 }}>📷</div>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", padding: "3px 9px", borderRadius: 20, background: "#1e293b", color: "#475569", border: "1px solid #334155" }}>
            Coming soon
          </span>
          <button disabled style={{ padding: "9px 22px", borderRadius: 8, border: "1px solid #334155", background: "#1e293b", color: "#475569", fontSize: 13, fontWeight: 600, cursor: "not-allowed", opacity: 0.5 }}>
            Capture or upload a field photo
          </button>
          <p style={{ fontSize: 12, color: "#334155", textAlign: "center", maxWidth: 300, lineHeight: 1.6, margin: 0 }}>
            Live MobileNetV3 inference on your own leaf photos is planned for a future update.
          </p>
        </div>

        <p style={{ fontSize: 11, color: "#334155", marginTop: 24, lineHeight: 1.7 }}>
          <strong style={{ color: "#475569" }}>Note:</strong> Images are from the same dataset used to train the model and are shown for demonstration only, not as independent validation.
          For full per-class accuracy and methodology, see the{" "}
          <Link href="/about" style={{ color: "#475569", textDecoration: "underline" }}>About page</Link>{" "}
          or the project README.
        </p>
      </main>
    </div>
  );
}
