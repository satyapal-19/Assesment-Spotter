import { useCallback, useRef, useState } from "react";
import { fetchHeatmap, planTrip } from "./api";
import { HeatmapControl } from "./components/HeatmapControl";
import { RouteList } from "./components/RouteList";
import { RouteMap } from "./components/RouteMap";
import { TripForm } from "./components/TripForm";
import type { Heatmap, TripPlan, TripRequest } from "./types";

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export default function App() {
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  const [heatmapError, setHeatmapError] = useState<string | null>(null);
  const [heatmapVisible, setHeatmapVisible] = useState(true);
  const [hour, setHour] = useState(0);

  const activeRequest = useRef<AbortController | null>(null);

  const loadHeatmap = useCallback(async (nextPlan: TripPlan, signal: AbortSignal) => {
    setHeatmapLoading(true);
    try {
      setHeatmap(await fetchHeatmap(nextPlan, signal));
    } catch (error) {
      if (!isAbort(error)) {
        setHeatmapError(messageOf(error));
      }
    } finally {
      if (!signal.aborted) {
        setHeatmapLoading(false);
      }
    }
  }, []);

  const handleSubmit = useCallback(
    async (trip: TripRequest) => {
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;

      setPlanning(true);
      setPlanError(null);
      setHeatmap(null);
      setHeatmapError(null);
      setHour(0);

      try {
        const nextPlan = await planTrip(trip, controller.signal);
        setPlan(nextPlan);
        setSelectedRouteId(nextPlan.recommendation.route_id);
        setPlanning(false);
        void loadHeatmap(nextPlan, controller.signal);
      } catch (error) {
        if (!isAbort(error)) {
          setPlan(null);
          setPlanError(messageOf(error));
          setPlanning(false);
        }
      }
    },
    [loadHeatmap],
  );

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="sidebar-header">
          <h1>Truck Weather Routing</h1>
          <p>Compare routes by the weather you'll meet when you get there.</p>
        </header>
        <TripForm busy={planning} onSubmit={handleSubmit} />
        {planError && (
          <p className="notice notice-error" role="alert">
            {planError}
          </p>
        )}
        {plan && selectedRouteId && (
          <RouteList plan={plan} selectedRouteId={selectedRouteId} onSelect={setSelectedRouteId} />
        )}
      </aside>

      <main className="map-area">
        <RouteMap
          plan={plan}
          selectedRouteId={selectedRouteId}
          onSelectRoute={setSelectedRouteId}
          heatmap={heatmap}
          heatmapVisible={heatmapVisible}
          hour={hour}
        />
        {planning && <div className="map-status">Checking routes and forecasts...</div>}
        {plan && (
          <HeatmapControl
            heatmap={heatmap}
            loading={heatmapLoading}
            error={heatmapError}
            departureAt={plan.departure_at}
            hour={hour}
            visible={heatmapVisible}
            onHourChange={setHour}
            onVisibleChange={setHeatmapVisible}
          />
        )}
      </main>
    </div>
  );
}
