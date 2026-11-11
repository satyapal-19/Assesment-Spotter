import { memo } from "react";
import {
  formatDateTime,
  formatDuration,
  formatMiles,
  NO_DATA_COLOR,
  RISK_COLORS,
  RISK_LABELS,
  riskColor,
  riskLabel,
} from "../format";
import type { RiskLevel, RoutePlan, TripPlan } from "../types";

const RISK_ORDER: RiskLevel[] = ["low", "moderate", "high", "severe", "no_travel"];

function RiskBar({ route }: { route: RoutePlan }) {
  const parts = [
    ...RISK_ORDER.map((risk) => ({
      key: risk,
      miles: route.miles_by_risk[risk],
      color: RISK_COLORS[risk],
    })),
    { key: "no_data", miles: route.miles_by_risk.no_data, color: NO_DATA_COLOR },
  ];
  return (
    <div className="risk-bar" aria-hidden="true">
      {parts.map(
        (part) =>
          part.miles > 0 && (
            <span
              key={part.key}
              style={{ flexGrow: part.miles, backgroundColor: part.color }}
            />
          ),
      )}
    </div>
  );
}

function RiskMiles({ route }: { route: RoutePlan }) {
  const rows = RISK_ORDER.filter((risk) => route.miles_by_risk[risk] > 0);
  return (
    <ul className="risk-miles">
      {rows.map((risk) => (
        <li key={risk}>
          <i style={{ backgroundColor: RISK_COLORS[risk] }} />
          {RISK_LABELS[risk]} <b>{formatMiles(route.miles_by_risk[risk])}</b>
        </li>
      ))}
      {route.miles_by_risk.no_data > 0 && (
        <li>
          <i style={{ backgroundColor: NO_DATA_COLOR }} />
          No data <b>{formatMiles(route.miles_by_risk.no_data)}</b>
        </li>
      )}
    </ul>
  );
}

function CheckpointTable({ route }: { route: RoutePlan }) {
  return (
    <details className="checkpoints">
      <summary>{route.checkpoints.length} checkpoints</summary>
      <div className="checkpoint-scroll">
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA</th>
              <th>Risk</th>
              <th>Wind</th>
              <th>Rain</th>
              <th>Snow</th>
            </tr>
          </thead>
          <tbody>
            {route.checkpoints.map((checkpoint, index) => (
              <tr key={index}>
                <td>{Math.round(checkpoint.mile)}</td>
                <td>{formatDateTime(checkpoint.eta)}</td>
                <td style={{ color: riskColor(checkpoint.risk) }}>{riskLabel(checkpoint.risk)}</td>
                <td>{checkpoint.weather ? Math.round(checkpoint.weather.wind_mph) : "-"}</td>
                <td>{checkpoint.weather?.rain_in_hr ?? "-"}</td>
                <td>{checkpoint.weather?.snow_in_hr ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="units">Wind in mph, rain and snow in in/hr.</p>
    </details>
  );
}

function RouteCard({
  route,
  recommended,
  safe,
  selected,
  onSelect,
}: {
  route: RoutePlan;
  recommended: boolean;
  safe: boolean;
  selected: boolean;
  onSelect: (routeId: string) => void;
}) {
  return (
    <article className={`route-card${selected ? " selected" : ""}`}>
      <button
        className="route-card-header"
        type="button"
        aria-pressed={selected}
        onClick={() => onSelect(route.id)}
      >
        <span className="route-name">Route {route.id}</span>
        {recommended && (
          <span className={`badge ${safe ? "badge-best" : "badge-warn"}`}>
            {safe ? "Recommended" : "Least risky"}
          </span>
        )}
        <span className="route-stats">
          {formatDuration(route.duration_s)} · {formatMiles(route.distance_miles)} · avg risk{" "}
          {route.average_risk?.toFixed(2) ?? "unknown"}
        </span>
        <RiskBar route={route} />
      </button>
      <RiskMiles route={route} />
      {route.miles_by_risk.no_data > 0 && (
        <p className="notice notice-warn">Part of this route is beyond the forecast range.</p>
      )}
      {selected && <CheckpointTable route={route} />}
    </article>
  );
}

export const RouteList = memo(function RouteList({
  plan,
  selectedRouteId,
  onSelect,
}: {
  plan: TripPlan;
  selectedRouteId: string;
  onSelect: (routeId: string) => void;
}) {
  const { recommendation } = plan;
  const verdict = !recommendation.is_safe
    ? { tone: "notice-error", headline: "No safe route right now." }
    : recommendation.is_complete
      ? { tone: "notice-best", headline: `Route ${recommendation.route_id} is the best choice.` }
      : {
          tone: "notice-warn",
          headline: `Route ${recommendation.route_id} ranks best on the forecast so far.`,
        };

  return (
    <section className="results">
      <div className="trip-summary">
        <b>{plan.origin.name}</b> to <b>{plan.destination.name}</b>
        <br />
        Leaving {formatDateTime(plan.departure_at)} with {plan.load_lb.toLocaleString()} lb
      </div>

      <p className={`notice ${verdict.tone}`} role={recommendation.is_safe ? undefined : "alert"}>
        <b>{verdict.headline}</b> {recommendation.reason}
      </p>

      {plan.routes.length < 3 && (
        <p className="notice notice-warn">
          Only {plan.routes.length} distinct truck route
          {plan.routes.length === 1 ? " exists" : "s exist"} between these places.
        </p>
      )}

      {plan.routes.map((route) => (
        <RouteCard
          key={route.id}
          route={route}
          recommended={route.id === recommendation.route_id}
          safe={recommendation.is_safe}
          selected={route.id === selectedRouteId}
          onSelect={onSelect}
        />
      ))}

      <p className="assumption">
        ETAs are drive time only and don't include rest breaks or stops.
      </p>
    </section>
  );
});
