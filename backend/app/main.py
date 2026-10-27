from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import get_settings
from . import nebius, optional_science, store
from .schemas import AskRequest, GoalRequest, OptimizationConfig, ResultRow, SimulationRequest
from .synthetic import sample_metadata

settings = get_settings()
app = FastAPI(
    title="Jupiter — Battery Experiment Planner",
    version="0.1.0",
    description="Hackathon MVP: Gaussian-process experiment planner with NVIDIA Nemotron explanations via Nebius Token Factory.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["http://localhost:4173", "http://127.0.0.1:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectCreate(BaseModel):
    name: str = "NMC811 processing campaign"


class ResultsBody(BaseModel):
    rows: list[ResultRow] = Field(min_length=1)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "jupiter",
        "inference": nebius.inference_status(),
        "pybamm": optional_science.pybamm_status(),
        "materials_project": optional_science.materials_project_status(),
    }


@app.get("/api/inference/status")
def inference_status() -> dict[str, Any]:
    return nebius.inference_status()


@app.get("/api/demo/sample")
def demo_sample() -> dict[str, Any]:
    return sample_metadata()


@app.post("/api/projects")
def create_project(body: ProjectCreate | None = None) -> dict[str, Any]:
    name = body.name if body else "NMC811 processing campaign"
    return store.create_project(name)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    try:
        return store.project_payload(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/dataset/sample")
def load_sample(project_id: str) -> dict[str, Any]:
    try:
        return store.load_sample_dataset(project_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/dataset/upload")
async def upload_dataset(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
        return store.upload_dataset(project_id, text, name=file.filename or "upload.csv")
    except (UnicodeDecodeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/projects/{project_id}/config")
def put_config(project_id: str, config: OptimizationConfig) -> dict[str, Any]:
    try:
        return store.save_config(project_id, config)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/goal")
def propose_goal(project_id: str, body: GoalRequest) -> dict[str, Any]:
    try:
        payload = store.project_payload(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    columns = body.available_columns or (payload.get("dataset") or {}).get("columns") or []
    return nebius.propose_goal(body.goal_text, columns, project_id=project_id)


@app.post("/api/projects/{project_id}/recommend")
def recommend(project_id: str) -> dict[str, Any]:
    try:
        return store.generate_recommendations(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/export")
def export_csv(project_id: str, batch_id: str | None = None) -> Response:
    try:
        csv_text = store.export_batch_csv(project_id, batch_id=batch_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="jupiter-experiment-plan.csv"'},
    )


@app.post("/api/projects/{project_id}/results")
def add_results(project_id: str, body: ResultsBody) -> dict[str, Any]:
    try:
        return store.add_results(project_id, [row.model_dump() for row in body.rows])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/results/upload")
async def upload_results(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    try:
        return store.add_results_csv(project_id, raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/run-sheet")
def get_run_sheet(project_id: str, batch_id: str | None = None) -> dict[str, Any]:
    try:
        return store.run_sheet(project_id, batch_id=batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/run-sheet.csv")
def get_run_sheet_csv(project_id: str, batch_id: str | None = None) -> Response:
    try:
        csv_text = store.run_sheet_csv(project_id, batch_id=batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="jupiter-lab-run-sheet.csv"'},
    )


@app.get("/api/projects/{project_id}/review")
def review(project_id: str) -> dict[str, Any]:
    try:
        return store.review_payload(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/ask")
def ask(project_id: str, body: AskRequest) -> dict[str, Any]:
    try:
        facts = store.campaign_facts(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return nebius.ask_campaign(body.question, facts, project_id=project_id)


@app.get("/api/projects/{project_id}/plot")
def plot(project_id: str) -> dict[str, Any]:
    try:
        return store.plot_data(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/simulate/pybamm")
def simulate(body: SimulationRequest) -> dict[str, Any]:
    return optional_science.run_pybamm_example(c_rate=body.c_rate, temperature_C=body.temperature_C)


@app.get("/api/materials/lookup")
def materials_lookup(formula: str = "LiNi0.8Mn0.1Co0.1O2") -> dict[str, Any]:
    return optional_science.lookup_formula(formula)


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
else:

    @app.get("/")
    def root() -> PlainTextResponse:
        return PlainTextResponse(
            "Jupiter API is running. Start the Vite frontend or build it into backend/static.\n"
        )
