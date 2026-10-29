import { useEffect, useState } from "react";
import { CampaignStatus } from "./components/CampaignStatus";
import { AgentDock } from "./components/Copilot";
import { ProjectProvider, useProject } from "./context";
import { Agent } from "./pages/Agent";
import { Planner } from "./pages/Planner";
import { Review } from "./pages/Review";
import { badgeClass, routeFromHash } from "./util";

function Shell() {
  const { project, status } = useProject();
  const [route, setRoute] = useState<"plan" | "review" | "agent">(routeFromHash());

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash) window.location.hash = "#/agent";
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const inference = project?.inference;
  const isAgent = route === "agent";

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to campaign workspace
      </a>
      <header className="top">
        <div className="brand">
          <h1>Jupiter</h1>
          <p>
            Autonomous campaign agent. NVIDIA Nemotron on Nebius Token Factory calls tools; a
            Gaussian process ranks the next processing runs. It never invents lab results.
          </p>
          <nav className="tabs" aria-label="Campaign workspace">
            <a
              className={route === "agent" ? "tab active" : "tab"}
              href="#/agent"
              aria-current={route === "agent" ? "page" : undefined}
            >
              Agent
            </a>
            <a
              className={route === "plan" ? "tab active" : "tab"}
              href="#/plan"
              aria-current={route === "plan" ? "page" : undefined}
            >
              Plan
            </a>
            <a
              className={route === "review" ? "tab active" : "tab"}
              href="#/review"
              aria-current={route === "review" ? "page" : undefined}
            >
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
        physics. The agent runs tools; you still type furnace measurements on Plan.
      </div>

      <CampaignStatus busy={status.kind === "loading"} />

      {status.kind !== "idle" && (
        <div className={`status ${status.kind}`} role="status" aria-live="polite">
          {status.text}
        </div>
      )}

      <div className={isAgent ? "workspace agent-layout" : "workspace"}>
        <main id="main" className="workspace-main" tabIndex={-1}>
          {route === "review" ? <Review /> : route === "agent" ? <Agent /> : <Planner />}
        </main>
        {!isAgent && <AgentDock />}
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
