import maplibregl, { type Map as MapLibreMap, type MapMouseEvent, Marker, Popup } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { formatDateTime, formatDuration, formatMiles, riskColor, riskLabel } from "../format";
import {
  addHeatmapLayers,
  removeHeatmapLayers,
  setHeatmapVisible,
  showHeatmapHour,
} from "../map/heatmapLayers";
import {
  addRouteLayers,
  CHECKPOINT_LAYER,
  ROUTE_LAYER,
  SELECTED_CHECKPOINT_LAYER,
  SELECTED_ROUTE_LAYER,
  setRouteData,
  setSelectedRoute,
} from "../map/routeLayers";
import type { Checkpoint, Heatmap, RoutePlan, TripPlan } from "../types";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
const US_CENTER: [number, number] = [-98.5, 39.5];
const FIT_PADDING = { top: 60, right: 60, bottom: 150, left: 60 };

// Spreads the summaries out along their routes, which often share the same road near the middle.
const LABEL_POSITIONS = [0.5, 0.33, 0.67];

function checkpointPopup(route: RoutePlan, checkpoint: Checkpoint) {
  const root = document.createElement("div");
  root.className = "popup";

  const title = document.createElement("strong");
  title.textContent = riskLabel(checkpoint.risk);
  title.style.color = riskColor(checkpoint.risk);
  root.append(title);

  const lines = [
    `Route ${route.id}, mile ${Math.round(checkpoint.mile)}`,
    `ETA ${formatDateTime(checkpoint.eta)}`,
  ];
  if (checkpoint.weather) {
    const { wind_mph, rain_in_hr, snow_in_hr } = checkpoint.weather;
    lines.push(`Wind ${Math.round(wind_mph)} mph`, `Rain ${rain_in_hr} in/hr`, `Snow ${snow_in_hr} in/hr`);
  } else {
    lines.push("The forecast doesn't reach this arrival time");
  }
  for (const line of lines) {
    const row = document.createElement("div");
    row.textContent = line;
    root.append(row);
  }
  return root;
}

function routeLabel(route: RoutePlan, recommended: boolean, onSelect: (id: string) => void) {
  const label = document.createElement("button");
  label.type = "button";
  label.className = `route-label${recommended ? " recommended" : ""}`;
  label.dataset.routeId = route.id;

  const name = document.createElement("b");
  name.textContent = route.id;
  const stats = document.createElement("span");
  const dangerous = route.miles_by_risk.severe + route.miles_by_risk.no_travel;
  stats.textContent = [
    formatDuration(route.duration_s),
    formatMiles(route.distance_miles),
    dangerous > 0 ? `${formatMiles(dangerous)} severe+` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  label.append(name, stats);

  label.addEventListener("click", (event) => {
    event.stopPropagation();
    onSelect(route.id);
  });
  return label;
}

function tripBounds(plan: TripPlan) {
  const bounds = new maplibregl.LngLatBounds();
  for (const route of plan.routes) {
    for (const checkpoint of route.checkpoints) {
      bounds.extend([checkpoint.lon, checkpoint.lat]);
    }
  }
  return bounds;
}

function fitPadding(map: MapLibreMap) {
  const { clientWidth, clientHeight } = map.getContainer();
  const small = clientWidth < 500 || clientHeight < 500;
  return small ? { top: 30, right: 30, bottom: 110, left: 30 } : FIT_PADDING;
}

export function RouteMap({
  plan,
  selectedRouteId,
  onSelectRoute,
  heatmap,
  heatmapVisible,
  hour,
}: {
  plan: TripPlan | null;
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  heatmap: Heatmap | null;
  heatmapVisible: boolean;
  hour: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const planRef = useRef(plan);
  const shownHour = useRef(0);
  const popupRef = useRef<Popup | null>(null);
  const onSelectRef = useRef(onSelectRoute);
  planRef.current = plan;
  onSelectRef.current = onSelectRoute;

  useEffect(() => {
    const instance = new maplibregl.Map({
      container: containerRef.current!,
      style: MAP_STYLE,
      center: US_CENTER,
      zoom: 3.4,
      attributionControl: { compact: true },
    });
    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    instance.on("load", () => {
      addRouteLayers(instance);
      setMap(instance);
    });

    const showCheckpoint = (event: MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      const feature = event.features?.[0];
      const route = planRef.current?.routes.find((r) => r.id === feature?.properties.routeId);
      if (!feature || !route) {
        return;
      }
      const checkpoint = route.checkpoints[feature.properties.index];
      popupRef.current?.remove();
      popupRef.current = new Popup({ offset: 10, maxWidth: "260px" })
        .setLngLat([checkpoint.lon, checkpoint.lat])
        .setDOMContent(checkpointPopup(route, checkpoint))
        .addTo(instance);
    };

    const selectRoute = (event: MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      const routeId = event.features?.[0]?.properties.routeId;
      if (routeId) {
        onSelectRef.current(routeId);
      }
    };

    for (const layer of [SELECTED_CHECKPOINT_LAYER, CHECKPOINT_LAYER]) {
      instance.on("click", layer, showCheckpoint);
    }
    instance.on("click", ROUTE_LAYER, selectRoute);

    for (const layer of [SELECTED_CHECKPOINT_LAYER, CHECKPOINT_LAYER, ROUTE_LAYER, SELECTED_ROUTE_LAYER]) {
      instance.on("mouseenter", layer, () => {
        instance.getCanvas().style.cursor = "pointer";
      });
      instance.on("mouseleave", layer, () => {
        instance.getCanvas().style.cursor = "";
      });
    }

    return () => {
      setMap(null);
      instance.remove();
    };
  }, []);

  const labelMarkers = useRef<HTMLElement[]>([]);

  useEffect(() => {
    if (!map) {
      return;
    }
    setRouteData(map, plan);
    if (!plan) {
      return;
    }

    map.fitBounds(tripBounds(plan), { padding: fitPadding(map), duration: 700 });

    const markers: Marker[] = [
      new Marker({ color: "#1d2733" }).setLngLat([plan.origin.lon, plan.origin.lat]),
      new Marker({ color: "#1d2733" }).setLngLat([plan.destination.lon, plan.destination.lat]),
    ];

    const labels = plan.routes.map((route, index) => {
      const element = routeLabel(
        route,
        route.id === plan.recommendation.route_id,
        (id) => onSelectRef.current(id),
      );
      const position = Math.floor(route.checkpoints.length * LABEL_POSITIONS[index]);
      const checkpoint = route.checkpoints[position];
      markers.push(new Marker({ element }).setLngLat([checkpoint.lon, checkpoint.lat]));
      return element;
    });
    labelMarkers.current = labels;

    markers.forEach((marker) => marker.addTo(map));
    return () => {
      markers.forEach((marker) => marker.remove());
      // A popup left open would keep describing a checkpoint from the trip being replaced.
      popupRef.current?.remove();
      popupRef.current = null;
    };
  }, [map, plan]);

  useEffect(() => {
    if (!map || !selectedRouteId) {
      return;
    }
    setSelectedRoute(map, selectedRouteId);
    for (const label of labelMarkers.current) {
      label.classList.toggle("selected", label.dataset.routeId === selectedRouteId);
    }
  }, [map, plan, selectedRouteId]);

  useEffect(() => {
    if (!map || !heatmap) {
      return;
    }
    addHeatmapLayers(map, heatmap, shownHour.current, ROUTE_LAYER);
    return () => removeHeatmapLayers(map, heatmap.hours);
  }, [map, heatmap]);

  useEffect(() => {
    if (map && heatmap) {
      setHeatmapVisible(map, shownHour.current, heatmapVisible);
    }
  }, [map, heatmap, heatmapVisible]);

  useEffect(() => {
    if (!map || !heatmap) {
      shownHour.current = hour;
      return;
    }
    if (heatmapVisible) {
      showHeatmapHour(map, shownHour.current, hour);
      shownHour.current = hour;
    }
  }, [map, heatmap, heatmapVisible, hour]);

  return <div ref={containerRef} className="map" />;
}
