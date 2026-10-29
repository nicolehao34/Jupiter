# Submit now — what only Nicole can click

Code and drafts are in this repo. These official items need **your** GitHub, Token Factory, host, YouTube, and Devpost accounts. Deadline **Friday 30 Oct 2026, 10:00 am PDT**.

## 1. Public repo + MIT in About (required)

1. Open https://github.com/nicolehao34/Jupiter/settings
2. **Danger Zone → Change repository visibility → Public**
3. Repo home → gear next to **About** → check **MIT License** so it shows at the top of the page
4. Merge the open stack into `main` if not already: #4 baseline → #5 run sheet → #6 PI brief → #7 agent

`LICENSE` is already MIT (Nicole Hao 2026). GitHub only shows it in About on a **public** repo.

## 2. Live Token Factory (required for the video)

1. https://tokenfactory.nebius.com/ → API keys
2. Locally or on the host: `cp .env.example .env`, set `NEBIUS_API_KEY`, `NEBIUS_OFFLINE_DEMO=false`
3. Restart the API
4. `curl -s https://YOUR-HOST/api/inference/status` must return `"mode": "live"`
5. In the UI the badge must read **Live Nemotron**, not unconfigured / offline demo

Hackathon credits: Nebius Builder Program on the [Devpost home](https://nebiusglobalaihackathon.devpost.com/).

## 3. Hosted demo URL (required for Best Apps)

Keep it free and up through **15 Dec 2026 12:00 pm PT**.

Fastest path: Render Blueprint (`render.yaml` in repo root).

1. https://dashboard.render.com/select-repo?type=blueprint
2. Connect `nicolehao34/Jupiter`
3. Add secret `NEBIUS_API_KEY`
4. Health check is `/api/health`
5. Paste the `onrender.com` URL into Devpost **and** `docs/hackathon-submission.md` (Demo URL)

Or: `docs/deployment.md` (Docker, Fly, Cloud Run).

## 4. YouTube ≤ 3 min, public (required)

Record from `docs/demo-script.md` **with live inference on screen** (model id, latency, tokens). The README mp4 is an unconfigured UI clip — do **not** submit it as the official video.

Upload to YouTube as **Public** or **Unlisted** (must be viewable without login). No copyrighted music.

## 5. Devpost form (paste from `docs/hackathon-submission.md`)

| Field | Paste |
| --- | --- |
| Track | Best Apps and Agents |
| Name | Jupiter |
| Tagline / elevator | Elevator pitch in the submission draft (≤ 500 characters) |
| Description | “What we built” + “Where NVIDIA and Nebius are used” |
| Demo URL | hosted URL from step 3 |
| Repo | https://github.com/nicolehao34/Jupiter |
| Video | YouTube URL from step 4 |
| Built with | Python, FastAPI, scikit-learn, React, Nebius Token Factory, NVIDIA Nemotron |
| Feedback | “Feedback for organizers” paragraph |

This project did **not** exist before the submission window — skip the pre-existing explanation.

Optional: IRL Builders & Brews city.

## What this environment cannot do

No Token Factory key, no GitHub owner toggle, no Render/Fly login, no YouTube account, no Devpost login. The agent, docs, and `render.yaml` are ready for you to finish those five clicks.
