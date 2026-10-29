"""Campaign agent: Nemotron chooses tools; the GP still ranks experiments.

Live mode uses Token Factory function calling
(https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling).
Without a key, a labeled playbook runs the same tools in order — never as a fake live call.

The agent may not invent μ, σ, EI, or lab results. It cannot record furnace outcomes.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from . import nebius, store
from .config import get_settings
from .schemas import OptimizationConfig

MAX_STEPS = 10
TOOL_RESULT_CHARS = 4000

AGENT_SYSTEM = (
    "You are Jupiter, an autonomous campaign manager for battery processing experiments. "
    "You act by calling tools. Ranking is done only by generate_batch (Gaussian process + EI). "
    "Never invent predicted_mean, predicted_std, EI, mechanisms, citations, or lab measurements. "
    "Never claim you ran a furnace. After you have a batch and a PI brief, stop. "
    "If a tool errors, explain the error and stop rather than fabricating a workaround."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "inspect_campaign",
            "description": "Read dataset, config, budget, latest batch, and inference mode.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_demo_dataset",
            "description": "Load the labeled synthetic NMC811 demonstration table and seed config.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_config",
            "description": "Ask Nemotron for a reviewable config from the researcher's goal. Does not save.",
            "parameters": {
                "type": "object",
                "properties": {"goal_text": {"type": "string"}},
                "required": ["goal_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_config",
            "description": "Persist optimization config (inputs, target, bounds, batch size, budget).",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_variables": {"type": "array", "items": {"type": "string"}},
                    "target_metric": {"type": "string"},
                    "direction": {"type": "string", "enum": ["maximize", "minimize"]},
                    "batch_size": {"type": "integer"},
                    "experiment_budget": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_batch",
            "description": "Fit the GP and rank the next processing batch. Numerical engine, not the LLM.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_run_sheet",
            "description": "Return numbered furnace/slurry setpoints for the latest batch.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_pi_brief",
            "description": "Grounded PI brief from stored facts only.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


def run_campaign_agent(project_id: str, goal_text: str, max_steps: int = MAX_STEPS) -> dict[str, Any]:
    settings = get_settings()
    max_steps = max(1, min(int(max_steps), MAX_STEPS))
    if settings.inference_mode == "live":
        return _run_live(project_id, goal_text, max_steps)
    return _run_playbook(project_id, goal_text, settings.inference_mode)


def execute_tool(project_id: str, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments = arguments or {}
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"Unknown or forbidden tool: {name}"}
    try:
        return {"ok": True, "tool": name, "result": handler(project_id, arguments)}
    except (KeyError, ValueError) as exc:
        return {"ok": False, "tool": name, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - unexpected
        return {"ok": False, "tool": name, "error": f"{type(exc).__name__}: {exc}"}


def _run_playbook(project_id: str, goal_text: str, mode: str) -> dict[str, Any]:
    transcript: list[dict[str, Any]] = []
    plan = [
        ("inspect_campaign", {}),
        ("load_demo_dataset", {}),
        ("propose_config", {"goal_text": goal_text}),
        ("generate_batch", {}),
        ("get_run_sheet", {}),
        ("write_pi_brief", {}),
    ]
    snapshot = store.project_payload(project_id)
    if snapshot.get("dataset"):
        plan = [step for step in plan if step[0] != "load_demo_dataset"]

    for name, args in plan:
        outcome = execute_tool(project_id, name, args)
        transcript.append(_event(name, args, outcome))
        if not outcome.get("ok"):
            break

    return {
        "controller": "playbook",
        "goal_text": goal_text,
        "inference": {
            "mode": mode,
            "model": None,
            "note": (
                "Labeled playbook: the same campaign tools ran in a fixed order. "
                "This is not a live Token Factory tool-calling loop."
            ),
            "error": None if mode != "unconfigured" else (
                "NEBIUS_API_KEY is not set. Tools still ran. Add a Token Factory key for live Nemotron tool calls."
            ),
        },
        "transcript": transcript,
        "final_text": _playbook_summary(transcript, mode),
        "disclaimer": (
            "The agent does not record lab results. Ranking came from generate_batch "
            "(Gaussian process + expected improvement), not from Nemotron."
        ),
    }


def _run_live(project_id: str, goal_text: str, max_steps: int) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM},
        {
            "role": "user",
            "content": (
                "Run this processing campaign end to end with tools. "
                f"Researcher goal: {goal_text}. "
                "Inspect, load the demo table if empty, propose then generate a batch, "
                "fetch the run sheet, write a PI brief, then stop. "
                "Do not invent numbers. Do not record furnace results."
            ),
        },
    ]
    transcript: list[dict[str, Any]] = []
    last_meta = None
    final_text = ""
    for _ in range(max_steps):
        message, meta = nebius.complete_with_tools(messages, TOOLS, project_id=project_id)
        last_meta = meta
        if meta.mode != "live":
            transcript.append(
                {
                    "tool": None,
                    "arguments": {},
                    "ok": False,
                    "error": meta.error or "Token Factory tool call did not return live.",
                }
            )
            break
        tool_calls = message.get("tool_calls") or []
        content = message.get("content") or ""
        if isinstance(content, str) and content.strip() and not tool_calls:
            final_text = content.strip()
            break
        if not tool_calls:
            final_text = final_text or "The model stopped without calling a tool."
            break
        assistant_msg: dict[str, Any] = {"role": "assistant", "tool_calls": tool_calls}
        if content:
            assistant_msg["content"] = content
        messages.append(assistant_msg)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                args = {}
                outcome = {"ok": False, "error": "Tool arguments were not valid JSON."}
            else:
                outcome = execute_tool(project_id, name, args if isinstance(args, dict) else {})
            transcript.append(_event(name, args if isinstance(args, dict) else {}, outcome))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or name,
                    "name": name,
                    "content": json.dumps(_compact(outcome), default=str)[:TOOL_RESULT_CHARS],
                }
            )
    if not final_text:
        final_text = _playbook_summary(transcript, (last_meta.mode if last_meta else "failed"))
    return {
        "controller": "live" if last_meta and last_meta.mode == "live" else "failed",
        "goal_text": goal_text,
        "inference": last_meta.model_dump() if last_meta else None,
        "transcript": transcript,
        "final_text": final_text,
        "disclaimer": (
            "The agent does not record lab results. Ranking came from generate_batch "
            "(Gaussian process + expected improvement), not from Nemotron."
        ),
    }


def _inspect(project_id: str, _args: dict[str, Any]) -> dict[str, Any]:
    payload = store.project_payload(project_id)
    dataset = payload.get("dataset") or {}
    config = payload.get("config")
    latest = (payload.get("batches") or [None])[0]
    return {
        "has_dataset": bool(dataset),
        "data_origin": dataset.get("data_origin"),
        "n_rows": dataset.get("n_rows"),
        "columns": dataset.get("columns"),
        "has_config": bool(config),
        "n_batches": len(payload.get("batches") or []),
        "latest_strategy": (latest or {}).get("strategy") if latest else None,
        "inference": payload.get("inference"),
    }


def _load_demo(project_id: str, _args: dict[str, Any]) -> dict[str, Any]:
    payload = store.load_sample_dataset(project_id)
    dataset = payload.get("dataset") or {}
    return {
        "loaded": True,
        "data_origin": dataset.get("data_origin"),
        "n_rows": dataset.get("n_rows"),
        "target": (payload.get("config") or {}).get("target_metric"),
        "note": "Synthetic demonstration table, not lab measurements.",
    }


def _propose(project_id: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = store.project_payload(project_id)
    columns = (payload.get("dataset") or {}).get("columns") or []
    goal = str(args.get("goal_text") or "")
    return nebius.propose_goal(goal, columns, project_id=project_id)


def _save(project_id: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = store.project_payload(project_id)
    existing = payload.get("config") or {}
    merged = {**existing}
    for key in ("input_variables", "target_metric", "direction", "batch_size", "experiment_budget", "units", "bounds"):
        if key in args and args[key] is not None:
            merged[key] = args[key]
    config = OptimizationConfig.model_validate(merged)
    saved = store.save_config(project_id, config)
    return {"saved": True, "config": saved.get("config")}


def _generate(project_id: str, _args: dict[str, Any]) -> dict[str, Any]:
    batch = store.generate_recommendations(project_id)
    rows = []
    for row in batch.get("rows") or []:
        rows.append(
            {
                "rank": row.get("rank"),
                "parameters": row.get("parameters"),
                "predicted_mean": row.get("predicted_mean"),
                "predicted_std": row.get("predicted_std"),
                "acquisition": row.get("acquisition"),
                "tradeoff": row.get("tradeoff"),
            }
        )
    return {
        "batch_id": batch.get("batch_id"),
        "strategy": batch.get("strategy"),
        "n_observed": batch.get("n_observed"),
        "baseline_comparison": batch.get("baseline_comparison"),
        "rows": rows,
        "note": "These numbers come from the Gaussian-process surrogate, not from Nemotron.",
    }


def _run_sheet(project_id: str, _args: dict[str, Any]) -> dict[str, Any]:
    sheet = store.run_sheet(project_id)
    return {
        "title": sheet.get("title"),
        "instructions": sheet.get("instructions"),
        "runs": sheet.get("runs"),
    }


def _brief(project_id: str, _args: dict[str, Any]) -> dict[str, Any]:
    facts = store.campaign_facts(project_id)
    return nebius.campaign_brief(facts, project_id=project_id)


TOOL_HANDLERS: dict[str, Callable[[str, dict[str, Any]], Any]] = {
    "inspect_campaign": _inspect,
    "load_demo_dataset": _load_demo,
    "propose_config": _propose,
    "save_config": _save,
    "generate_batch": _generate,
    "get_run_sheet": _run_sheet,
    "write_pi_brief": _brief,
}


def _event(name: str, args: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    result = outcome.get("result")
    return {
        "tool": name,
        "arguments": args,
        "ok": bool(outcome.get("ok")),
        "error": outcome.get("error"),
        "result": _compact(result) if outcome.get("ok") else None,
    }


def _compact(value: Any) -> Any:
    text = json.dumps(value, default=str)
    if len(text) <= TOOL_RESULT_CHARS:
        return value
    return {"truncated": True, "preview": text[:1200]}


def _playbook_summary(transcript: list[dict[str, Any]], mode: str) -> str:
    names = [step["tool"] for step in transcript if step.get("ok")]
    failed = next((step for step in transcript if not step.get("ok")), None)
    if failed:
        return (
            f"Playbook stopped at {failed.get('tool')}: {failed.get('error')}. "
            f"Completed tools: {', '.join(names) or 'none'}. Mode={mode}."
        )
    return (
        f"Campaign tools finished ({', '.join(names)}). Ranking was generate_batch "
        f"(GP + EI). Mode={mode}. Record furnace results on the Plan tab — the agent will not invent them."
    )
