# Demo script (≤ 3 minutes)

Goal: show the **autonomous agent** making **live Nebius / NVIDIA Nemotron tool calls**, and that ranking is still a Gaussian process. Record at 1080p. No copyrighted music.

**Prep (not in the video).** `cp .env.example .env`, paste `NEBIUS_API_KEY`, confirm `/api/inference/status` returns `"mode": "live"`. Start the app (`README` commands). Do not use offline demo mode for the recorded run.

| Time | Say | Show |
| --- | --- | --- |
| 0:00–0:20 | “Jupiter is a campaign agent for a **fixed NMC811 cathode**. Nemotron on Token Factory calls tools. Ranking is a Gaussian process — the model never invents μ, σ, or EI.” | Landing **Agent** workspace (not a copilot sidebar). Point at **Live Nemotron**. |
| 0:20–0:55 | “I give it the goal. It inspects the campaign, loads the labeled demo if needed, proposes a config, and generates a batch.” | Click **Run campaign**. Wait for live tool transcript: inspect → load → generate. Point at model id / latency / tokens. |
| 0:55–1:20 | “generate_batch is the GP. Each row has predicted capacity, posterior std — a **model estimate**, not a lab CI — EI, and a space-filling baseline lift. Not a measured saving.” | Switch to **Plan**. Scroll the table and Σ EI vs baseline. |
| 1:20–1:40 | “The agent also emitted a furnace run sheet: setpoints, what to measure, where to type the result back.” | Run sheet on Plan or Agent transcript `get_run_sheet`. |
| 1:40–2:10 | “A run comes back. I type the measured capacity. The agent will not invent that number. Save, regenerate, open proposals stay excluded.” | **Save result**, **Regenerate**. |
| 2:10–2:35 | “Review is the same campaign: audience, budget, in-sample parity, PI brief from stored facts only.” | **Review**. Point at PI brief inference line. |
| 2:35–3:00 | “Copilot can ask about EI lift, or I send it back to the Agent tab. Human still owns the furnace.” | Copilot starter + **Run as agent**. End on Live badge. |

**If live inference fails while recording.** Stop; do not present the playbook or offline templates as success. Fix the key, restart, record again.

**B-roll / cutaways (optional).** Token Factory [function calling docs](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling); `docs/scientific-integrations.md`.
