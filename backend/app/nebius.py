"""Server-side Nebius Token Factory client for NVIDIA Nemotron.

Live calls use the OpenAI-compatible Chat Completions API:
  POST {NEBIUS_BASE_URL}/chat/completions
Docs: https://docs.tokenfactory.nebius.com/quickstart
Catalog IDs (2026-10-27): nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B, ...

Offline demo mode is explicit (NEBIUS_OFFLINE_DEMO=true). It never pretends
to be a successful live Token Factory call.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from .config import get_settings
from .db import dump, new_id, session
from .db import InferenceLog
from .schemas import InferenceMeta

SYSTEM_RULES = (
    "You are Jupiter, an experiment-planning assistant for battery researchers. "
    "You explain and structure information that was already computed by deterministic code. "
    "You must NOT invent scientific mechanisms, literature citations, experimental results, "
    "numerical predictions, materials properties, or lab outcomes. "
    "If a number is not in the user payload, say it is unavailable. "
    "Keep claims scoped to the supplied table, validation issues, and surrogate outputs. "
    "Always state that surrogate uncertainty is a model estimate, not experimental confidence. "
    "The demo dataset, if present, is synthetic and not real battery physics. "
    "Respond with JSON only, matching the requested schema."
)


class GoalPayload(BaseModel):
    target_metric: str
    direction: str
    input_variables: list[str]
    units: dict[str, str] = Field(default_factory=dict)
    rationale: str
    caveats: list[str] = Field(default_factory=list)


class TextPayload(BaseModel):
    summary: str
    bullets: list[str] = Field(default_factory=list)


def inference_status() -> dict[str, Any]:
    settings = get_settings()
    mode = settings.inference_mode
    messages = {
        "live": "Live Token Factory calls are enabled. Responses are NVIDIA Nemotron via Nebius.",
        "offline_demo": (
            "OFFLINE DEMO MODE is on (NEBIUS_OFFLINE_DEMO=true). "
            "Explanations are local templates and are NOT live Nebius/NVIDIA inference."
        ),
        "unconfigured": (
            "No NEBIUS_API_KEY is set. The numerical planner still works. "
            "To enable live Nemotron: copy .env.example to .env, add a Token Factory key from "
            "https://tokenfactory.nebius.com/, restart the API, and confirm this badge reads Live."
        ),
    }
    return {
        "mode": mode,
        "configured": settings.nebius_configured,
        "offline_demo": settings.nebius_offline_demo,
        "model": settings.nebius_model,
        "base_url": settings.nebius_base_url.rstrip("/"),
        "message": messages[mode],
        "docs": "https://docs.tokenfactory.nebius.com/quickstart",
    }


def propose_goal(goal_text: str, columns: list[str], project_id: str | None = None) -> dict[str, Any]:
    schema_hint = {
        "target_metric": "column name from available_columns",
        "direction": "maximize|minimize",
        "input_variables": ["column names from available_columns"],
        "units": {"column": "user-stated unit or empty string if unstated"},
        "rationale": "one short paragraph grounded only in the researcher's text",
        "caveats": ["things the researcher did not specify"],
    }
    user = {
        "task": "Propose a structured optimization configuration for review. Do not invent columns.",
        "researcher_goal": goal_text,
        "available_columns": columns,
        "schema": schema_hint,
        "limits": "At most 6 continuous numeric inputs and one target.",
    }
    raw, meta = complete("goal_config", user, project_id=project_id)
    try:
        parsed = GoalPayload.model_validate(_coerce_json(raw))
    except (ValidationError, ValueError) as exc:
        meta.mode = "failed" if meta.mode == "live" else meta.mode
        meta.error = f"Nemotron JSON failed schema validation: {exc}"
        return {
            "proposed_config": {},
            "summary": "The model reply was not a valid configuration. Edit the form manually.",
            "caveats": [str(exc)],
            "inference": meta,
        }
    allowed = set(columns)
    inputs = [c for c in parsed.input_variables if c in allowed]
    target = parsed.target_metric if parsed.target_metric in allowed else (columns[0] if columns else "")
    direction = parsed.direction if parsed.direction in {"maximize", "minimize"} else "maximize"
    return {
        "proposed_config": {
            "target_metric": target,
            "direction": direction,
            "input_variables": inputs,
            "units": {k: v for k, v in parsed.units.items() if k in allowed or k == target},
        },
        "summary": parsed.rationale,
        "caveats": parsed.caveats,
        "inference": meta,
    }


def summarize_validation(issues: list[dict[str, Any]], project_id: str | None = None) -> tuple[str, InferenceMeta]:
    user = {
        "task": "Summarize these deterministic validation findings. Do not add issues that are not listed.",
        "issues": issues,
        "schema": {"summary": "short paragraph", "bullets": ["actionable next step", "..."]},
    }
    raw, meta = complete("validation_summary", user, project_id=project_id)
    parsed = _parse_text(raw, meta)
    return parsed, meta


def explain_batch(payload: dict[str, Any], project_id: str | None = None) -> tuple[list[str], InferenceMeta]:
    user = {
        "task": (
            "For each ranked experiment, write one plain-language sentence that restates the "
            "supplied predicted mean, posterior std, EI, and explore/exploit label. "
            "Do not change any numbers. Do not invent mechanisms."
        ),
        "batch": payload,
        "schema": {"summary": "unused", "bullets": ["explanation for rank 1", "explanation for rank 2"]},
    }
    raw, meta = complete("batch_explanations", user, project_id=project_id)
    text_model = _parse_model(raw, meta)
    bullets = text_model.bullets if text_model else []
    return bullets, meta


def ask_campaign(question: str, facts: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    user = {
        "task": (
            "Answer the researcher's question using ONLY campaign_facts. "
            "If a number or claim is not in campaign_facts, say it is unavailable. "
            "Do not invent mechanisms, citations, or predictions."
        ),
        "question": question,
        "campaign_facts": facts,
        "schema": {"summary": "short answer", "bullets": ["supporting fact from the payload", "..."]},
    }
    raw, meta = complete("campaign_ask", user, project_id=project_id)
    parsed = _parse_model(raw, meta)
    if parsed is None:
        return {
            "answer": meta.error or "No explanation available.",
            "bullets": [],
            "inference": meta,
        }
    return {"answer": parsed.summary, "bullets": parsed.bullets, "inference": meta}


def campaign_brief(facts: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    user = {
        "task": (
            "Write a four-bullet PI update for this campaign using ONLY campaign_facts. "
            "Restate best observed, remaining budget, latest strategy, and surrogate EI lift "
            "if latest_baseline_comparison.applicable is true. "
            "If a number is missing, say it is unavailable. "
            "Do not invent mechanisms, citations, lab savings, or predictions. "
            "If data_origin is synthetic_demonstration, say the table is synthetic."
        ),
        "campaign_facts": facts,
        "schema": {
            "summary": "one-sentence headline restating stored facts",
            "bullets": ["best so far", "budget remaining", "latest batch / EI lift", "next bench action from run_sheet"],
        },
    }
    raw, meta = complete("campaign_brief", user, project_id=project_id)
    parsed = _parse_model(raw, meta)
    if parsed is None:
        return {
            "headline": meta.error or "No brief available.",
            "bullets": [],
            "inference": meta,
        }
    return {"headline": parsed.summary, "bullets": parsed.bullets, "inference": meta}


def summarize_change(payload: dict[str, Any], project_id: str | None = None) -> tuple[str, InferenceMeta]:
    user = {
        "task": (
            "Summarize how the new recommendation batch differs from the previous one using only "
            "the supplied numbers (means, stds, excluded counts, n_observed). No mechanisms."
        ),
        "comparison": payload,
        "schema": {"summary": "short paragraph", "bullets": ["optional supporting facts"]},
    }
    raw, meta = complete("change_summary", user, project_id=project_id)
    parsed = _parse_text(raw, meta)
    return parsed, meta


def complete(purpose: str, user_payload: dict[str, Any], project_id: str | None = None) -> tuple[str, InferenceMeta]:
    settings = get_settings()
    if settings.inference_mode == "offline_demo":
        text = _offline_text(purpose, user_payload)
        meta = InferenceMeta(
            mode="offline_demo",
            model=None,
            note="OFFLINE DEMO — local template, not a Token Factory response.",
        )
        _log(project_id, purpose, meta)
        return text, meta
    if settings.inference_mode == "unconfigured":
        meta = InferenceMeta(
            mode="unconfigured",
            model=settings.nebius_model,
            error=(
                "NEBIUS_API_KEY is not set. Numerical recommendations still ran. "
                "Add a Token Factory key to enable live NVIDIA Nemotron explanations."
            ),
        )
        _log(project_id, purpose, meta)
        return "", meta

    body = {
        "model": settings.nebius_model,
        "temperature": 0.2,
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": SYSTEM_RULES},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
    }
    url = settings.nebius_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.nebius_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    started = time.perf_counter()
    last_error = "unknown error"
    for attempt in range(settings.nebius_max_retries + 1):
        try:
            with httpx.Client(timeout=settings.nebius_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=body)
            latency_ms = int((time.perf_counter() - started) * 1000)
            if response.status_code >= 400:
                last_error = f"Token Factory HTTP {response.status_code}: {_safe_body(response)}"
                if response.status_code in {429, 500, 502, 503, 504} and attempt < settings.nebius_max_retries:
                    time.sleep(0.6 * (2**attempt))
                    continue
                meta = InferenceMeta(
                    mode="failed",
                    model=settings.nebius_model,
                    latency_ms=latency_ms,
                    error=last_error,
                )
                _log(project_id, purpose, meta)
                return "", meta
            data = response.json()
            content = _message_content(data)
            usage = data.get("usage") or {}
            meta = InferenceMeta(
                mode="live",
                model=data.get("model") or settings.nebius_model,
                latency_ms=latency_ms,
                prompt_tokens=_as_int(usage.get("prompt_tokens")),
                completion_tokens=_as_int(usage.get("completion_tokens")),
                total_tokens=_as_int(usage.get("total_tokens")),
                request_id=response.headers.get("x-request-id") or data.get("id"),
                note="Live NVIDIA Nemotron response via Nebius Token Factory.",
            )
            _log(project_id, purpose, meta)
            return content, meta
        except httpx.TimeoutException:
            last_error = f"Token Factory request timed out after {settings.nebius_timeout_seconds}s."
        except httpx.HTTPError as exc:
            last_error = f"Token Factory network error: {exc}"
        if attempt < settings.nebius_max_retries:
            time.sleep(0.6 * (2**attempt))
    meta = InferenceMeta(
        mode="failed",
        model=settings.nebius_model,
        latency_ms=int((time.perf_counter() - started) * 1000),
        error=last_error,
    )
    _log(project_id, purpose, meta)
    return "", meta


def _offline_text(purpose: str, user_payload: dict[str, Any]) -> str:
    if purpose == "goal_config":
        columns = user_payload.get("available_columns") or []
        goal = user_payload.get("researcher_goal", "")
        target = next((c for c in columns if "capacit" in c.lower() or "target" in c.lower()), columns[-1] if columns else "")
        inputs = [c for c in columns if c != target][:4]
        payload = {
            "target_metric": target,
            "direction": "maximize" if "minimi" not in goal.lower() else "minimize",
            "input_variables": inputs,
            "units": {},
            "rationale": (
                "OFFLINE DEMO: configuration drafted from column names and the researcher's text only. "
                "Not a live Nemotron call."
            ),
            "caveats": ["Offline demo mode is on; review every field before generating experiments."],
        }
        return json.dumps(payload)
    if purpose == "validation_summary":
        issues = user_payload.get("issues") or []
        codes = [i.get("code") for i in issues]
        return json.dumps(
            {
                "summary": (
                    f"OFFLINE DEMO: deterministic validation reported {len(issues)} issue(s) "
                    f"({', '.join(str(c) for c in codes) or 'none'}). Not a live Nemotron call."
                ),
                "bullets": [i.get("message", "") for i in issues[:6]],
            }
        )
    if purpose == "campaign_brief":
        facts = user_payload.get("campaign_facts") or {}
        budget = facts.get("budget") or {}
        baseline = facts.get("latest_baseline_comparison") or {}
        lift = baseline.get("ei_lift") if baseline.get("applicable") else "unavailable"
        sheet = facts.get("run_sheet") or {}
        n_runs = len(sheet.get("runs") or [])
        return json.dumps(
            {
                "summary": (
                    "OFFLINE DEMO: PI brief from stored facts only "
                    f"(n_observed={facts.get('n_observed')}, remaining={budget.get('remaining')}, "
                    f"EI lift={lift}). Not a live Nemotron call."
                ),
                "bullets": [
                    f"Best observed in facts: {facts.get('best_observed')}",
                    f"Budget remaining: {budget.get('remaining')} of {budget.get('total')}",
                    f"Latest strategy: {facts.get('latest_strategy')}; surrogate EI lift: {lift}",
                    f"Next bench runs on the sheet: {n_runs}. {facts.get('demo_disclaimer')}",
                ],
            }
        )
    if purpose == "campaign_ask":
        facts = user_payload.get("campaign_facts") or {}
        question = user_payload.get("question", "")
        return json.dumps(
            {
                "summary": (
                    "OFFLINE DEMO: answering from stored campaign facts only "
                    f"(n_observed={facts.get('n_observed')}, batches={facts.get('n_batches')}). "
                    f"Question was: {question[:160]}. Not a live Nemotron call."
                ),
                "bullets": [
                    f"Best observed in facts: {facts.get('best_observed')}",
                    f"Latest strategy: {facts.get('latest_strategy')}",
                    f"Surrogate EI lift: {(facts.get('latest_baseline_comparison') or {}).get('ei_lift')}",
                ],
            }
        )
    if purpose == "batch_explanations":
        rows = (user_payload.get("batch") or {}).get("rows") or []
        bullets = []
        for row in rows:
            bullets.append(
                "OFFLINE DEMO: rank {rank} is labeled {tradeoff} with predicted {mean} ± {std} "
                "and EI {ei}. Numbers copied from the surrogate; not a live Nemotron call.".format(
                    rank=row.get("rank"),
                    tradeoff=row.get("tradeoff"),
                    mean=row.get("predicted_mean"),
                    std=row.get("predicted_std"),
                    ei=row.get("acquisition"),
                )
            )
        return json.dumps({"summary": "offline", "bullets": bullets})
    comparison = user_payload.get("comparison") or {}
    return json.dumps(
        {
            "summary": (
                "OFFLINE DEMO: observations grew from "
                f"{comparison.get('n_observed_before')} to {comparison.get('n_observed_after')}. "
                "Not a live Nemotron call."
            ),
            "bullets": [],
        }
    )


def _parse_text(raw: str, meta: InferenceMeta) -> str:
    parsed = _parse_model(raw, meta)
    if parsed is None:
        return meta.error or "No explanation available."
    extra = " ".join(parsed.bullets)
    return (parsed.summary + (" " + extra if extra else "")).strip()


def _parse_model(raw: str, meta: InferenceMeta) -> TextPayload | None:
    if not raw:
        return None
    try:
        return TextPayload.model_validate(_coerce_json(raw))
    except (ValidationError, ValueError) as exc:
        meta.error = f"Response failed schema validation: {exc}"
        return None


def _coerce_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object in model output.")
    return json.loads(match.group(0))


def _message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Token Factory response had no choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text") or "")
            elif isinstance(item, str):
                parts.append(item)
        content = "".join(parts)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Token Factory response had empty content.")
    return content


def _safe_body(response: httpx.Response) -> str:
    text = response.text[:300].replace("\n", " ")
    text = re.sub(r"(sk-|Bearer\s+)[A-Za-z0-9._-]+", r"\1[redacted]", text)
    return text


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _log(project_id: str | None, purpose: str, meta: InferenceMeta) -> None:
    db = session()
    try:
        db.add(
            InferenceLog(
                id=new_id(),
                project_id=project_id,
                purpose=purpose,
                mode=meta.mode,
                model=meta.model,
                latency_ms=meta.latency_ms,
                prompt_tokens=meta.prompt_tokens,
                completion_tokens=meta.completion_tokens,
                total_tokens=meta.total_tokens,
                error=meta.error,
            )
        )
        db.commit()
    finally:
        db.close()


# Keep dump imported for potential debug; silence linters by referencing.
_ = dump
