"use client";

import { useState } from "react";

type ApiStatus = "idle" | "loading" | "ok" | "error";

export default function Home() {
  const [status, setStatus] = useState<ApiStatus>("idle");
  const [response, setResponse] = useState<object | null>(null);

  async function pingApi() {
    setStatus("loading");
    setResponse(null);
    try {
      const res = await fetch("/api/ping");
      const data = await res.json();
      setResponse(data);
      setStatus("ok");
    } catch {
      setStatus("error");
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#0f1117",
        color: "#e2e8f0",
        fontFamily: "'Inter', system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
      }}
    >
      <div style={{ maxWidth: 640, width: "100%", textAlign: "center" }}>
        {/* Header */}
        <div style={{ fontSize: 52, marginBottom: 12 }}>🌽</div>
        <h1
          style={{
            fontSize: 34,
            fontWeight: 700,
            margin: 0,
            color: "#f8fafc",
            letterSpacing: "-0.5px",
          }}
        >
          N Scout
        </h1>
        <p style={{ color: "#64748b", marginTop: 8, marginBottom: 36, fontSize: 15 }}>
          Nitrogen deficiency scouting · Sentinel-2 + PRNT
        </p>

        {/* Stack check card */}
        <div
          style={{
            background: "#1a1f2e",
            border: "1px solid #2d3748",
            borderRadius: 14,
            padding: "1.75rem",
            marginBottom: 20,
          }}
        >
          <p
            style={{
              margin: "0 0 16px",
              fontSize: 12,
              color: "#64748b",
              textTransform: "uppercase",
              letterSpacing: 1.2,
              fontWeight: 600,
            }}
          >
            Stack verification
          </p>

          <button
            onClick={pingApi}
            disabled={status === "loading"}
            style={{
              background: status === "ok" ? "#16a34a" : "#22c55e",
              color: "#0f1117",
              border: "none",
              borderRadius: 8,
              padding: "10px 28px",
              fontSize: 15,
              fontWeight: 600,
              cursor: status === "loading" ? "wait" : "pointer",
              opacity: status === "loading" ? 0.65 : 1,
              transition: "all 0.15s",
            }}
          >
            {status === "loading" ? "Pinging…" : "Ping Flask API"}
          </button>

          {response && (
            <pre
              style={{
                marginTop: 16,
                background: "#0f1117",
                borderRadius: 8,
                padding: "12px 16px",
                textAlign: "left",
                fontSize: 13,
                color: "#86efac",
                overflow: "auto",
                border: "1px solid #1a3a2e",
              }}
            >
              {JSON.stringify(response, null, 2)}
            </pre>
          )}

          {status === "error" && (
            <p style={{ color: "#f87171", marginTop: 14, fontSize: 14 }}>
              ✗ Could not reach the Flask API.
            </p>
          )}

          {status === "ok" && (
            <p style={{ color: "#86efac", marginTop: 14, fontSize: 14 }}>
              ✓ Next.js → Flask communication confirmed.
            </p>
          )}
        </div>

        <p style={{ color: "#334155", fontSize: 12 }}>
          Next.js static export · Flask · Gunicorn · Docker
        </p>
      </div>
    </main>
  );
}
