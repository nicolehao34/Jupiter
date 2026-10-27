import { useEffect, useState } from "react";
import { Copilot } from "./components/Copilot";
import { ProjectProvider, useProject } from "./context";
import { Planner } from "./pages/Planner";
import { Review } from "./pages/Review";
import { badgeClass, routeFromHash } from "./util";

function Shell() {
  const { project, status } = useProject();
  const [route, setRoute] = useState<"plan" | "review">(routeFromHash());

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash) window.location.hash = "#/plan";
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const inference = project?.inference;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <h1>Jupiter</h1>
          <p>
            Plan the next processing runs, then review the same campaign. Ranking is a Gaussian
            process; the copilot only explains stored numbers via NVIDIA Nemotron on Nebius Token
            Factory.
          </p>
          <nav className="tabs">
            <a className={route === "plan" ? "tab active" : "tab"} href="#/plan">
              Plan
            </a>
            <a className={route === "review" ? "tab active" : "tab"} href="#/review">
              Review
            </a>
          </nav>
        </div>
        <div className="badge-row">
          {inference && (
            <span className={badgeClass(inference.mode)} title={inference.message}>
              {inference.mode === "live"
                ? `Live Nemotron · ${inference.model}`
                : inference.mode === "offline_demo"
                  ? "Offline demo — not live Nebius"
                  : "Nemotron unconfigured"}
            </span>
          )}
          <span className="badge">Best Apps & Agents · Nebius × NVIDIA</span>
        </div>
      </header>

      <div className="disclaimer">
        Demonstration scenario: fixed NMC811 cathode ({project?.sample_metadata.composition}). The
        bundled table is a <strong>synthetic demonstration dataset</strong> — not real battery
        physics. Plan writes the campaign; Review and Copilot only read it.
      </div>

      {status.kind !== "idle" && <div className={`status ${status.kind}`}>{status.text}</div>}

      <div className="workspace">
        <main className="workspace-main">{route === "review" ? <Review /> : <Planner />}</main>
        <Copilot />
      </div>
    </div>
  );
}

export function App() {
  return (
    <ProjectProvider>
      <Shell />
    </ProjectProvider>
  );
}
