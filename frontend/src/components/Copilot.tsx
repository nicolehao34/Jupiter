import { useState } from "react";
import { api } from "../api";
import { useProject } from "../context";
import type { AskReply } from "../types";

interface Turn {
  role: "user" | "assistant";
  text: string;
  bullets?: string[];
  inference?: AskReply["inference"];
}

const STARTERS = [
  "What is the best observed capacity so far, and from which source?",
  "How much of the experiment budget is left?",
  "What is the surrogate EI lift versus the space-filling baseline?",
  "What setpoints are on the latest lab run sheet?",
];

export function AskPanel() {
  const { project } = useProject();
  const [question, setQuestion] = useState(STARTERS[0]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send(text: string) {
    if (!project || !text.trim()) return;
    setBusy(true);
    setError("");
    setTurns((prev) => [...prev, { role: "user", text }]);
    try {
      const reply = await api.ask(project.id, text.trim());
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          text: reply.answer,
          bullets: reply.bullets,
          inference: reply.inference,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Ask about this campaign</h2>
      <p className="hint">
        Optional. After the agent has run, Nemotron may only restate stored facts. It still will not
        invent predictions. Use <strong>Run campaign</strong> above to act.
      </p>
      <div className="starter-row">
        {STARTERS.map((item) => (
          <button key={item} className="secondary chip-btn" type="button" onClick={() => setQuestion(item)}>
            {item}
          </button>
        ))}
      </div>
      <div className="transcript">
        {turns.length === 0 && <p className="meta">No questions yet.</p>}
        {turns.map((turn, i) => (
          <div key={i} className={`bubble ${turn.role}`}>
            <p>{turn.text}</p>
            {turn.bullets?.map((b, j) => (
              <p key={j} className="meta">
                • {b}
              </p>
            ))}
            {turn.inference && (
              <p className={`meta infer ${turn.inference.mode}`}>
                {turn.inference.mode}
                {turn.inference.model ? ` · ${turn.inference.model}` : ""}
                {turn.inference.latency_ms != null ? ` · ${turn.inference.latency_ms} ms` : ""}
                {turn.inference.error ? ` · ${turn.inference.error}` : ""}
              </p>
            )}
          </div>
        ))}
      </div>
      {error && <div className="status error">{error}</div>}
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask about budget, best so far, or the last batch…"
      />
      <div className="actions">
        <button className="secondary" disabled={busy || !project} onClick={() => void send(question)}>
          {busy ? "Asking…" : "Ask"}
        </button>
      </div>
    </section>
  );
}

export function AgentDock() {
  return (
    <aside className="copilot card">
      <h2>Agent</h2>
      <p className="hint">
        The campaign agent owns the loop. Plan and Review only inspect the same SQLite campaign.
      </p>
      <div className="actions">
        <a className="tab active" href="#/agent">
          Open agent
        </a>
      </div>
      <p className="meta">Ranking stays a Gaussian process. The agent cannot record furnace results.</p>
    </aside>
  );
}
