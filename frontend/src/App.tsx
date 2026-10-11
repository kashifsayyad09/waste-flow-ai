import { useState } from "react";
import { StateMessage } from "./components/ui";
import { useDashboardData } from "./hooks/useDashboardData";
import { BinDetails } from "./pages/BinDetails";
import { CollectionPlan } from "./pages/CollectionPlan";
import { Assistant } from "./pages/Assistant";
import { Overview } from "./pages/Overview";
import { PriorityBins } from "./pages/PriorityBins";
import { WasteClassifier } from "./pages/WasteClassifier";

type Section = "overview" | "priorities" | "plan" | "assistant" | "classifier";

const SECTIONS: { id: Section; label: string; title: string }[] = [
  { id: "overview", label: "Overview", title: "Today's collection picture" },
  { id: "priorities", label: "Priority bins", title: "Bins by priority" },
  { id: "plan", label: "Collection plan", title: "Collection plan" },
  { id: "assistant", label: "AI assistant", title: "AI collection assistant" },
  { id: "classifier", label: "Waste photo", title: "Waste photo classifier" },
];

export default function App() {
  const { state, reload } = useDashboardData();
  const [section, setSection] = useState<Section>("overview");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const go = (s: Section) => {
    setSelectedId(null);
    setSection(s);
  };
  const isAi = section === "assistant" || section === "classifier";
  const title = selectedId ? "Bin details" : SECTIONS.find((s) => s.id === section)!.title;

  return (
    <div className="shell">
      <aside className="side">
        <p className="brand">WasteFlow AI</p>
        <p className="muted tagline">From waste data to the next collection decision.</p>
        <nav aria-label="Main">
          {SECTIONS.map((s) => (
            <button key={s.id} className="nav-item" aria-current={!selectedId && section === s.id ? "page" : undefined} onClick={() => go(s.id)}>
              {s.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <h1>{title}</h1>
          <button className="btn btn-outline" onClick={reload} disabled={state.status === "loading"}>Refresh data</button>
        </header>

        {/* AI pages stay mounted (hidden while a bin is open) so an answer isn't lost, and work even if the dashboard data failed to load. */}
        {section === "assistant" && (
          <div hidden={!!selectedId}><Assistant onSelectBin={state.status === "ready" ? setSelectedId : undefined} /></div>
        )}
        {section === "classifier" && <div hidden={!!selectedId}><WasteClassifier /></div>}

        {(!isAi || selectedId) && state.status === "loading" && <StateMessage kind="loading" title="Loading bin data…" />}
        {(!isAi || selectedId) && state.status === "error" && <StateMessage kind="error" title="Could not load the dashboard" detail={state.message} onRetry={reload} />}
        {(!isAi || selectedId) && state.status === "ready" && (
          selectedId ? (
            <BinDetails row={state.rows.find((r) => r.bin.id === selectedId)} onBack={() => setSelectedId(null)} />
          ) : section === "overview" ? (
            <Overview rows={state.rows} onSelect={setSelectedId} />
          ) : section === "priorities" ? (
            <PriorityBins rows={state.rows} onSelect={setSelectedId} />
          ) : (
            <CollectionPlan plan={state.plan} onSelect={setSelectedId} />
          )
        )}
      </main>
    </div>
  );
}
