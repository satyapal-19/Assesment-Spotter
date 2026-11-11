import { type FormEvent, memo, useEffect, useId, useState } from "react";
import { fetchSuggestions } from "../api";
import { toLocalInputValue } from "../format";
import type { TripRequest } from "../types";

const INTERVALS = [10, 25, 50];
const SUGGEST_DELAY_MS = 250;
const MIN_SUGGEST_LENGTH = 3;

function PlaceInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const listId = useId();
  const [suggestions, setSuggestions] = useState<string[]>([]);

  useEffect(() => {
    if (value.trim().length < MIN_SUGGEST_LENGTH) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      // Suggestions are optional, so a failed lookup just leaves the list as it was.
      fetchSuggestions(value, controller.signal).then(setSuggestions, () => undefined);
    }, SUGGEST_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  return (
    <label className="field">
      <span>{label}</span>
      <input
        required
        list={listId}
        autoComplete="off"
        placeholder="City, state or address"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <datalist id={listId}>
        {suggestions.map((suggestion) => (
          <option key={suggestion} value={suggestion} />
        ))}
      </datalist>
    </label>
  );
}

function defaultDeparture() {
  const date = new Date(Date.now() + 60 * 60 * 1000);
  date.setMinutes(0, 0, 0);
  return toLocalInputValue(date);
}

export const TripForm = memo(function TripForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (trip: TripRequest) => void;
}) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [departure, setDeparture] = useState(defaultDeparture);
  const [load, setLoad] = useState("");
  const [interval, setInterval] = useState(25);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit({
      origin,
      destination,
      departure_at: new Date(departure).toISOString(),
      load_lb: Number(load),
      interval_miles: interval,
    });
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit}>
      <PlaceInput label="Origin" value={origin} onChange={setOrigin} />
      <PlaceInput label="Destination" value={destination} onChange={setDestination} />
      <div className="field-row">
        <label className="field">
          <span>Departure</span>
          <input
            required
            type="datetime-local"
            value={departure}
            onChange={(event) => setDeparture(event.target.value)}
          />
        </label>
        <label className="field field-load">
          <span>Load (lb)</span>
          <input
            required
            type="number"
            min={1}
            max={200000}
            step={1}
            placeholder="40000"
            value={load}
            onChange={(event) => setLoad(event.target.value)}
          />
        </label>
      </div>
      <fieldset className="field intervals">
        <legend>Check weather every</legend>
        <div className="segmented">
          {INTERVALS.map((miles) => (
            <label key={miles} className={miles === interval ? "active" : ""}>
              <input
                type="radio"
                name="interval"
                checked={miles === interval}
                onChange={() => setInterval(miles)}
              />
              {miles} mi
            </label>
          ))}
        </div>
      </fieldset>
      <button className="submit" type="submit" disabled={busy}>
        {busy ? "Checking..." : "Compare routes"}
      </button>
    </form>
  );
});
