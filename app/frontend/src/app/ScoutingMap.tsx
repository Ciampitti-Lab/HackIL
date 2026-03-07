"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap, GeoJSON as LeafletGeoJSON } from "leaflet";

export type PlotFeature = {
  type: "Feature";
  geometry: GeoJSON.Polygon;
  properties: {
    plot_id: number;
    n_trt: number;
    block: number;
    plant_n_kgha: number;
    side_n_kgha: number;
    nni: number;
    is_deficient: number;
    [key: string]: number;
  };
};

export type TrialGeoJSON = {
  type: "FeatureCollection";
  trial: number;
  site: string;
  state: string;
  features: PlotFeature[];
};

type Props = {
  data: TrialGeoJSON;
  nStages: number;
  useFusion: boolean;
};

const DEFICIENT_COLOR = "#f59e0b";
const SUFFICIENT_COLOR = "#0d9488";
const BORDER_COLOR = "#1e293b";
const RESTRICTED_TRT_MIN = 9; // treatments 9-16 had in-season N applied; excluded from model training/testing

function probToConfidence(prob: number, pred: number): string {
  const distance = pred === 1 ? prob : 1 - prob;
  if (distance >= 0.7) return "High confidence";
  if (distance >= 0.5) return "Moderate confidence";
  return "Low confidence";
}

// Renders the GeoJSON plot layer onto the map.
// Extracted so it can be called both after map init and on prop changes.
function renderLayer(
  L: typeof import("leaflet"),
  map: LeafletMap,
  data: TrialGeoJSON,
  nStages: number,
  useFusion: boolean,
  layerRef: React.MutableRefObject<LeafletGeoJSON | null>,
  hatchLayerRef: React.MutableRefObject<LeafletGeoJSON | null>,
) {
  const modelKey = useFusion ? "fusion" : "remote";
  const probKey = `${modelKey}_${nStages}_prob`;
  const predKey = `${modelKey}_${nStages}_pred`;

  if (layerRef.current) {
    layerRef.current.remove();
    layerRef.current = null;
  }
  if (hatchLayerRef.current) {
    hatchLayerRef.current.remove();
    hatchLayerRef.current = null;
  }

  const layer = L.geoJSON(data as GeoJSON.FeatureCollection, {
    style: (feature) => {
      const pred = feature?.properties?.[predKey] ?? 0;
      const isRestricted = (feature?.properties?.n_trt ?? 0) >= RESTRICTED_TRT_MIN;
      return {
        fillColor: pred === 1 ? DEFICIENT_COLOR : SUFFICIENT_COLOR,
        fillOpacity: isRestricted ? 0.28 : 0.65,
        color: BORDER_COLOR,
        weight: 1,
      };
    },
    onEachFeature: (feature, leafletLayer) => {
      const p = feature.properties;
      const prob: number = p[probKey] ?? 0;
      const pred: number = p[predKey] ?? 0;
      const isRestricted = (p.n_trt ?? 0) >= RESTRICTED_TRT_MIN;
      const statusLabel = pred === 1 ? "Deficient" : "Sufficient";
      const confidence = probToConfidence(prob, pred);
      const confPct = Math.round((pred === 1 ? prob : 1 - prob) * 100);
      const statusColor = pred === 1 ? DEFICIENT_COLOR : SUFFICIENT_COLOR;

      // Compute polygon centroid for the proximal link
      const ring = (feature.geometry as GeoJSON.Polygon).coordinates[0];
      const centLat = (ring.reduce((s, c) => s + c[1], 0) / ring.length).toFixed(4);
      const centLng = (ring.reduce((s, c) => s + c[0], 0) / ring.length).toFixed(4);
      const proximalUrl = `/proximal?trial=${data.trial}&plot=${p.plot_id}&lat=${centLat}&lng=${centLng}&field=${encodeURIComponent(`${data.site}, ${data.state}`)}`;

      leafletLayer.bindPopup(`
        <div style="min-width:160px">
          ${isRestricted ? `<div style="margin-bottom:8px;padding:4px 7px;background:#6b728020;border:1px solid #6b728055;border-radius:5px;font-size:10px;color:#9ca3af;">&#9888; Trt ${p.n_trt} — in-season N applied; excluded from model training</div>` : ""}
          <div style="font-size:15px;font-weight:600;margin-bottom:8px">
            Plot ${p.plot_id}
          </div>
          <div style="font-size:14px;font-weight:600;margin-bottom:6px;color:${statusColor}">
            ${statusLabel}
          </div>
          <div style="font-size:11px;color:#94a3b8;margin-bottom:8px">${confidence}</div>
          <div style="background:#0f1117;border-radius:6px;height:6px;overflow:hidden;margin-bottom:10px">
            <div style="height:100%;width:${confPct}%;background:${statusColor};border-radius:6px"></div>
          </div>
          <div style="font-size:11px;color:#64748b;line-height:1.7">
            Treatment: ${p.n_trt}<br/>
            NNI (ground truth): ${p.nni.toFixed(3)}<br/>
            Plant N (SI): ${p.plant_n_kgha} kg/ha<br/>
            Side N (SI): ${p.side_n_kgha} kg/ha
          </div>
          ${pred === 1 && !isRestricted ? `<a href="${proximalUrl}" style="display:block;margin-top:10px;padding:7px 10px;background:#f59e0b1a;border:1px solid #f59e0b55;border-radius:6px;color:#f59e0b;font-size:12px;font-weight:600;text-decoration:none;text-align:center;">Do targeted scouting</a>` : ""}
        </div>
      `);

      leafletLayer.on("mouseover", () => {
        (leafletLayer as L.Path).setStyle({ fillOpacity: isRestricted ? 0.45 : 0.9, weight: 2 });
      });
      leafletLayer.on("mouseout", () => {
        layer.resetStyle(leafletLayer as L.Path);
      });
    },
  }).addTo(map);

  layerRef.current = layer;

  // Hatch overlay for restricted treatments (9-16)
  const restrictedFeatures = data.features.filter(
    (f) => (f.properties.n_trt ?? 0) >= RESTRICTED_TRT_MIN,
  );
  if (restrictedFeatures.length > 0) {
    const restrictedFC: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: restrictedFeatures as GeoJSON.Feature[],
    };
    const hatchLayer = L.geoJSON(restrictedFC, {
      style: () => ({
        fillColor: "#6b7280",
        fillOpacity: 0,     // replaced by SVG pattern below
        color: "#6b7280",
        weight: 1,
        dashArray: "4 2",
      }),
      interactive: false,  // clicks fall through to base layer
    }).addTo(map);
    hatchLayerRef.current = hatchLayer;

    // Inject SVG diagonal-hatch pattern and apply it to each restricted path
    requestAnimationFrame(() => {
      const svgEl = map.getPanes().overlayPane?.querySelector("svg");
      if (!svgEl) return;

      let defs = svgEl.querySelector("defs");
      if (!defs) {
        defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        svgEl.insertBefore(defs, svgEl.firstChild);
      }
      if (!defs.querySelector("#n-scout-hatch")) {
        const pat = document.createElementNS("http://www.w3.org/2000/svg", "pattern");
        pat.setAttribute("id", "n-scout-hatch");
        pat.setAttribute("patternUnits", "userSpaceOnUse");
        pat.setAttribute("width", "8");
        pat.setAttribute("height", "8");
        const ln = document.createElementNS("http://www.w3.org/2000/svg", "line");
        ln.setAttribute("x1", "0"); ln.setAttribute("y1", "8");
        ln.setAttribute("x2", "8"); ln.setAttribute("y2", "0");
        ln.setAttribute("stroke", "#6b7280");
        ln.setAttribute("stroke-width", "2");
        ln.setAttribute("stroke-opacity", "0.7");
        pat.appendChild(ln);
        defs.appendChild(pat);
      }
      hatchLayer.eachLayer((fl) => {
        const path = (fl as any)._path as SVGElement | undefined;
        if (path) {
          path.setAttribute("fill", "url(#n-scout-hatch)");
          path.setAttribute("fill-opacity", "0.55");
        }
      });
    });
  }

  const bounds = layer.getBounds();
  if (bounds.isValid()) {
    map.fitBounds(bounds, { padding: [24, 24] });
  }
}

export default function ScoutingMap({ data, nStages, useFusion }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LeafletGeoJSON | null>(null);
  const hatchLayerRef = useRef<LeafletGeoJSON | null>(null);

  // Keep latest props in refs so the async init callback can access current values.
  const dataRef = useRef(data);
  const nStagesRef = useRef(nStages);
  const useFusionRef = useRef(useFusion);
  dataRef.current = data;
  nStagesRef.current = nStages;
  useFusionRef.current = useFusion;

  // Initialize the map once. After init, immediately render the first layer
  // using the refs above so we don't miss props that arrived before the
  // async import resolved.
  useEffect(() => {
    if (!containerRef.current) return;

    import("leaflet").then((L) => {
      if (mapRef.current || !containerRef.current) return;

      const map = L.map(containerRef.current, {
        zoomControl: false,
        attributionControl: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        touchZoom: false,
        boxZoom: false,
        keyboard: false,
        dragging: false,
      });

      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        attribution:
          'Tiles &copy; Esri &mdash; Source: Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA, USGS, AeroGRID, IGN, and the GIS User Community',
        maxZoom: 19,
      }).addTo(map);

      mapRef.current = map;

      // Render first layer now that the map is ready.
      renderLayer(L, map, dataRef.current, nStagesRef.current, useFusionRef.current, layerRef, hatchLayerRef);
    });

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
      hatchLayerRef.current = null;
    };
  }, []);

  // Update layer when props change. If the map isn't ready yet the init
  // callback above will handle the first render, so we can skip safely.
  useEffect(() => {
    if (!mapRef.current) return;
    import("leaflet").then((L) => {
      if (!mapRef.current) return;
      renderLayer(L, mapRef.current, data, nStages, useFusion, layerRef, hatchLayerRef);
    });
  }, [data, nStages, useFusion]);

  return (
    <div
      ref={containerRef}
      style={{ position: "absolute", inset: 0 }}
    />
  );
}
