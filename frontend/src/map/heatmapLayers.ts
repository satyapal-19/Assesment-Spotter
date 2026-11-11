import type { ExpressionSpecification, HeatmapLayerSpecification, Map } from "maplibre-gl";
import type { Heatmap } from "../types";

const SOURCE_ID = "heatmap";
const VISIBLE_OPACITY = 0.8;
const MAX_RADIUS_ZOOM = 9;
const PIXELS_PER_MILE_AT_ZOOM_0 = 512 / 24_901;

// Kernel radius as a multiple of the grid spacing. Larger blends neighbouring cells more smoothly.
const RADIUS_TO_STEP = 1.6;

// MapLibre's kernel is a Gaussian with sigma = radius / 3 and a peak of 1 / sqrt(2 pi). Summed over
// a regular grid, a field of equal weights reaches a density of about
// weight * 2 pi (sigma / step)^2 / sqrt(2 pi). Dividing that out makes density track the risk
// weight, so the colour stops below line up with the risk levels.
const KERNEL_SUM = Math.sqrt(2 * Math.PI) * (RADIUS_TO_STEP / 3) ** 2;
const INTENSITY = 1 / KERNEL_SUM;

const RISK_WEIGHTS = [0, 0.3, 0.55, 0.8, 1];

const HEAT_COLORS: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["heatmap-density"],
  0,
  "rgba(217, 164, 6, 0)",
  0.12,
  "rgba(217, 164, 6, 0.3)",
  0.3,
  "rgba(217, 164, 6, 0.7)",
  0.55,
  "rgba(232, 112, 42, 0.8)",
  0.8,
  "rgba(212, 42, 60, 0.88)",
  1,
  "rgba(107, 29, 122, 0.92)",
];

function layerId(hour: number): string {
  return `heatmap-hour-${hour}`;
}

function toGeoJson(heatmap: Heatmap): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: heatmap.points.map((point) => {
      const properties: Record<string, number> = {};
      point.risk.forEach((level, hour) => {
        properties[`h${hour}`] = level === null ? 0 : RISK_WEIGHTS[level];
      });
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [point.lon, point.lat] },
        properties,
      };
    }),
  };
}

function radius(heatmap: Heatmap): ExpressionSpecification {
  const midLat = heatmap.points.reduce((sum, p) => sum + p.lat, 0) / heatmap.points.length;
  const atZoom0 =
    heatmap.step_miles * RADIUS_TO_STEP * PIXELS_PER_MILE_AT_ZOOM_0 * (1 / Math.cos((midLat * Math.PI) / 180));
  return [
    "interpolate",
    ["exponential", 2],
    ["zoom"],
    0,
    atZoom0,
    MAX_RADIUS_ZOOM,
    atZoom0 * 2 ** MAX_RADIUS_ZOOM,
  ];
}

/**
 * Each forecast hour gets its own layer, and the slider only changes which one is opaque.
 *
 * Changing a data-driven property like heatmap-weight makes MapLibre rebuild the tiles for the
 * source, which shows up as lag while dragging. heatmap-opacity is a plain paint property, and
 * layers at zero opacity skip their render pass, so having one layer per hour costs very little.
 */
export function addHeatmapLayers(map: Map, heatmap: Heatmap, hour: number, beforeLayer: string) {
  map.addSource(SOURCE_ID, { type: "geojson", data: toGeoJson(heatmap) });

  const heatmapRadius = radius(heatmap);
  for (let h = 0; h <= heatmap.hours; h += 1) {
    const layer: HeatmapLayerSpecification = {
      id: layerId(h),
      type: "heatmap",
      source: SOURCE_ID,
      paint: {
        "heatmap-weight": ["get", `h${h}`],
        "heatmap-radius": heatmapRadius,
        "heatmap-intensity": INTENSITY,
        "heatmap-color": HEAT_COLORS,
        "heatmap-opacity": h === hour ? VISIBLE_OPACITY : 0,
        "heatmap-opacity-transition": { duration: 0 },
      },
    };
    map.addLayer(layer, beforeLayer);
  }
}

export function removeHeatmapLayers(map: Map, hours: number) {
  for (let h = 0; h <= hours; h += 1) {
    if (map.getLayer(layerId(h))) {
      map.removeLayer(layerId(h));
    }
  }
  if (map.getSource(SOURCE_ID)) {
    map.removeSource(SOURCE_ID);
  }
}

export function showHeatmapHour(map: Map, previousHour: number, hour: number) {
  if (previousHour === hour) {
    return;
  }
  map.setPaintProperty(layerId(previousHour), "heatmap-opacity", 0);
  map.setPaintProperty(layerId(hour), "heatmap-opacity", VISIBLE_OPACITY);
}

export function setHeatmapVisible(map: Map, hour: number, visible: boolean) {
  map.setPaintProperty(layerId(hour), "heatmap-opacity", visible ? VISIBLE_OPACITY : 0);
}
