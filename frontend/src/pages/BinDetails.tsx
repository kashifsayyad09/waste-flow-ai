import { FillMeter, PriorityBadge, StateMessage, titleCase } from "../components/ui";
import type { BinRow } from "../types";

interface Props {
  row: BinRow | undefined;
  onBack: () => void;
}

export function BinDetails({ row, onBack }: Props) {
  if (!row) {
    return (
      <>
        <button className="btn btn-outline" onClick={onBack}>Back</button>
        <StateMessage kind="empty" title="Bin not found" detail="This bin is not in the latest data. Go back and pick another." />
      </>
    );
  }
  const { bin, priority } = row;
  const facts: [string, string][] = [
    ["Location", bin.location],
    ["Coordinates", `${bin.latitude.toFixed(4)}, ${bin.longitude.toFixed(4)}`],
    ["Waste type", titleCase(bin.waste_type)],
    ["Temperature", `${bin.temperature}°C`],
    ["Days since collection", String(bin.days_since_collection)],
    ["Last collected", new Date(bin.last_collected).toLocaleString()],
    ["Estimated overflow", `in ${bin.estimated_overflow_time} hours`],
    ["Sensor status", titleCase(bin.status)],
  ];

  return (
    <>
      <button className="btn btn-outline" onClick={onBack}>Back</button>
      <section className="card detail-head">
        <div>
          <p className="muted">{bin.id}</p>
          <p className="next-name">{bin.name}</p>
          <FillMeter value={bin.fill_level} />
        </div>
        <div className="next-score">
          <PriorityBadge level={priority.priority_level} />
          <span className="score">{priority.priority_score}</span>
        </div>
      </section>

      <div className="grid-2">
        <section className="card" aria-labelledby="info-title">
          <h2 id="info-title">Bin information</h2>
          <dl className="facts">
            {facts.map(([k, v]) => (
              <div key={k}><dt className="muted">{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
        </section>

        <section className="card" aria-labelledby="why-title">
          <h2 id="why-title">Why this score</h2>
          {priority.reasons.length ? (
            <ul className="reasons">{priority.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          ) : (
            <p className="muted">No factor is adding meaningful urgency.</p>
          )}
          <ul className="breakdown">
            {priority.breakdown.map((f) => (
              <li key={f.factor}>
                <span>{f.factor}</span>
                <div className="fill-track"><div className="fill-bar" style={{ width: `${(f.points / f.max_points) * 100}%` }} /></div>
                <span className="muted">{f.points} / {f.max_points}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
