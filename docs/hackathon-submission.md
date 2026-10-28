# Hackathon submission draft — Jupiter

**Hackathon.** Nebius × NVIDIA Global AI Hackathon  
**Track.** Best Apps and Agents  
**Deadline.** 30 October 2026, 10:00 am PDT  
**Repo.** https://github.com/nicolehao34/Jupiter  
**License.** MIT (root `LICENSE`)

## Project title

**Jupiter** — an autonomous campaign agent that helps battery researchers improve an existing material with fewer processing runs.

## Elevator pitch (≤ 500 characters)

Battery labs still brute-force calcination temperature, hold time, and slurry recipe. Jupiter is a Token Factory agent: NVIDIA Nemotron calls tools to load a labeled NMC811 demo, fit a Gaussian-process surrogate, rank a diverse EI batch, emit a furnace run sheet, and brief the PI. It never invents μ, σ, EI, or lab results. A human still types furnace outcomes. Without a key it runs a labeled playbook of the same tools.

## What we built

A research workspace (React + FastAPI) for **closed-loop processing optimization of a fixed cathode composition**:

1. Load the seeded synthetic dataset or upload CSV.
2. Preview and validate (types, missing values, duplicates, bounds, units).
3. Choose inputs, one target, units, maximize/minimize.
4. Set allowable ranges, batch size, and budget.
5. Generate a ranked batch (GP + EI, or Latin-hypercube if *n* is too small).
6. See predicted mean, posterior std (labeled as a surrogate estimate), and a plain-language explanation.
7. Export the plan as CSV.
8. Type or upload results and generate the next batch.

## Where NVIDIA and Nebius are used

| Call | Model (default, env-configurable) | Endpoint |
| --- | --- | --- |
| Goal → structured config for review | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | `POST https://api.tokenfactory.nebius.com/v1/chat/completions` |
| Summarize deterministic validation issues | same | same |
| Explain ranked rows (explore vs exploit) using supplied μ, σ, EI | same | same |
| Summarize how the batch changed after new results | same | same |
| Write a PI brief from stored best / budget / EI lift / run sheet | same | same |
| Campaign agent tool loop (inspect, load, generate, run sheet, brief) | same + `tools` | [function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling) |

Server-side only. No key in the browser. Catalog IDs verified 27 Oct 2026 from [Token Factory model catalog](https://tokenfactory.nebius.com/model-catalog.md) and [quickstart](https://docs.tokenfactory.nebius.com/quickstart). Switch to Super/Ultra via `NEBIUS_MODEL` if you want heavier reasoning.

The numerical engine is **not** Nemotron. If `NEBIUS_API_KEY` is missing, recommendations still run and the UI says **unconfigured** — never a fake “live” success. `NEBIUS_OFFLINE_DEMO=true` is an explicit, labeled template mode.

## Why this track

A researcher-facing campaign agent for the *next batch*, not a robot. Nemotron selects tools; the GP ranks. Serverless Endpoints/Jobs are encouraged by the rules but not required; Token Factory runtime calls (including function calling) satisfy “runs on Nebius Token Factory.”

## Audience and impact (honest)

**Audience.** Battery process / materials researchers iterating on an already-chosen chemistry.  
**Intended benefit.** Spend the next *k* experiments where the surrogate’s expected improvement is high.  
**What we do not claim.** That Jupiter has been shown to reduce real lab experiments, or that the demo surface is battery physics.

## How it works (one paragraph)

Goal → Token Factory tool loop (or labeled playbook) → inspect/load/propose → sklearn `GaussianProcessRegressor` (Matern 2.5) + expected improvement → diversity batch vs space-filling baseline → furnace run sheet → grounded PI brief. SQLite stores dataset version, config, and batch. The agent cannot write measured results.

## Demo URL

*To be filled after hosting (see `docs/deployment.md`). Local fallback: `docker compose up --build` then open the printed URL.*

## Demo video

*To be recorded from `docs/demo-script.md` (≤ 3 minutes, public YouTube).*

## Built with

Python 3.12, FastAPI, scikit-learn, React 19, Vite, SQLite, Nebius Token Factory, NVIDIA Nemotron 3 Nano. Optional: PyBaMM Chen2020 SPM, Materials Project summary API.

## Feedback for organizers (draft)

Token Factory’s OpenAI-compatible `/v1/chat/completions` made the Nemotron wiring straightforward. A first-class “hackathon demo key in the browser is forbidden” example in the cookbook would help student teams. Explicit model IDs in the catalog markdown (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) were essential; keep that file authoritative.

## If this repo existed before the submission period

It did not. `main` started as LICENSE + gitignore; this project was built during the submission window.
