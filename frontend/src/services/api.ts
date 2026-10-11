import type { Bin, ChatResponse, ClassificationResult, CollectionPlan, CollectionRecord, PriorityResult } from "../types";

/**
 * Single place to change where the API lives.
 * Always a same-origin path, never a host: the browser calls the frontend's own origin.
 *  - Production: the frontend Nginx forwards /api/ to the backend EC2 (see deploy/).
 *  - Local dev:  the Vite dev proxy forwards /api/ to FastAPI on 127.0.0.1:8000.
 */
export const API_BASE_PATH = "/api/v1";

export class ApiError extends Error {
  constructor(message: string, readonly code?: string, readonly status?: number) {
    super(message);
  }
}

const UNREACHABLE =
  "Cannot reach the API. Check that the backend is running and that Nginx (or the Vite dev proxy) can reach it.";

async function get<T>(path: string, isValid: (data: unknown) => boolean): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_PATH}${path}`);
  } catch {
    throw new ApiError(UNREACHABLE);
  }
  if (res.status === 503) {
    // FastAPI is up but its database is not (it never reveals connection details).
    const body = await res.json().catch(() => null);
    if (isObject(body) && body.detail === "Database unavailable")
      throw new ApiError("The API is running but cannot reach its database. Check the RDS instance, its security group and backend/.env.");
  }
  // Other 5xx from Nginx/Vite proxy means the upstream is down.
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

/** POST helper for the AI endpoints. The server returns {detail: {code, message}} with user-safe text. */
async function post<T>(path: string, init: RequestInit, isValid: (data: unknown) => boolean): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_PATH}${path}`, { method: "POST", ...init });
  } catch {
    throw new ApiError(UNREACHABLE);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = isObject(body) ? body.detail : undefined;
    if (isObject(detail) && typeof detail.message === "string")
      throw new ApiError(detail.message, typeof detail.code === "string" ? detail.code : undefined, res.status);
    if (res.status === 413) throw new ApiError("The upload is too large for the server.", "image_too_large", 413);
    if (res.status === 422) throw new ApiError("The request was not valid. Please check your input.", "validation", 422);
    if (res.status >= 500) throw new ApiError(`${UNREACHABLE} (HTTP ${res.status})`, undefined, res.status);
    throw new ApiError(`The server answered ${res.status}.`, undefined, res.status);
  }
  const data: unknown = await res.json().catch(() => null);
  if (!isValid(data)) throw new ApiError("The server's response had an unexpected shape.");
  return data as T;
}

const isObject = (d: unknown): d is Record<string, unknown> => typeof d === "object" && d !== null;

export const api = {
  chat: (message: string) =>
    post<ChatResponse>("/ai/chat", { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) },
      (d) => isObject(d) && typeof d.answer === "string" && Array.isArray(d.referenced_bins)),
  classifyWaste: (file: File) => {
    const form = new FormData();
    form.append("image", file);
    return post<ClassificationResult>("/ai/classify-waste", { body: form }, (d) => isObject(d) && typeof d.category === "string");
  },
  getBins: () => get<Bin[]>("/bins", Array.isArray),
  getBin: (id: string) => get<Bin>(`/bins/${encodeURIComponent(id)}`, (d) => isObject(d) && "id" in d),
  getCollections: (binId: string, limit = 10) =>
    get<CollectionRecord[]>(`/collections?bin_id=${encodeURIComponent(binId)}&limit=${limit}`, Array.isArray),
  getPriorities: () => get<PriorityResult[]>("/priorities", Array.isArray),
  getCollectionPlan: () =>
    get<CollectionPlan>("/collection-plan", (d) => isObject(d) && Array.isArray(d.collection_order)),
};
