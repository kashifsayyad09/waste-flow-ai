import { useEffect, useRef, useState } from "react";
import { StateMessage } from "../components/ui";
import { api, ApiError } from "../services/api";
import type { ClassificationResult, WasteCategory } from "../types";

export const MAX_UPLOAD_BYTES = 3 * 1024 * 1024; // keep in sync with backend upload_max_bytes
const ALLOWED = ["image/jpeg", "image/png", "image/webp"];

const CATEGORY_LABEL: Record<WasteCategory, string> = {
  organic: "Organic", plastic: "Plastic", paper_cardboard: "Paper / cardboard", metal: "Metal", glass: "Glass",
  electronic: "Electronic waste", hazardous: "Hazardous waste", mixed: "Mixed waste", unknown: "Unknown / uncertain",
};

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; result: ClassificationResult };

export function WasteClassifier() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [state, setState] = useState<State>({ status: "idle" });
  const previewUrl = useRef<string | null>(null);

  useEffect(() => () => { if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); }, []);

  function choose(f: File | undefined) {
    if (previewUrl.current) { URL.revokeObjectURL(previewUrl.current); previewUrl.current = null; }
    setState({ status: "idle" });
    setFile(null);
    setPreview(null);
    setFileError(null);
    if (!f) return;
    if (!ALLOWED.includes(f.type)) return setFileError("Please choose a JPEG, PNG or WebP image.");
    if (f.size > MAX_UPLOAD_BYTES) return setFileError(`That image is larger than ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB. Please choose a smaller photo.`);
    previewUrl.current = URL.createObjectURL(f);
    setFile(f);
    setPreview(previewUrl.current);
  }

  async function submit() {
    if (!file || state.status === "loading") return;
    setState({ status: "loading" });
    try {
      setState({ status: "done", result: await api.classifyWaste(file) });
    } catch (e) {
      setState({ status: "error", message: e instanceof ApiError ? e.message : "Something went wrong classifying the photo." });
    }
  }

  return (
    <section className="card" aria-labelledby="classifier-title">
      <h2 id="classifier-title">Classify a waste photo</h2>
      <p className="muted plan-note">
        AI looks at one photo and suggests a waste category. It is an estimate, not a lab test, and it never changes any bin record.
        Photos are processed in memory and not stored.
      </p>

      <div className="file-row">
        <label className="btn btn-outline file-btn">
          Choose photo
          <input type="file" accept={ALLOWED.join(",")} className="visually-hidden" aria-label="Choose photo" onChange={(e) => choose(e.target.files?.[0])} />
        </label>
        <label className="btn btn-outline file-btn">
          Take photo
          <input type="file" accept="image/*" capture="environment" className="visually-hidden" aria-label="Take photo" onChange={(e) => choose(e.target.files?.[0])} />
        </label>
      </div>

      {fileError && <p role="alert" className="field-error">{fileError}</p>}

      {preview && file && (
        <div className="preview">
          <img src={preview} alt="Selected waste photo preview" />
          <p className="muted">{file.name} · {(file.size / 1024).toFixed(0)} KB</p>
          <button type="button" className="btn btn-accent" disabled={state.status === "loading"} onClick={() => void submit()}>Classify photo</button>
        </div>
      )}

      <div aria-live="polite" className="ai-output">
        {state.status === "loading" && <StateMessage kind="loading" title="Analysing photo…" />}
        {state.status === "error" && <StateMessage kind="error" title="Could not classify the photo" detail={state.message} onRetry={() => void submit()} />}
        {state.status === "done" && <Result result={state.result} />}
      </div>
    </section>
  );
}

function Result({ result }: { result: ClassificationResult }) {
  return (
    <div className="answer-block">
      <h3>Predicted category</h3>
      <p className="next-name">{CATEGORY_LABEL[result.category]}</p>
      <p className="muted">
        Confidence: {result.confidence === null ? "not provided (the AI provider gives no reliable score)" : `${Math.round(result.confidence * 100)}%`}
      </p>
      <p className="answer">{result.explanation}</p>
      <h3>Handling guidance</h3>
      <p className="answer">{result.handling_guidance}</p>
      <h3>Limitations</h3>
      <ul className="reasons">{result.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
    </div>
  );
}
