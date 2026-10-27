# Demo script (≤ 3 minutes)

Goal: show the **full feedback loop** and **live Nebius / NVIDIA Nemotron** usage. Record at 1080p. No copyrighted music.

**Prep (not in the video).** `cp .env.example .env`, paste `NEBIUS_API_KEY`, confirm `/api/inference/status` returns `"mode": "live"`. Start the app (`README` commands). Do not use offline demo mode for the recorded run.

| Time | Say | Show |
| --- | --- | --- |
| 0:00–0:20 | “Jupiter plans the next processing experiments for a **fixed NMC811 cathode**. Ranking is a Gaussian process. Nemotron on Nebius Token Factory only explains the numbers.” | Landing view. Point at the **Live Nemotron** badge. Point at the synthetic-demonstration disclaimer. |
| 0:20–0:40 | “We load a clearly labeled synthetic table so you don’t need a lab file. Validation checks types, missing values, duplicates.” | Click **Load demo dataset**. Scroll the preview. Read one validation line if present. |
| 0:40–1:05 | “I describe the goal in plain language. Nemotron proposes which columns to optimize. I still have to confirm units and bounds.” | Click **Propose config with Nemotron**. Wait for the inference line: model id, latency, tokens. Do **not** skip this — it is the live call. |
| 1:05–1:25 | “Four continuous inputs, one target, maximize mAh/g, lab ranges, batch of four, budget twelve.” | Gesture at the bound fields. Click **Generate ranked batch**. |
| 1:25–1:55 | “Each row has a surrogate prediction, posterior uncertainty — that’s a **model estimate**, not a lab CI — expected improvement, and explore vs exploit. Nemotron’s sentence restates those numbers; it didn’t invent them.” | Scroll the table. Point at the uncertainty caption and the inference status (live, ms, tokens). |
| 1:55–2:15 | “Export the plan for the furnace list.” | Click **Export plan CSV**. |
| 2:15–2:45 | “A run comes back. I type the measured capacity on rank 1, save, and regenerate. Jupiter excludes finished and still-open proposals and tells us how the batch moved.” | Enter a number, **Save result**, **Regenerate**. Read the change summary. |
| 2:45–3:00 | “Review is the complementary UI: same campaign, budget and in-sample parity, no new proposals. The copilot may only restate those facts.” | Switch to **Review**, point at RMSE / budget, ask the copilot “What is the best observed capacity so far?” End on the live/unconfigured badge. |

**If live inference fails while recording.** Stop; do not present offline templates as success. Fix the key, restart, record again.

**B-roll / cutaways (optional).** `docs/scientific-integrations.md` comparison table; Token Factory docs tab showing `api.tokenfactory.nebius.com`.
