import type { PriorityLevel } from "../types";

const LEVEL_LABEL: Record<PriorityLevel, string> = { CRITICAL: "Critical", HIGH: "High", MEDIUM: "Medium", LOW: "Low" };

export function PriorityBadge({ level }: { level: PriorityLevel }) {
  return <span className={`badge badge-${level.toLowerCase()}`}>{LEVEL_LABEL[level]}</span>;
}

export function FillMeter({ value }: { value: number }) {
  return (
    <div className="fill" role="img" aria-label={`${value}% full`}>
      <div className="fill-track">
        <div className="fill-bar" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
      <span className="fill-value">{value}%</span>
    </div>
  );
}

interface StateProps {
  kind: "loading" | "error" | "empty";
  title: string;
  detail?: string;
  onRetry?: () => void;
}

export function StateMessage({ kind, title, detail, onRetry }: StateProps) {
  return (
    <div className={`state state-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <p className="state-title">{title}</p>
      {detail && <p className="muted">{detail}</p>}
      {onRetry && (
        <button className="btn btn-primary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export const titleCase = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
