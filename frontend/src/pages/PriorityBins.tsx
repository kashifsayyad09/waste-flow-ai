import { FillMeter, PriorityBadge, StateMessage, titleCase } from "../components/ui";
import type { BinRow } from "../types";

interface Props {
  rows: BinRow[];
  onSelect: (id: string) => void;
}

export function PriorityBins({ rows, onSelect }: Props) {
  if (rows.length === 0) return <StateMessage kind="empty" title="No bins to show" detail="Priorities appear here once the backend returns bin data." />;
  return (
    <div className="card table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Bin</th><th>Location</th><th>Fill level</th><th>Waste</th><th>Score</th><th>Level</th><th>Main reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ bin, priority }) => (
            <tr key={bin.id} className={`row-${priority.priority_level.toLowerCase()}`}>
              <td data-label="Bin"><button className="link" onClick={() => onSelect(bin.id)}>{bin.id}</button></td>
              <td data-label="Location">{bin.location}</td>
              <td data-label="Fill level"><FillMeter value={bin.fill_level} /></td>
              <td data-label="Waste">{titleCase(bin.waste_type)}</td>
              <td data-label="Score"><span className="score-sm">{priority.priority_score}</span></td>
              <td data-label="Level"><PriorityBadge level={priority.priority_level} /></td>
              <td data-label="Main reason">{priority.reasons[0] ?? "No urgent factors"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
