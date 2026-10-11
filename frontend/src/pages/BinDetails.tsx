import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { CollectionRecord } from "../types";
import { FillMeter, PriorityBadge, StateMessage, titleCase } from "../components/ui";
import type { BinRow } from "../types";

interface Props {
  row: BinRow | undefined;
  onBack: () => void;
}

type History = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; records: CollectionRecord[] };

function useCollectionHistory(binId: string | undefined): History {
  const [history, setHistory] = useState<History>({ status: "loading" });
  useEffect(() => {
    if (!binId) return;
    let cancelled = false;
    setHistory({ status: "loading" });
    api.getCollections(binId)
      .then((records) => !cancelled && setHistory({ status: "ready", records }))
      .catch((e) => !cancelled && setHistory({ status: "error", message: e instanceof Error ? e.message : "Could not load collection history." }));
    return () => { cancelled = true; };
  }, [binId]);
  return history;
}

export function BinDetails({ row, onBack }: Props) {
  const history = useCollectionHistory(row?.bin.id);
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

      <section className="card" aria-labelledby="hist-title">
        <h2 id="hist-title">Collection history</h2>
        {history.status === "loading" && <p className="muted">Loading history…</p>}
        {history.status === "error" && <p role="alert">{history.message}</p>}
        {history.status === "ready" && history.records.length === 0 && <p className="muted">No collections recorded for this bin yet.</p>}
        {history.status === "ready" && history.records.length > 0 && (
          <ul className="list">
            {history.records.map((r) => (
              <li key={r.id}>
                <span>{new Date(r.collected_at).toLocaleString()}{r.notes ? ` · ${r.notes}` : ""}</span>
                <span className="row-meta">{titleCase(r.collection_status)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
