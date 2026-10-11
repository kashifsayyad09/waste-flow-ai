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

export interface CollectionRecord {
  id: number;
  bin_id: string;
  collected_at: string;
  collection_status: "completed" | "skipped" | "failed";
  notes: string | null;
  created_at: string;
}

export type DataStatus = "verified" | "partial" | "no_data_used" | "unavailable";

export interface ReferencedBin {
  bin_id: string;
  priority_score: number | null;
  priority_level: PriorityLevel | null;
}

export interface ChatResponse {
  status: "ok" | "unavailable";
  answer: string;
  referenced_bins: ReferencedBin[];
  tools_used: string[];
  data_status: DataStatus;
  warnings: string[];
  model: string | null;
}

export type WasteCategory =
  | "organic" | "plastic" | "paper_cardboard" | "metal" | "glass" | "electronic" | "hazardous" | "mixed" | "unknown";

export interface ClassificationResult {
  category: WasteCategory;
  confidence: number | null;
  explanation: string;
  handling_guidance: string;
  limitations: string[];
}
