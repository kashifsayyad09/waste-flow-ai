/**
 * UI tests. Default mode uses fixture responses shaped like the real API.
 * Live mode runs the same assertions against the real, database-backed backend:
 *   WASTEFLOW_LIVE_API=http://127.0.0.1:8000 npm test
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const LIVE = process.env.WASTEFLOW_LIVE_API;

const bins = [
  { id: "BIN-A", name: "Alpha Bin", location: "Alpha Street", latitude: 17.3616, longitude: 78.4747, fill_level: 95, waste_type: "organic",
    last_collected: "2026-10-07T08:00:00Z", days_since_collection: 3, temperature: 37, estimated_overflow_time: 2, status: "critical" },
  { id: "BIN-B", name: "Beta Bin", location: "Beta Road", latitude: 17.44, longitude: 78.37, fill_level: 60, waste_type: "mixed",
    last_collected: "2026-10-09T08:00:00Z", days_since_collection: 1, temperature: 31, estimated_overflow_time: 14, status: "normal" },
  { id: "BIN-C", name: "Gamma Bin", location: "Gamma Lane", latitude: 17.41, longitude: 78.44, fill_level: 20, waste_type: "glass",
    last_collected: "2026-10-10T08:00:00Z", days_since_collection: 0, temperature: 25, estimated_overflow_time: 70, status: "normal" },
];
const factors = (p: number) => [{ factor: "Fill level", points: p, max_points: 45 }];
const priorities = [
  { bin_id: "BIN-A", priority_score: 93, priority_level: "CRITICAL", reasons: ["95% full", "Organic waste"], breakdown: factors(40) },
  { bin_id: "BIN-B", priority_score: 45, priority_level: "MEDIUM", reasons: ["60% full"], breakdown: factors(14) },
  { bin_id: "BIN-C", priority_score: 6, priority_level: "LOW", reasons: [], breakdown: factors(1) },
];
const plan = {
  generated_at: "2026-10-10T09:00:00Z", total_bins: 3,
  collection_order: priorities.map((p, i) => ({
    rank: i + 1, bin_id: p.bin_id, bin_name: bins[i].name, location: bins[i].location,
    priority_score: p.priority_score, priority_level: p.priority_level, reason: p.reasons.join(", ") || "Low urgency across all factors",
  })),
};
const history = [{ id: 1, bin_id: "BIN-A", collected_at: "2026-10-07T08:00:00Z", collection_status: "completed", notes: "Seed data", created_at: "2026-10-07T08:00:01Z" }];

type Route = unknown | (() => Response | Promise<Response>);
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mockApi(overrides: Record<string, Route> = {}) {
  const routes: Record<string, Route> = {
    "/api/v1/bins": bins, "/api/v1/priorities": priorities, "/api/v1/collection-plan": plan, "/api/v1/collections": history, ...overrides,
  };
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    calls.push(input);
    const key = Object.keys(routes).find((k) => input === k || input.startsWith(k + "?"));
    if (!key) return json({ detail: "not found" }, 404);
    const r = routes[key];
    return typeof r === "function" ? (r as () => Response | Promise<Response>)() : json(r);
  }));
  return calls;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe.skipIf(!!LIVE)("dashboard (fixture API)", () => {
  it("calls only same-origin /api paths (no hardcoded host)", async () => {
    const calls = mockApi();
    render(<App />);
    await screen.findByText("Collect next");
    expect(calls.length).toBeGreaterThan(0);
    for (const c of calls) expect(c).toMatch(/^\/api\/v1\//);
  });

  it("shows a loading state, then the overview computed from API data", async () => {
    mockApi();
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading bin data");
    await screen.findByText("Collect next");
    const stats = screen.getByLabelText("Fleet summary");
    const stat = (label: string) => within(stats).getByText(label).parentElement!.textContent;
    expect(stat("Total bins")).toContain("3");
    expect(stat("Critical bins")).toContain("1");
    expect(stat("High priority bins")).toContain("0");
    expect(stat("Average fill level")).toContain("58%"); // (95+60+20)/3
    expect(stat("Need immediate collection")).toContain("1");
    expect(screen.getByText("Alpha Bin")).toBeInTheDocument();
  });

  it("shows an error state with retry when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the API");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("explains a database outage (503) instead of blaming the network", async () => {
    mockApi({ "/api/v1/bins": () => json({ detail: "Database unavailable" }, 503) });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("cannot reach its database");
  });

  it("shows an empty state when there are no bins", async () => {
    mockApi({ "/api/v1/bins": [], "/api/v1/priorities": [], "/api/v1/collection-plan": { ...plan, total_bins: 0, collection_order: [] } });
    render(<App />);
    expect(await screen.findByText("No bins yet")).toBeInTheDocument();
  });

  it("rejects a malformed response instead of crashing", async () => {
    mockApi({ "/api/v1/priorities": { not: "an array" } });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("unexpected shape");
  });

  it("priority page lists bins in API order with score, level and main reason", async () => {
    mockApi();
    render(<App />);
    await screen.findByText("Collect next");
    fireEvent.click(screen.getByRole("button", { name: "Priority bins" }));
    const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[0].textContent)).toEqual(["BIN-A", "BIN-B", "BIN-C"]);
    expect(rows[0]).toHaveTextContent("93");
    expect(rows[0]).toHaveTextContent("Critical");
    expect(rows[0]).toHaveTextContent("95% full");
    expect(rows[2]).toHaveTextContent("No urgent factors"); // empty reasons handled
  });

  it("collection plan shows rank, level, score and the reason for each position", async () => {
    mockApi();
    render(<App />);
    await screen.findByText("Collect next");
    fireEvent.click(screen.getByRole("button", { name: "Collection plan" }));
    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("BIN-A");
    expect(items[0]).toHaveTextContent("93");
    expect(items[0]).toHaveTextContent("95% full, Organic waste");
    expect(items[1]).toHaveTextContent("Medium");
  });

  it("bin details match the API and show collection history", async () => {
    const calls = mockApi();
    render(<App />);
    await screen.findByText("Collect next");
    fireEvent.click(screen.getByRole("button", { name: "Priority bins" }));
    fireEvent.click(screen.getByRole("button", { name: "BIN-A" }));
    const info = (await screen.findByText("Bin information")).closest("section")!;
    expect(info).toHaveTextContent("Alpha Street");
    expect(info).toHaveTextContent("17.3616, 78.4747");
    expect(info).toHaveTextContent("37°C");
    expect(info).toHaveTextContent("in 2 hours");
    expect(info).toHaveTextContent("Organic");
    expect(screen.getByText("Why this score").closest("section")).toHaveTextContent("Organic waste");
    expect(await screen.findByText(/Seed data/)).toBeInTheDocument();
    expect(calls.some((c) => c.startsWith("/api/v1/collections?bin_id=BIN-A"))).toBe(true);
  });

  it("bin details handle empty and failed history", async () => {
    mockApi({ "/api/v1/collections": [] });
    render(<App />);
    await screen.findByText("Collect next");
    fireEvent.click(screen.getByRole("button", { name: "Inspect this bin" }));
    expect(await screen.findByText("No collections recorded for this bin yet.")).toBeInTheDocument();
    cleanup();
    mockApi({ "/api/v1/collections": () => json({ detail: "Database unavailable" }, 503) });
    render(<App />);
    await screen.findByText("Collect next");
    fireEvent.click(screen.getByRole("button", { name: "Inspect this bin" }));
    await waitFor(() => expect(screen.getAllByRole("alert").length).toBeGreaterThan(0));
  });
});

describe.runIf(!!LIVE)("dashboard against the LIVE database-backed API", () => {
  beforeEach(() => {
    const real = globalThis.fetch;
    vi.stubGlobal("fetch", (input: string) => real(`${LIVE}${input}`));
  });

  it("every value the UI shows equals what the API returned", async () => {
    const [liveBins, livePriorities, livePlan] = await Promise.all(
      ["/api/v1/bins", "/api/v1/priorities", "/api/v1/collection-plan"].map((p) => fetch(p).then((r) => r.json())),
    );
    render(<App />);
    await screen.findByText("Collect next");
    const stats = screen.getByLabelText("Fleet summary");
    const stat = (label: string) => within(stats).getByText(label).parentElement!.textContent;
    const count = (lv: string) => livePriorities.filter((p: { priority_level: string }) => p.priority_level === lv).length;
    expect(stat("Total bins")).toContain(String(liveBins.length));
    expect(stat("Critical bins")).toContain(String(count("CRITICAL")));
    expect(stat("High priority bins")).toContain(String(count("HIGH")));
    const avg = Math.round(liveBins.reduce((s: number, b: { fill_level: number }) => s + b.fill_level, 0) / liveBins.length);
    expect(stat("Average fill level")).toContain(`${avg}%`);

    fireEvent.click(screen.getByRole("button", { name: "Priority bins" }));
    const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[0].textContent)).toEqual(livePriorities.map((p: { bin_id: string }) => p.bin_id));
    rows.forEach((r, i) => expect(r).toHaveTextContent(String(livePriorities[i].priority_score)));

    fireEvent.click(screen.getByRole("button", { name: "Collection plan" }));
    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toHaveLength(livePlan.collection_order.length);
    items.forEach((li, i) => {
      expect(li).toHaveTextContent(livePlan.collection_order[i].bin_id);
      expect(li).toHaveTextContent(livePlan.collection_order[i].reason);
    });
  });
});
