import { PriorityBadge, StateMessage } from "../components/ui";
import type { CollectionPlan as Plan } from "../types";

interface Props {
  plan: Plan;
  onSelect: (id: string) => void;
}

export function CollectionPlan({ plan, onSelect }: Props) {
  if (plan.collection_order.length === 0) return <StateMessage kind="empty" title="No collection order yet" detail="The plan is built from bin priorities; none were returned." />;
  return (
    <section aria-labelledby="plan-title">
      <h2 id="plan-title">Recommended collection order</h2>
      <p className="muted plan-note">
        Ranked by priority score, highest first. Generated {new Date(plan.generated_at).toLocaleString()}. This is an order, not a driving route.
      </p>
      <ol className="plan">
        {plan.collection_order.map((s) => (
          <li className={`card plan-item row-${s.priority_level.toLowerCase()}`} key={s.bin_id}>
            <span className="plan-rank" aria-label={`Rank ${s.rank}`}>{s.rank}</span>
            <div className="plan-body">
              <div className="plan-top">
                <button className="link" onClick={() => onSelect(s.bin_id)}>{s.bin_id} · {s.location}</button>
                <span className="row-meta"><PriorityBadge level={s.priority_level} /><span className="score-sm">{s.priority_score}</span></span>
              </div>
              <p className="muted">Why here: {s.reason}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
