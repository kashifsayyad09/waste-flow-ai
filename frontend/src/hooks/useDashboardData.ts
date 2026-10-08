import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import type { BinRow, CollectionPlan } from "../types";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; rows: BinRow[]; plan: CollectionPlan };

export function useDashboardData() {
  const [state, setState] = useState<State>({ status: "loading" });

  const load = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const [bins, priorities, plan] = await Promise.all([api.getBins(), api.getPriorities(), api.getCollectionPlan()]);
      const byId = new Map(bins.map((b) => [b.id, b]));
      const rows: BinRow[] = priorities.flatMap((priority) => {
        const bin = byId.get(priority.bin_id);
        return bin ? [{ bin, priority }] : [];
      });
      setState({ status: "ready", rows, plan });
    } catch (e) {
      setState({ status: "error", message: e instanceof Error ? e.message : "Something went wrong loading the dashboard." });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, reload: load };
}
