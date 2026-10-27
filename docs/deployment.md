# Deployment

The smallest hosted demo is **one container**: FastAPI serves `/api/*` and the built React app.

## What Nicole still needs to do

1. Create a Nebius Token Factory key at https://tokenfactory.nebius.com/ (API keys).
2. Set `NEBIUS_API_KEY` in the host’s environment (never in git).
3. Optionally set `MATERIALS_PROJECT_API_KEY` for the lookup panel.
4. Deploy the image and paste the public URL into Devpost **and** `docs/hackathon-submission.md`.
5. Keep the URL up through the judging period (1–15 Dec 2026).

Live inference is **not** required for the numerical loop. Without a key the app still recommends experiments; the badge will read **unconfigured**.

## Local (compose)

```bash
cp .env.example .env
# edit NEBIUS_API_KEY
docker compose up --build
# http://localhost:8000
```

## Single Docker image (Fly, Render, Cloud Run, …)

```bash
docker build -t jupiter .
docker run --rm -p 8000:8000 --env-file .env jupiter
```

### Render (example)

- New **Web Service**, connect `nicolehao34/Jupiter`.
- Dockerfile at repo root.
- Health check: `/api/health`.
- Env: `NEBIUS_API_KEY`, `NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1`, `NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `NEBIUS_OFFLINE_DEMO=false`, `JUPITER_CORS_ORIGINS=https://<your-service>.onrender.com`.
- Persistent disk optional (`/app/backend/data`) so SQLite survives restarts; otherwise each deploy starts empty (the UI reloads the demo CSV).

### Fly.io (example)

```bash
fly launch --dockerfile Dockerfile --name jupiter-planner
fly secrets set NEBIUS_API_KEY=...
fly deploy
```

## Verify live Nemotron after deploy

```bash
curl -s https://YOUR-HOST/api/inference/status
# expect "mode": "live"
```

Then in the UI: **Propose config with Nemotron** and confirm the recommendation panel shows `Inference: live`, a model id, latency, and token usage — not “offline demo” and not a mocked paragraph presented as success.
