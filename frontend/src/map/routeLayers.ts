import type { ExpressionSpecification, GeoJSONSource, Map } from "maplibre-gl";
import { NO_DATA_COLOR, RISK_COLORS } from "../format";
import type { RiskLevel, TripPlan } from "../types";

export const ROUTE_LAYER = "route-other";
export const SELECTED_ROUTE_LAYER = "route-selected";
export const CHECKPOINT_LAYER = "checkpoint-other";
export const SELECTED_CHECKPOINT_LAYER = "checkpoint-selected";

const ROUTE_SOURCE = "routes";
const CHECKPOINT_SOURCE = "checkpoints";
const SELECTED_CASING_LAYER = "route-selected-casing";

const riskColorExpression: ExpressionSpecification = [
  "match",
  ["get", "risk"],
  ...(Object.entries(RISK_COLORS) as [RiskLevel, string][]).flat(),
  NO_DATA_COLOR,
] as unknown as ExpressionSpecification;

function routesGeoJson(plan: TripPlan): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: plan.routes.flatMap((route) =>
      route.segments.map((segment) => ({
        type: "Feature" as const,
        geometry: {
          type: "LineString" as const,
          coordinates: segment.path.map(([lat, lon]) => [lon, lat]),
        },
        properties: { routeId: route.id, risk: segment.risk ?? "no_data" },
      })),
    ),
  };
}

function checkpointsGeoJson(plan: TripPlan): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: plan.routes.flatMap((route) =>
      route.checkpoints.map((checkpoint, index) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [checkpoint.lon, checkpoint.lat] },
        properties: { routeId: route.id, risk: checkpoint.risk ?? "no_data", index },
      })),
    ),
  };
}

export function addRouteLayers(map: Map) {
  map.addSource(ROUTE_SOURCE, { type: "geojson", data: emptyCollection });
  map.addSource(CHECKPOINT_SOURCE, { type: "geojson", data: emptyCollection });

  const lineLayout = { "line-cap": "round", "line-join": "round" } as const;

  map.addLayer({
    id: ROUTE_LAYER,
    type: "line",
    source: ROUTE_SOURCE,
    layout: lineLayout,
    paint: { "line-color": riskColorExpression, "line-width": 3.5, "line-opacity": 0.45 },
  });
  map.addLayer({
    id: CHECKPOINT_LAYER,
    type: "circle",
    source: CHECKPOINT_SOURCE,
    paint: {
      "circle-radius": 3,
      "circle-color": riskColorExpression,
      "circle-opacity": 0.6,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 0.75,
      "circle-stroke-opacity": 0.6,
    },
  });
  map.addLayer({
    id: SELECTED_CASING_LAYER,
    type: "line",
    source: ROUTE_SOURCE,
    layout: lineLayout,
    paint: { "line-color": "#ffffff", "line-width": 8.5 },
  });
  map.addLayer({
    id: SELECTED_ROUTE_LAYER,
    type: "line",
    source: ROUTE_SOURCE,
    layout: lineLayout,
    paint: { "line-color": riskColorExpression, "line-width": 5.5 },
  });
  map.addLayer({
    id: SELECTED_CHECKPOINT_LAYER,
    type: "circle",
    source: CHECKPOINT_SOURCE,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 4, 10, 7],
      "circle-color": riskColorExpression,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 1.5,
    },
  });
}

const emptyCollection: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function geoJsonSource(map: Map, id: string) {
  return map.getSource(id) as GeoJSONSource;
}

export function setRouteData(map: Map, plan: TripPlan | null) {
  geoJsonSource(map, ROUTE_SOURCE).setData(plan ? routesGeoJson(plan) : emptyCollection);
  geoJsonSource(map, CHECKPOINT_SOURCE).setData(plan ? checkpointsGeoJson(plan) : emptyCollection);
}

export function setSelectedRoute(map: Map, routeId: string) {
  const isSelected: ExpressionSpecification = ["==", ["get", "routeId"], routeId];
  const isOther: ExpressionSpecification = ["!=", ["get", "routeId"], routeId];

  map.setFilter(ROUTE_LAYER, isOther);
  map.setFilter(CHECKPOINT_LAYER, isOther);
  map.setFilter(SELECTED_CASING_LAYER, isSelected);
  map.setFilter(SELECTED_ROUTE_LAYER, isSelected);
  map.setFilter(SELECTED_CHECKPOINT_LAYER, isSelected);
}
