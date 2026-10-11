import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { Assistant } from "../pages/Assistant";
import { MAX_UPLOAD_BYTES, WasteClassifier } from "../pages/WasteClassifier";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const chatResponse = {
  status: "ok", answer: "Collect BIN-004 first (score 97), then BIN-001.", tools_used: ["get_critical_bins"], data_status: "verified",
  warnings: [], model: "m",
  referenced_bins: [
    { bin_id: "BIN-004", priority_score: 97, priority_level: "CRITICAL" },
    { bin_id: "BIN-001", priority_score: 86, priority_level: "CRITICAL" },
  ],
};
const classification = {
  category: "organic", confidence: null, explanation: "Food scraps are visible.",
  handling_guidance: "Keep organic waste separate from dry recyclables.", limitations: ["This is an AI estimate from one photo and can be wrong."],
};

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("AI assistant", () => {
  it("disables submit until there is a question and fills the box from an example chip", () => {
    render(<Assistant />);
    const ask = screen.getByRole("button", { name: "Ask assistant" });
    expect(ask).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Why is BIN-004 critical?" }));
    expect(screen.getByLabelText("Your question")).toHaveValue("Why is BIN-004 critical?");
    expect(ask).toBeEnabled();
  });

  it("posts to the same-origin API, shows loading, then the answer with referenced bins and scores", async () => {
    let release!: () => void;
    const fetchMock = vi.fn(() => new Promise<Response>((res) => { release = () => res(json(chatResponse)); }));
    vi.stubGlobal("fetch", fetchMock);
    const onSelect = vi.fn();
    render(<Assistant onSelectBin={onSelect} />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "Which bins are critical?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask assistant" }));

    expect(await screen.findByText("Checking live bin data…")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/ai/chat");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ message: "Which bins are critical?" });

    release();
    expect(await screen.findByText(/Collect BIN-004 first/)).toBeInTheDocument();
    expect(screen.getByText("Verified against live bin data")).toBeInTheDocument();
    const list = within(screen.getByText("Bins referenced").parentElement!).getAllByRole("listitem");
    expect(list[0]).toHaveTextContent("BIN-004");
    expect(list[0]).toHaveTextContent("97");
    expect(list[0]).toHaveTextContent("Critical");
    fireEvent.click(within(list[1]).getByRole("button", { name: "BIN-001" }));
    expect(onSelect).toHaveBeenCalledWith("BIN-001");
  });

  it("marks unverified answers and shows warnings", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ ...chatResponse, data_status: "partial", warnings: ["Some data could not be verified."], referenced_bins: [] })));
    render(<Assistant />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "q" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask assistant" }));
    expect(await screen.findByText(/Partly verified/)).toBeInTheDocument();
    expect(screen.getByText("Some data could not be verified.")).toBeInTheDocument();
    expect(screen.queryByText("Bins referenced")).not.toBeInTheDocument();
  });

  it("shows the server's safe error message and retries the same question", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ detail: { code: "ai_rate_limited", message: "The AI provider rate limit was reached. Please wait a moment and try again." } }, 429))
      .mockResolvedValueOnce(json(chatResponse));
    vi.stubGlobal("fetch", fetchMock);
    render(<Assistant />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "Summarize" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask assistant" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("rate limit was reached");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/Collect BIN-004 first/)).toBeInTheDocument();
    expect(JSON.parse((fetchMock.mock.calls[1] as unknown as [string, RequestInit])[1].body as string)).toEqual({ message: "Summarize" });
  });

  it("explains 'not configured' and unreachable backends", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: { code: "ai_not_configured", message: "The Groq text model (GROQ_API_KEY / GROQ_TEXT_MODEL) is not configured on the server." } }, 503)));
    render(<Assistant />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "q" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask assistant" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("is not configured on the server");
    cleanup();
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    render(<Assistant />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "q" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask assistant" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the API");
  });
});

describe("waste photo classifier", () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:preview");
    URL.revokeObjectURL = vi.fn();
  });

  const pick = (file: File, label = "Choose photo") => fireEvent.change(screen.getByLabelText(label), { target: { files: [file] } });
  const image = (type = "image/jpeg", name = "bin.jpg") => new File(["x"], name, { type });

  it("rejects unsupported types and oversized files in the browser, without calling the API", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<WasteClassifier />);
    pick(image("image/gif", "a.gif"));
    expect(screen.getByRole("alert")).toHaveTextContent("JPEG, PNG or WebP");
    const big = image();
    Object.defineProperty(big, "size", { value: MAX_UPLOAD_BYTES + 1 });
    pick(big);
    expect(screen.getByRole("alert")).toHaveTextContent("larger than 3 MB");
    expect(screen.queryByRole("button", { name: "Classify photo" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("previews the photo, uploads it as multipart 'image', and shows category, guidance and limitations", async () => {
    const fetchMock = vi.fn(async () => json(classification));
    vi.stubGlobal("fetch", fetchMock);
    render(<WasteClassifier />);
    const file = image("image/png", "scraps.png");
    pick(file);
    expect(screen.getByAltText("Selected waste photo preview")).toHaveAttribute("src", "blob:preview");
    fireEvent.click(screen.getByRole("button", { name: "Classify photo" }));
    expect(await screen.findByText("Predicted category")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/ai/classify-waste");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("image")).toBe(file);
    expect((init.headers as unknown) ?? undefined).toBeUndefined(); // browser sets the multipart boundary itself
    expect(screen.getByText("Organic")).toBeInTheDocument();
    expect(screen.getByText(/Confidence: not provided/)).toBeInTheDocument();
    expect(screen.getByText("Food scraps are visible.")).toBeInTheDocument();
    expect(screen.getByText("Keep organic waste separate from dry recyclables.")).toBeInTheDocument();
    expect(screen.getByText(/can be wrong/)).toBeInTheDocument();
  });

  it("only shows a confidence figure when the API actually provides one", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ ...classification, confidence: 0.82 })));
    render(<WasteClassifier />);
    pick(image());
    fireEvent.click(screen.getByRole("button", { name: "Classify photo" }));
    expect(await screen.findByText("Confidence: 82%")).toBeInTheDocument();
  });

  it("shows provider/validation errors and allows retry", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ detail: { code: "ai_model_unsupported", message: "The configured AI model is unavailable or does not support this request. Contact the administrator." } }, 502))
      .mockResolvedValueOnce(json(classification));
    vi.stubGlobal("fetch", fetchMock);
    render(<WasteClassifier />);
    pick(image());
    fireEvent.click(screen.getByRole("button", { name: "Classify photo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("does not support this request");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Predicted category")).toBeInTheDocument();
  });

  it("maps a proxy 413 (HTML body) to a readable message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>413</html>", { status: 413 })));
    render(<WasteClassifier />);
    pick(image());
    fireEvent.click(screen.getByRole("button", { name: "Classify photo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("too large");
  });
});

describe("navigation", () => {
  it("AI pages work even when the dashboard data failed to load", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    render(<App />);
    expect(await screen.findByText("Could not load the dashboard")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "AI assistant" }));
    expect(screen.getByLabelText("Your question")).toBeInTheDocument();
    expect(screen.queryByText("Could not load the dashboard")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Waste photo" }));
    expect(screen.getByText("Classify a waste photo")).toBeInTheDocument();
  });

  it("clicking a referenced bin opens its details, and Back returns to the assistant with the answer intact", async () => {
    const bins = [{ id: "BIN-004", name: "Begum Bazaar Bin", location: "Begum Bazaar", latitude: 17.37, longitude: 78.473, fill_level: 97, waste_type: "organic",
      last_collected: "2026-10-07T08:00:00Z", days_since_collection: 3, temperature: 37, estimated_overflow_time: 2, status: "critical" }];
    const priorities = [{ bin_id: "BIN-004", priority_score: 97, priority_level: "CRITICAL", reasons: ["97% full"], breakdown: [{ factor: "Fill level", points: 40, max_points: 45 }] }];
    const plan = { generated_at: "2026-10-10T09:00:00Z", total_bins: 1, collection_order: [{ rank: 1, bin_id: "BIN-004", bin_name: "x", location: "Begum Bazaar", priority_score: 97, priority_level: "CRITICAL", reason: "97% full" }] };
    vi.stubGlobal("fetch", vi.fn(async (input: string) => {
      if (input.startsWith("/api/v1/ai/chat")) return json({ ...chatResponse, referenced_bins: [chatResponse.referenced_bins[0]] });
      if (input.startsWith("/api/v1/bins")) return json(bins);
      if (input.startsWith("/api/v1/priorities")) return json(priorities);
      if (input.startsWith("/api/v1/collection-plan")) return json(plan);
      if (input.startsWith("/api/v1/collections")) return json([]);
      return json({}, 404);
    }));
    render(<App />);
    await screen.findByText("Collect next");
    fireEvent.click(screen.getByRole("button", { name: "AI assistant" }));
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "critical?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask assistant" }));
    await screen.findByText(/Collect BIN-004 first/);
    fireEvent.click(screen.getByRole("button", { name: "BIN-004" }));
    expect(await screen.findByText("Bin information")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    await waitFor(() => expect(screen.getByText(/Collect BIN-004 first/)).toBeVisible());
  });
});
