import { formatDateTime, RISK_COLORS, RISK_LABELS } from "../format";
import type { Heatmap, RiskLevel } from "../types";

const LEGEND: RiskLevel[] = ["moderate", "high", "severe", "no_travel"];
const HOUR_MS = 3_600_000;

function hasMissingData(heatmap: Heatmap, hour: number) {
  return heatmap.points.some((point) => point.risk[hour] === null);
}

function isAllLow(heatmap: Heatmap, hour: number) {
  return heatmap.points.every((point) => point.risk[hour] === 0);
}

export function HeatmapControl({
  heatmap,
  loading,
  error,
  departureAt,
  hour,
  visible,
  onHourChange,
  onVisibleChange,
}: {
  heatmap: Heatmap | null;
  loading: boolean;
  error: string | null;
  departureAt: string;
  hour: number;
  visible: boolean;
  onHourChange: (hour: number) => void;
  onVisibleChange: (visible: boolean) => void;
}) {
  const moment = new Date(new Date(departureAt).getTime() + hour * HOUR_MS);

  return (
    <section className="heatmap-control" aria-label="Weather heatmap">
      <div className="heatmap-top">
        <label className="heatmap-toggle">
          <input
            type="checkbox"
            checked={visible}
            disabled={!heatmap}
            onChange={(event) => onVisibleChange(event.target.checked)}
          />
          Weather heatmap
        </label>
        <output className="heatmap-time">
          +{hour} h · {formatDateTime(moment)}
        </output>
      </div>

      <input
        className="heatmap-slider"
        type="range"
        aria-label="Hours after departure"
        min={0}
        max={heatmap?.hours ?? 48}
        step={1}
        value={hour}
        disabled={!heatmap || !visible}
        onChange={(event) => onHourChange(Number(event.target.value))}
      />

      <div className="heatmap-bottom">
        {loading && <span>Loading forecast for the corridor...</span>}
        {error && <span className="heatmap-error">{error}</span>}
        {heatmap && hasMissingData(heatmap, hour) && (
          <span className="heatmap-error">Some of the corridor has no forecast for this hour.</span>
        )}
        {heatmap && isAllLow(heatmap, hour) && <span>No risky weather in the corridor at this hour.</span>}
        {heatmap && !hasMissingData(heatmap, hour) && !isAllLow(heatmap, hour) && (
          <ul className="legend">
            {LEGEND.map((risk) => (
              <li key={risk}>
                <i style={{ backgroundColor: RISK_COLORS[risk] }} />
                {RISK_LABELS[risk]}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
