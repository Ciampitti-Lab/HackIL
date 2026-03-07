import Image from "next/image";
import Link from "next/link";

const s = {
  page: {
    minHeight: "100dvh",
    background: "#ffffff",
    color: "#0f172a",
    fontFamily: "var(--font-dm-sans, system-ui, sans-serif)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 20px",
    height: 52,
    borderBottom: "1px solid #e2e8f0",
    background: "#ffffff",
  },
  logo: {
    fontFamily: "var(--font-fraunces, serif)",
    fontSize: 20,
    fontWeight: 700,
    color: "#0f172a",
    letterSpacing: "-0.3px",
    textDecoration: "none",
  },
  navLink: {
    fontSize: 13,
    color: "#64748b",
    textDecoration: "none",
  },
  main: {
    maxWidth: 680,
    margin: "0 auto",
    padding: "40px 20px 60px",
  },
  h1: {
    fontFamily: "var(--font-fraunces, serif)",
    fontSize: 32,
    fontWeight: 700,
    color: "#0f172a",
    letterSpacing: "-0.5px",
    marginBottom: 8,
    marginTop: 0,
  },
  subtitle: {
    fontSize: 15,
    color: "#64748b",
    marginBottom: 40,
    marginTop: 0,
  },
  h2: {
    fontFamily: "var(--font-fraunces, serif)",
    fontSize: 20,
    fontWeight: 600,
    color: "#0f172a",
    marginBottom: 10,
    marginTop: 36,
  },
  p: {
    fontSize: 14,
    lineHeight: 1.75,
    color: "#6b7280",
    margin: "0 0 12px",
  },
  card: {
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 12,
    padding: "16px 20px",
    marginBottom: 12,
  },
  metricRow: {
    display: "flex",
    gap: 16,
    flexWrap: "wrap" as const,
    marginBottom: 12,
  },
  metric: {
    background: "#f1f5f9",
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: "10px 16px",
    flex: "1 1 140px",
  },
  metricLabel: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    color: "#475569",
    marginBottom: 4,
  },
  metricValue: {
    fontSize: 22,
    fontWeight: 700,
    color: "#0f172a",
    fontVariantNumeric: "tabular-nums" as const,
  },
  metricSub: {
    fontSize: 11,
    color: "#64748b",
    marginTop: 2,
  },
  warningBox: {
    background: "#f59e0b12",
    border: "1px solid #f59e0b40",
    borderRadius: 10,
    padding: "14px 16px",
    marginBottom: 16,
  },
  warningTitle: {
    fontSize: 13,
    fontWeight: 700,
    color: "#f59e0b",
    marginBottom: 6,
  },
  warningText: {
    fontSize: 13,
    color: "#6b7280",
    lineHeight: 1.6,
    margin: 0,
  },
  tag: {
    display: "inline-block",
    fontSize: 11,
    fontWeight: 600,
    padding: "3px 8px",
    borderRadius: 20,
    background: "#f1f5f9",
    color: "#64748b",
    marginRight: 6,
    marginBottom: 4,
  },
  divider: {
    borderColor: "#e2e8f0",
    margin: "36px 0",
  },
  a: {
    color: "#b45309",
    textDecoration: "none",
  },
};

export default function About() {
  return (
    <div style={s.page}>
      <header style={s.header}>
        <Link href="/" style={{ ...s.logo, display: "flex", alignItems: "center", gap: 10 }}>
          <Image src="/logo.png" alt="Boilermaker Bushels" width={32} height={32} style={{ display: "block" }} />
          <span>Boilermaker Bushels <span style={{ color: "#daaa00", fontWeight: 400 }}>|</span> N Scout</span>
        </Link>
        <Link href="/" style={s.navLink}>
          Back to map
        </Link>
      </header>

      <main style={s.main}>
        <h1 style={s.h1}>About N Scout</h1>
        <p style={s.subtitle}>
          Detecting nitrogen deficiency in corn fields using Sentinel‑2 satellite
          imagery and the PRNT public research dataset.
        </p>

        {/* Demo disclaimer */}
        <div style={s.warningBox}>
          <div style={s.warningTitle}>⚠ Research demonstration — not for production use</div>
          <p style={s.warningText}>
            This demo uses precomputed predictions on the 7 PRNT trial sites from 2016.{" "}
            <strong style={{ color: "#0f172a" }}>
              Predictions include both training-set and test-set plots.
            </strong>{" "}
            Performance on training-set plots will appear inflated. The honest
            model evaluation metrics below are from the held-out test set only.
            This tool is a proof of concept for a hackathon and should not be
            used to guide real nitrogen management decisions.
          </p>
        </div>

        {/* How it works */}
        <h2 style={s.h2}>How it works</h2>
        <p style={s.p}>
          N Scout detects probable nitrogen deficiency at the plot level by combining
          Sentinel-2 multispectral imagery with optional soil nitrate and weather
          records from the PRNT dataset. The core steps are:
        </p>
        <div style={s.card}>
          <p style={{ ...s.p, margin: 0, lineHeight: 1.9 }}>
            <strong style={{ color: "#0f172a" }}>1. Remote sensing features</strong> —
            16 spectral features per V-stage: 5 raw reflectance bands (B02 blue, B03 green,
            B04 red, B05 red-edge, B08 NIR) and 11 indices (NDVI, GNDVI, NDRE, EVI2,
            CIrededge, NIRv, SAVI, OSAVI, TGI, MCARI, OCARI) extracted from Sentinel-2
            (10 m) at growth stages V6 through V10 — 80 features total. Cloud gaps are
            filled using a nearest-in-time mosaic strategy.
            <br />
            <strong style={{ color: "#0f172a" }}>2. Ground-truth labels</strong> —
            Nitrogen Nutrition Index (NNI) computed from PRNT plant tissue N and
            biomass measurements. Plots with NNI &lt; 1.0 are labelled deficient (25.9 %).
            <br />
            <strong style={{ color: "#0f172a" }}>3. Fusion features</strong> —
            9 soil nitrate / ammonium columns (PPNT + PSNT sampling times) and
            6 growing-season weather metrics (GDD, precipitation, solar radiation,
            heat days) aggregated over the planting to V10 window.
            <br />
            <strong style={{ color: "#0f172a" }}>4. Classification</strong> —
            Logistic Regression trained with stage-dropout augmentation (robust to
            missing V-stages) and an F-beta (beta=2) threshold that weights recall over
            precision.
          </p>
        </div>

        {/* Model performance */}
        <h2 style={s.h2}>Model performance (test set)</h2>
        <p style={s.p}>
          Honest evaluation on held-out plots (treatments 1–8 only; 45 test plots,
          25.9 % N-deficient).
        </p>

        <p style={{ ...s.p, fontWeight: 600, color: "#374151" }}>
          Satellite only (RS model)
        </p>
        <div style={s.metricRow}>
          {[
            { label: "AUC", value: "0.634" },
            { label: "Recall", value: "0.750", sub: "sensitivity" },
            { label: "F1", value: "0.514" },
            { label: "Specificity", value: "0.576" },
          ].map((m) => (
            <div key={m.label} style={s.metric}>
              <div style={s.metricLabel}>{m.label}</div>
              <div style={s.metricValue}>{m.value}</div>
              {m.sub && <div style={s.metricSub}>{m.sub}</div>}
            </div>
          ))}
        </div>

        <p style={{ ...s.p, fontWeight: 600, color: "#374151", marginTop: 16 }}>
          Satellite + Soil &amp; Weather (fusion model)
        </p>
        <div style={s.metricRow}>
          {[
            { label: "AUC", value: "0.904" },
            { label: "Recall", value: "0.833", sub: "sensitivity" },
            { label: "F1", value: "0.870" },
            { label: "Specificity", value: "0.970" },
          ].map((m) => (
            <div key={m.label} style={{ ...s.metric, borderColor: "#daaa0040" }}>
              <div style={s.metricLabel}>{m.label}</div>
              <div style={{ ...s.metricValue, color: "#7a5e00" }}>{m.value}</div>
              {m.sub && <div style={s.metricSub}>{m.sub}</div>}
            </div>
          ))}
        </div>
        <p style={s.p}>
          Soil and weather context provides the dominant signal: adding those features
          improves AUC from 0.634 to 0.904 and lifts F1 from 0.514 to 0.870.
          Satellite imagery refines but does not replace the agronomic context.
        </p>

        {/* Proximal sensing */}
        <h2 style={s.h2}>Proximal sensing (leaf image classifier)</h2>
        <p style={s.p}>
          A MobileNetV3-Small model fine-tuned on a public maize leaf nutrient
          deficiency dataset classifies individual leaf images into 6 nutrient
          classes. This complements the satellite view by confirming plot-level
          deficiency at the individual plant level.
        </p>
        <div style={s.metricRow}>
          {[
            { label: "ALL Present", value: "97.3%" },
            { label: "N absent", value: "100%" },
            { label: "K absent", value: "100%" },
            { label: "P absent", value: "98.6%" },
            { label: "Zn absent", value: "95.2%" },
            { label: "All absent", value: "100%" },
          ].map((m) => (
            <div key={m.label} style={{ ...s.metric, flex: "1 1 100px" }}>
              <div style={s.metricLabel}>{m.label}</div>
              <div style={{ ...s.metricValue, fontSize: 18 }}>{m.value}</div>
            </div>
          ))}
        </div>
        <p style={s.p}>
          Overall test accuracy: <strong style={{ color: "#0f172a" }}>98.5%</strong> on
          882 held-out images (7,056 train / 882 val / 882 test). Model: MobileNetV3-Small
          via timm, fine-tuned from ImageNet weights with Optuna HPO.
        </p>

        {/* Dataset */}
        <hr style={s.divider} />
        <h2 style={s.h2}>Data</h2>
        <p style={s.p}>
          All field data are from the publicly available{" "}
          <strong style={{ color: "#0f172a" }}>PRNT dataset</strong> (
          <em>
            Public-industry Research Network for N rate response studies in corn,
            2014–2016
          </em>
          ), published on Dryad. The dataset covers 49 site-years across 8 U.S.
          Midwest states. This demo uses the 7 trials from 2016 that had reliable
          NNI ground truth and usable Sentinel-2 coverage.
        </p>
        <p style={s.p}>
          Satellite imagery: Sentinel-2 Level-1C (TOA) via Google Earth Engine,{" "}
          <code style={{ fontSize: 12, color: "#6b7280" }}>
            COPERNICUS/S2_HARMONIZED
          </code>
          , cloud-filtered at 30 % scene level + QA60 pixel mask.
        </p>
        <div style={s.card}>
          <p style={{ ...s.p, margin: "0 0 8px", fontWeight: 600, color: "#374151" }}>
            Trial sites used
          </p>
          {[
            "33 — IA Crawford",
            "34 — IA Story",
            "37 — IN Loam",
            "40 — MN Waseca",
            "41 — MO Bradford",
            "42 — MO Loess",
            "43 — MO Troth",
          ].map((s_) => (
            <span key={s_} style={s.tag}>
              {s_}
            </span>
          ))}
        </div>

        {/* Tech stack */}
        <h2 style={s.h2}>Technical stack</h2>
        <p style={s.p}>
          ML pipeline: Python · scikit-learn · XGBoost · LightGBM · Google Earth Engine
          <br />
          Proximal model: PyTorch · timm · MobileNetV3 · Optuna
          <br />
          Backend: Flask 3 + Gunicorn · Python 3.14 · uv
          <br />
          Frontend: Next.js (static export) · Leaflet · TypeScript
          <br />
          Deployment: Docker multi-stage build to Render
        </p>

        {/* Team */}
        <hr style={s.divider} />
        <h2 style={s.h2}>Team</h2>
        <p style={s.p}>
          Built at{" "}
          <strong style={{ color: "#0f172a" }}>Precision & Digital Agriculture Hackathon</strong> by Gustavo, Leonardo, Natalia, Pedro from the
          Ciampitti Lab, Purdue University.
        </p>
      </main>
    </div>
  );
}
