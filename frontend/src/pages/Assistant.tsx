import { useState } from "react";
import { PriorityBadge, StateMessage } from "../components/ui";
import { api, ApiError } from "../services/api";
import type { ChatResponse, DataStatus } from "../types";

const EXAMPLES = [
  "Which three bins should we collect first today?",
  "Why is BIN-004 critical?",
  "Which bins may overflow soon?",
  "Summarize today's collection priorities.",
  "Which bins contain organic waste and have high priority?",
  "Explain the recommended collection order in simple language.",
];

const STATUS_LABEL: Record<DataStatus, string> = {
  verified: "Verified against live bin data",
  partial: "Partly verified: some data could not be confirmed",
  no_data_used: "No bin data was used for this answer",
  unavailable: "Could not verify: the data service is unavailable",
};

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; response: ChatResponse };

interface Props {
  onSelectBin?: (id: string) => void;
}

export function Assistant({ onSelectBin }: Props) {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [state, setState] = useState<State>({ status: "idle" });

  async function ask(text: string) {
    const q = text.trim();
    if (!q || state.status === "loading") return;
    setAsked(q);
    setState({ status: "loading" });
    try {
      setState({ status: "done", response: await api.chat(q) });
    } catch (e) {
      setState({ status: "error", message: e instanceof ApiError ? e.message : "Something went wrong asking the assistant." });
    }
  }

  return (
    <section className="card" aria-labelledby="assistant-title">
      <h2 id="assistant-title">Ask about today's collection</h2>
      <p className="muted plan-note">
        Answers are written by AI but every bin, reading and score comes from the live database and the deterministic priority engine.
        The assistant explains the ranking; it never changes it.
      </p>

      <div className="chips" role="group" aria-label="Example questions">
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" className="chip" onClick={() => setQuestion(ex)}>{ex}</button>
        ))}
      </div>

      <div className="ai-form">
        <label htmlFor="assistant-question" className="muted">Your question</label>
        <textarea
          id="assistant-question" rows={3} maxLength={500} value={question} placeholder="e.g. Why is BIN-004 critical?"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void ask(question); } }}
        />
        <div className="ai-form-row">
          <span className="muted">{question.length}/500</span>
          <button type="button" className="btn btn-accent" disabled={!question.trim() || state.status === "loading"} onClick={() => void ask(question)}>
            Ask assistant
          </button>
        </div>
      </div>

      <div aria-live="polite" className="ai-output">
        {state.status === "loading" && <StateMessage kind="loading" title="Checking live bin data…" />}
        {state.status === "error" && <StateMessage kind="error" title="The assistant could not answer" detail={state.message} onRetry={() => void ask(asked)} />}
        {state.status === "done" && <Answer response={state.response} question={asked} onSelectBin={onSelectBin} />}
      </div>
    </section>
  );
}

function Answer({ response, question, onSelectBin }: { response: ChatResponse; question: string; onSelectBin?: (id: string) => void }) {
  return (
    <div className="answer-block">
      <p className="muted">You asked: {question}</p>
      <p className="answer">{response.answer}</p>
      <p className={`data-status data-${response.data_status}`}>{STATUS_LABEL[response.data_status]}</p>
      {response.warnings.length > 0 && (
        <ul className="reasons">{response.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      )}
      {response.referenced_bins.length > 0 && (
        <>
          <h3>Bins referenced</h3>
          <ul className="list">
            {response.referenced_bins.map((b) => (
              <li key={b.bin_id}>
                {onSelectBin ? <button className="link" onClick={() => onSelectBin(b.bin_id)}>{b.bin_id}</button> : <span>{b.bin_id}</span>}
                <span className="row-meta">
                  {b.priority_level && <PriorityBadge level={b.priority_level} />}
                  {b.priority_score !== null && <span className="score-sm" aria-label={`Priority score ${b.priority_score}`}>{b.priority_score}</span>}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {response.tools_used.length > 0 && <p className="muted">Checked with: {response.tools_used.join(", ")}</p>}
    </div>
  );
}
