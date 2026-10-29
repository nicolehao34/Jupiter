# Submit now — what only Nicole can click

Code, tests, agent loop, and drafts are in this repo on **`main`**. These official items need **your** GitHub, Token Factory, host, YouTube, and Devpost accounts.

**Deadline: Friday 30 Oct 2026, 10:00 am PDT** ([Devpost rules](https://nebiusglobalaihackathon.devpost.com/rules)).

---

## Remaining checklist (you)

### 1. Public repo + MIT in About (required)

- [ ] https://github.com/nicolehao34/Jupiter/settings → **Public**
- [ ] Repo **About** → check **MIT License** (shows at top of GitHub page)
- [ ] Confirm `main` is current (stack #4–#11 already merged)

### 2. Live Token Factory (required for judging video + runtime call rule)

- [ ] Create API key: https://tokenfactory.nebius.com/
- [ ] Optional credits: code **`NEBIUS-DEVPOST-GLOBAL26`** + [Nebius Builder Program](https://dev.nebius.com/builders) ([hackathon resources](https://nebiusglobalaihackathon.devpost.com/resources))
- [ ] Local or host: `cp .env.example .env`, set `NEBIUS_API_KEY`, `NEBIUS_OFFLINE_DEMO=false`
- [ ] Restart API; `curl -s https://YOUR-HOST/api/health` → `"mode": "live"`
- [ ] UI badge: **Live Nemotron** (not unconfigured / offline demo)
- [ ] **Never** commit `.env` or paste the key in chat

### 3. Hosted demo URL (required — Best Apps track)

Must stay up through **15 Dec 2026 12:00 pm PT** (judging).

- [ ] Render: https://dashboard.render.com/select-repo?type=blueprint → connect repo → use root `render.yaml`
- [ ] Set secret **`NEBIUS_API_KEY`** on the service
- [ ] Health: `/api/health`
- [ ] Smoke: `#/agent` → Run campaign with live inference
- [ ] Paste URL into Devpost **and** `docs/hackathon-submission.md` (Demo URL field)

Alternatives: `docs/deployment.md` (Docker, Fly, Cloud Run).

### 4. YouTube demo ≤ 3 min, public (required)

- [ ] Follow **`docs/demo-script.md`** with **live** Nemotron on screen (model id, latency/tokens if shown)
- [ ] Show: Agent tool loop → GP batch table → run sheet → human types result on Plan → **Continue campaign** → Review / PI brief
- [ ] Upload **Public** or **Unlisted** (viewable without login); no copyrighted music
- [ ] **Do not** submit the README mp4 as the official video (that clip is unconfigured playbook only)

### 5. Devpost entry

Paste from **`docs/hackathon-submission.md`**:

- [ ] Track: **Best Apps and Agents**
- [ ] Demo URL (hosted)
- [ ] Repo: https://github.com/nicolehao34/Jupiter
- [ ] Video URL (YouTube)
- [ ] Description + “Where NVIDIA / Nebius are used”
- [ ] Built with: Python, FastAPI, scikit-learn, React, Nebius Token Factory, NVIDIA Nemotron
- [ ] Feedback for organizers
- [ ] Optional: IRL Builders & Brews city

### 6. Final sanity (rules)

- [ ] README setup works on a clean clone
- [ ] Video matches hosted behavior
- [ ] No secrets in git; Materials Project key optional only

---

## What agents already shipped

- Autonomous multi-turn agent (SQLite session, continue after lab results)
- Agent / Plan / Review / campaign status UI
- GP + EI ranking, baseline comparison, run sheet, grounded PI brief
- `render.yaml`, submission drafts, README walkthrough mp4 (playbook mode)

## What this environment cannot do

No GitHub visibility toggle, no Render/YouTube/Devpost login, no Nicole’s Token Factory key.
