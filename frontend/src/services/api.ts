import type { Bin, CollectionPlan, PriorityResult } from "../types";

/**
 * Single place to change where the API lives.
 * Same-origin path: requests go through Nginx (http://localhost/api/...),
 * or through the Vite dev proxy to Nginx when using http://localhost:5173.
 */
export const API_BASE_PATH = "/api/v1";

export class ApiError extends Error {}

const UNREACHABLE =
  "Cannot reach the API. Check that FastAPI is running on 127.0.0.1:8000 and Nginx is running on port 80 (see nginx/README.md).";

async function get<T>(path: string, isValid: (data: unknown) => boolean): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_PATH}${path}`);
  } catch {
    throw new ApiError(UNREACHABLE);
  }
  // 5xx from Nginx/Vite proxy means the upstream is down.
  if (res.status >= 500) throw new ApiError(`${UNREACHABLE} (HTTP ${res.status})`);
  if (!res.ok) throw new ApiError(`The server answered ${res.status} for ${path}.`);
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    throw new ApiError(`The response for ${path} was not valid JSON.`);
  }
  if (!isValid(data)) throw new ApiError(`The response for ${path} had an unexpected shape.`);
  return data as T;
}

const isObject = (d: unknown): d is Record<string, unknown> => typeof d === "object" && d !== null;

export const api = {
  getBins: () => get<Bin[]>("/bins", Array.isArray),
  getBin: (id: string) => get<Bin>(`/bins/${encodeURIComponent(id)}`, (d) => isObject(d) && "id" in d),
  getPriorities: () => get<PriorityResult[]>("/priorities", Array.isArray),
  getCollectionPlan: () =>
    get<CollectionPlan>("/collection-plan", (d) => isObject(d) && Array.isArray(d.collection_order)),
};
