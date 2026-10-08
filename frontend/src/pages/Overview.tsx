import { PriorityBadge, StateMessage } from "../components/ui";
import type { BinRow } from "../types";

interface Props {
  rows: BinRow[];
  onSelect: (id: string) => void;
}

export function Overview({ rows, onSelect }: Props) {
  if (rows.length === 0) return <StateMessage kind="empty" title="No bins yet" detail="The backend returned no bins to prioritise." />;

  const count = (...levels: string[]) => rows.filter((r) => levels.includes(r.priority.priority_level)).length;
  const avgFill = Math.round(rows.reduce((sum, r) => sum + r.bin.fill_level, 0) / rows.length);
  const immediate = rows.filter((r) => ["CRITICAL", "HIGH"].includes(r.priority.priority_level));
  const next = rows[0];

  const stats = [
    { label: "Total bins", value: rows.length },
    { label: "Critical bins", value: count("CRITICAL") },
    { label: "High priority bins", value: count("HIGH") },
    { label: "Average fill level", value: `${avgFill}%` },
    { label: "Need immediate collection", value: immediate.length },
  ];

  return (
    <>
      <section className="grid-stats" aria-label="Fleet summary">
        {stats.map((s) => (
          <div className="card stat" key={s.label}>
            <span className="stat-value">{s.value}</span>
            <span className="muted">{s.label}</span>
          </div>
        ))}
      </section>

      <section className="card next" aria-labelledby="next-title">
        <h2 id="next-title">Collect next</h2>
        <div className="next-head">
          <div>
            <p className="next-name">{next.bin.name}</p>
            <p className="muted">{next.bin.id} · {next.bin.location}</p>
          </div>
          <div className="next-score">
            <PriorityBadge level={next.priority.priority_level} />
            <span className="score">{next.priority.priority_score}</span>
          </div>
        </div>
        <ul className="reasons">
          {next.priority.reasons.map((r) => <li key={r}>{r}</li>)}
        </ul>
        <button className="btn btn-accent" onClick={() => onSelect(next.bin.id)}>Inspect this bin</button>
      </section>

      <section className="card" aria-labelledby="imm-title">
        <h2 id="imm-title">Needs immediate collection</h2>
        {immediate.length === 0 ? (
          <p className="muted">Nothing is critical or high right now.</p>
        ) : (
          <ul className="list">
            {immediate.map((r) => (
              <li key={r.bin.id}>
                <button className="link" onClick={() => onSelect(r.bin.id)}>{r.bin.id} · {r.bin.location}</button>
                <span className="row-meta"><PriorityBadge level={r.priority.priority_level} /><span className="score-sm">{r.priority.priority_score}</span></span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
