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
) {
  const modelKey = useFusion ? "fusion" : "remote";
  const probKey = `${modelKey}_${nStages}_prob`;
  const predKey = `${modelKey}_${nStages}_pred`;

  if (layerRef.current) {
    layerRef.current.remove();
    layerRef.current = null;
  }

  const layer = L.geoJSON(data as GeoJSON.FeatureCollection, {
    style: (feature) => {
      const pred = feature?.properties?.[predKey] ?? 0;
      return {
        fillColor: pred === 1 ? DEFICIENT_COLOR : SUFFICIENT_COLOR,
        fillOpacity: 0.65,
        color: BORDER_COLOR,
        weight: 1,
      };
    },
    onEachFeature: (feature, leafletLayer) => {
      const p = feature.properties;
      const prob: number = p[probKey] ?? 0;
      const pred: number = p[predKey] ?? 0;
      const statusLabel = pred === 1 ? "Deficient" : "Sufficient";
      const confidence = probToConfidence(prob, pred);
      const confPct = Math.round((pred === 1 ? prob : 1 - prob) * 100);
      const statusColor = pred === 1 ? DEFICIENT_COLOR : SUFFICIENT_COLOR;

      leafletLayer.bindPopup(`
        <div style="min-width:160px">
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
            Plant N: ${p.plant_n_kgha} kg/ha<br/>
            Side N: ${p.side_n_kgha} kg/ha
          </div>
        </div>
      `);

      leafletLayer.on("mouseover", () => {
        (leafletLayer as L.Path).setStyle({ fillOpacity: 0.9, weight: 2 });
      });
      leafletLayer.on("mouseout", () => {
        layer.resetStyle(leafletLayer as L.Path);
      });
    },
  }).addTo(map);

  layerRef.current = layer;

  const bounds = layer.getBounds();
  if (bounds.isValid()) {
    map.fitBounds(bounds, { padding: [24, 24] });
  }
}

export default function ScoutingMap({ data, nStages, useFusion }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LeafletGeoJSON | null>(null);

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
      renderLayer(L, map, dataRef.current, nStagesRef.current, useFusionRef.current, layerRef);
    });

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  // Update layer when props change. If the map isn't ready yet the init
  // callback above will handle the first render, so we can skip safely.
  useEffect(() => {
    if (!mapRef.current) return;
    import("leaflet").then((L) => {
      if (!mapRef.current) return;
      renderLayer(L, mapRef.current, data, nStages, useFusion, layerRef);
    });
  }, [data, nStages, useFusion]);

  return (
    <div
      ref={containerRef}
      style={{ position: "absolute", inset: 0 }}
    />
  );
}
