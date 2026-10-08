export type PriorityLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type WasteType = "organic" | "plastic" | "paper" | "glass" | "mixed";

export interface Bin {
  id: string;
  name: string;
  location: string;
  latitude: number;
  longitude: number;
  fill_level: number;
  waste_type: WasteType;
  last_collected: string;
  days_since_collection: number;
  temperature: number;
  estimated_overflow_time: number;
  status: "normal" | "warning" | "critical";
}

export interface FactorScore {
  factor: string;
  points: number;
  max_points: number;
}

export interface PriorityResult {
  bin_id: string;
  priority_score: number;
  priority_level: PriorityLevel;
  reasons: string[];
  breakdown: FactorScore[];
}

export interface CollectionStep {
  rank: number;
  bin_id: string;
  bin_name: string;
  location: string;
  priority_score: number;
  priority_level: PriorityLevel;
  reason: string;
}

export interface CollectionPlan {
  generated_at: string;
  total_bins: number;
  collection_order: CollectionStep[];
}

/** A bin joined with its priority result — what the UI mostly works with. */
export interface BinRow {
  bin: Bin;
  priority: PriorityResult;
}
