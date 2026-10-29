"""Campaign agent: Nemotron chooses tools; the GP still ranks experiments.

Sessions persist in SQLite so each POST continues the same campaign (transcript,
OpenAI message history for live mode, checkpoint counters).

Live mode uses Token Factory function calling. Without a key, a stateful labeled
playbook picks the next tool from campaign state — never presented as live success.

The agent may not invent μ, σ, EI, or lab results. It cannot record furnace outcomes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from . import nebius, store
from .config import get_settings
from .schemas import OptimizationConfig

MAX_STEPS = 10
TOOL_RESULT_CHARS = 4000

StopReason = Literal[
    "human_checkpoint",
    "awaiting_lab_results",
    "tool_error",
    "max_steps",
    "model_stop",
    "session_reset",
]

LIVE_ENABLE_HINT = (
    "To enable live Nemotron tool calling locally: copy .env.example to .env in the repo root, "
    "set NEBIUS_API_KEY to your Nebius Token Factory key (https://tokenfactory.nebius.com/), "
    "keep NEBIUS_OFFLINE_DEMO=false, restart the API, and confirm GET /api/health reports "
    '"mode": "live". Never commit .env or paste keys into chat.'
)

AGENT_SYSTEM = (
    "You are Jupiter, an autonomous campaign manager for battery processing experiments. "
    "You act by calling tools. Ranking is done only by generate_batch (Gaussian process + EI). "
    "Never invent predicted_mean, predicted_std, EI, mechanisms, citations, or lab measurements. "
    "Never claim you ran a furnace or record experiment outcomes. "
    "After get_run_sheet succeeds, stop and wait for the human to type measured results on Plan. "
    "On continuation turns, inspect_campaign first; if new observations exist since the last "
    "checkpoint, you may generate_batch and get_run_sheet again, then stop. "
    "If no new observations, stop and tell the researcher to record results first. "
    "If a tool errors, explain the error and stop rather than fabricating a workaround."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "inspect_campaign",
            "description": "Read dataset, config, budget, observations, latest batch, inference mode.",
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
            "description": "Grounded PI brief from stored facts only (optional; never invent citations).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]

RUNNING_PLAN_TEMPLATE = [
    {"id": "observe", "label": "Inspect campaign state", "tools": ["inspect_campaign", "load_demo_dataset"]},
    {"id": "configure", "label": "Propose and apply config", "tools": ["propose_config", "save_config"]},
    {"id": "rank", "label": "Fit GP and rank batch", "tools": ["generate_batch"]},
    {"id": "handoff", "label": "Furnace run sheet", "tools": ["get_run_sheet"]},
    {"id": "checkpoint", "label": "Human records measured results", "tools": []},
]


def run_campaign_agent(
    project_id: str,
    goal_text: str,
    max_steps: int = MAX_STEPS,
    *,
    continue_campaign: bool = False,
    reset_session: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    max_steps = max(1, min(int(max_steps), MAX_STEPS))

    if reset_session:
        store.clear_agent_session(project_id)
        session: dict[str, Any] | None = None
    else:
        session = store.get_agent_session(project_id)

    if continue_campaign:
        if not session or session.get("phase") not in {"human_checkpoint", "awaiting_lab_results"}:
            return _response_from_session(
                project_id,
                session,
                goal_text,
                stop_reason="awaiting_lab_results",
                final_text=(
                    "No campaign is waiting at a checkpoint. Run a new campaign goal first, "
                    "complete the run sheet handoff, then record results on Plan before continuing."
                ),
                turn_transcript=[],
                settings=settings,
            )
        turn = int(session.get("turn") or 0) + 1
        goal_text = session.get("goal_text") or goal_text
    else:
        turn = 1 if not session else int(session.get("turn") or 0) + 1

    if settings.inference_mode == "live":
        payload = _run_live_turn(
            project_id, goal_text, max_steps, continue_campaign=continue_campaign, turn=turn, prior=session
        )
    else:
        payload = _run_playbook_turn(
            project_id,
            goal_text,
            settings.inference_mode,
            continue_campaign=continue_campaign,
            turn=turn,
            prior=session,
        )

    store.save_agent_session(project_id, payload["_session"])
    del payload["_session"]
    payload["live_enable_hint"] = LIVE_ENABLE_HINT if settings.inference_mode != "live" else None
    return payload


def get_session_payload(project_id: str) -> dict[str, Any]:
    session = store.get_agent_session(project_id)
    settings = get_settings()
    summary = store.agent_session_summary(session)
    return {
        "session": summary,
        "transcript": (session or {}).get("transcript") or [],
        "goal_text": (session or {}).get("goal_text"),
        "final_text": None,
        "live_enable_hint": LIVE_ENABLE_HINT if settings.inference_mode != "live" else None,
    }


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


def _run_playbook_turn(
    project_id: str,
    goal_text: str,
    mode: str,
    *,
    continue_campaign: bool,
    turn: int,
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    cumulative = list((prior or {}).get("transcript") or [])
    turn_transcript: list[dict[str, Any]] = []
    stop_reason: StopReason = "human_checkpoint"
    final_text = ""
    proposed_config: dict[str, Any] | None = None

    n_obs_before = len(store.project_payload(project_id).get("observations") or [])
    checkpoint_obs = (prior or {}).get("observations_at_checkpoint")

    if continue_campaign:
        inspect_out = execute_tool(project_id, "inspect_campaign", {})
        turn_transcript.append(_event("inspect_campaign", {}, inspect_out))
        cumulative.append(turn_transcript[-1])
        if not inspect_out.get("ok"):
            return _build_turn_result(
                project_id,
                goal_text,
                mode,
                turn,
                cumulative,
                turn_transcript,
                "playbook",
                "tool_error",
                _playbook_summary(turn_transcript, mode, "tool_error"),
                prior,
                checkpoint_obs,
            )
        n_obs = len(store.project_payload(project_id).get("observations") or [])
        if checkpoint_obs is not None and n_obs <= int(checkpoint_obs):
            stop_reason = "awaiting_lab_results"
            final_text = (
                f"No new measured results since checkpoint ({n_obs} observation(s)). "
                "Record furnace outcomes on Plan, then click Continue campaign."
            )
            return _build_turn_result(
                project_id,
                goal_text,
                mode,
                turn,
                cumulative,
                turn_transcript,
                "playbook",
                stop_reason,
                final_text,
                prior,
                checkpoint_obs,
            )
        tool_queue = ["generate_batch", "get_run_sheet"]
    else:
        tool_queue = ["inspect_campaign"]
        snapshot = store.project_payload(project_id)
        if not snapshot.get("dataset"):
            tool_queue.append("load_demo_dataset")
        tool_queue.extend(["propose_config", "save_config", "generate_batch", "get_run_sheet"])

    for name in tool_queue:
        args: dict[str, Any] = {}
        if name == "propose_config":
            args = {"goal_text": goal_text}
        elif name == "save_config":
            if not proposed_config:
                propose_step = next((s for s in turn_transcript if s.get("tool") == "propose_config" and s.get("ok")), None)
                if propose_step:
                    proposed_config = (propose_step.get("result") or {}).get("proposed_config") or {}
            payload = store.project_payload(project_id)
            existing = payload.get("config") or {}
            args = {**existing, **(proposed_config or {})}
            if not args:
                continue
        outcome = execute_tool(project_id, name, args)
        event = _event(name, args, outcome)
        turn_transcript.append(event)
        cumulative.append(event)
        if name == "propose_config" and outcome.get("ok"):
            proposed_config = (outcome.get("result") or {}).get("proposed_config") or {}
        if not outcome.get("ok"):
            return _build_turn_result(
                project_id,
                goal_text,
                mode,
                turn,
                cumulative,
                turn_transcript,
                "playbook",
                "tool_error",
                _playbook_summary(turn_transcript, mode, "tool_error"),
                prior,
                checkpoint_obs,
            )
        if name == "get_run_sheet" and outcome.get("ok"):
            stop_reason = "human_checkpoint"
            n_obs = len(store.project_payload(project_id).get("observations") or [])
            final_text = (
                "Run sheet ready. Execute furnaces and type measured capacity on Plan — "
                "the agent will not invent lab results. Then Continue campaign to re-rank."
            )
            return _build_turn_result(
                project_id,
                goal_text,
                mode,
                turn,
                cumulative,
                turn_transcript,
                "playbook",
                stop_reason,
                final_text,
                prior,
                n_obs,
            )

    final_text = final_text or _playbook_summary(turn_transcript, mode, stop_reason)
    return _build_turn_result(
        project_id,
        goal_text,
        mode,
        turn,
        cumulative,
        turn_transcript,
        "playbook",
        stop_reason,
        final_text,
        prior,
        checkpoint_obs if continue_campaign else n_obs_before,
    )


def _run_live_turn(
    project_id: str,
    goal_text: str,
    max_steps: int,
    *,
    continue_campaign: bool,
    turn: int,
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    cumulative = list((prior or {}).get("transcript") or [])
    turn_transcript: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = list((prior or {}).get("messages") or [])
    checkpoint_obs = (prior or {}).get("observations_at_checkpoint")

    if not messages:
        messages = [
            {"role": "system", "content": AGENT_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Run this processing campaign with tools. "
                    f"Researcher goal: {goal_text}. "
                    "Inspect, load demo if empty, propose and save config, generate_batch, "
                    "get_run_sheet, then stop for human lab work. Do not invent numbers."
                ),
            },
        ]
    elif continue_campaign:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Continuation turn: the researcher may have recorded new furnace results on Plan. "
                    "Inspect the campaign. If there are new observations since the last checkpoint, "
                    "you may generate_batch and get_run_sheet again, then stop. "
                    "If not, stop and ask them to record results — do not invent outcomes."
                ),
            }
        )

    last_meta = None
    final_text = ""
    stop_reason: StopReason = "model_stop"
    handoff_done = False

    for _ in range(max_steps):
        message, meta = nebius.complete_with_tools(messages, TOOLS, project_id=project_id)
        last_meta = meta
        if meta.mode != "live":
            turn_transcript.append(
                {
                    "tool": None,
                    "arguments": {},
                    "ok": False,
                    "error": meta.error or "Token Factory tool call did not return live.",
                }
            )
            cumulative.extend(turn_transcript)
            stop_reason = "tool_error"
            break
        tool_calls = message.get("tool_calls") or []
        content = message.get("content") or ""
        if isinstance(content, str) and content.strip() and not tool_calls:
            final_text = content.strip()
            stop_reason = "model_stop"
            break
        if not tool_calls:
            final_text = final_text or "The model stopped without calling a tool."
            stop_reason = "model_stop"
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
            event = _event(name, args if isinstance(args, dict) else {}, outcome)
            turn_transcript.append(event)
            cumulative.append(event)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or name,
                    "name": name,
                    "content": json.dumps(_compact(outcome), default=str)[:TOOL_RESULT_CHARS],
                }
            )
            if not outcome.get("ok"):
                stop_reason = "tool_error"
                final_text = f"Stopped at {name}: {outcome.get('error')}"
                handoff_done = True
                break
            if name == "get_run_sheet":
                handoff_done = True
                stop_reason = "human_checkpoint"
                final_text = (
                    final_text
                    or "Run sheet emitted. Record measured results on Plan before the next agent turn."
                )
                break
        if handoff_done:
            break
    else:
        stop_reason = "max_steps"

    if continue_campaign and stop_reason == "model_stop" and not handoff_done:
        n_obs = len(store.project_payload(project_id).get("observations") or [])
        if checkpoint_obs is not None and n_obs <= int(checkpoint_obs):
            stop_reason = "awaiting_lab_results"
            final_text = (
                final_text or "No new observations since the last checkpoint. Record results on Plan first."
            )

    if not final_text:
        final_text = _playbook_summary(turn_transcript, "live", stop_reason)

    obs_at_cp = checkpoint_obs
    if stop_reason == "human_checkpoint":
        obs_at_cp = len(store.project_payload(project_id).get("observations") or [])

    controller = "live" if last_meta and last_meta.mode == "live" else "failed"
    return _build_turn_result(
        project_id,
        goal_text,
        last_meta.mode if last_meta else "failed",
        turn,
        cumulative,
        turn_transcript,
        controller,
        stop_reason,
        final_text,
        prior,
        obs_at_cp,
        messages=messages,
        inference_meta=last_meta.model_dump() if last_meta else None,
    )


def _build_turn_result(
    project_id: str,
    goal_text: str,
    mode: str,
    turn: int,
    cumulative: list[dict[str, Any]],
    turn_transcript: list[dict[str, Any]],
    controller: str,
    stop_reason: StopReason,
    final_text: str,
    prior: dict[str, Any] | None,
    observations_at_checkpoint: int | None,
    *,
    messages: list[dict[str, Any]] | None = None,
    inference_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    phase = "human_checkpoint" if stop_reason == "human_checkpoint" else (
        "awaiting_lab_results" if stop_reason == "awaiting_lab_results" else "idle"
    )
    can_continue = phase in {"human_checkpoint", "awaiting_lab_results"}
    running_plan = _running_plan_from_transcript(cumulative, stop_reason)

    session = {
        "goal_text": goal_text,
        "turn": turn,
        "phase": phase,
        "stop_reason": stop_reason,
        "controller": controller,
        "observations_at_checkpoint": observations_at_checkpoint,
        "can_continue": can_continue,
        "transcript": cumulative,
        "running_plan": running_plan,
        "messages": messages or (prior or {}).get("messages") or [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    inference: dict[str, Any] | None
    if controller == "live" and inference_meta:
        inference = inference_meta
    else:
        inference = {
            "mode": mode,
            "model": None,
            "note": (
                "Labeled playbook: tools are chosen from campaign state each turn. "
                "This is not a live Token Factory tool-calling loop."
                if controller == "playbook"
                else None
            ),
            "error": (
                "NEBIUS_API_KEY is not set. Tools still ran. See live_enable_hint in the API response."
                if mode == "unconfigured" and controller == "playbook"
                else None
            ),
        }

    return {
        "_session": session,
        "controller": controller,
        "goal_text": goal_text,
        "turn": turn,
        "stop_reason": stop_reason,
        "phase": phase,
        "can_continue": can_continue,
        "running_plan": running_plan,
        "turn_transcript": turn_transcript,
        "transcript": cumulative,
        "inference": inference,
        "final_text": final_text,
        "disclaimer": (
            "The agent does not record lab results. Ranking came from generate_batch "
            "(Gaussian process + expected improvement), not from Nemotron."
        ),
        "continue_hint": (
            "Record measured furnace results on Plan, then POST continue_campaign=true to resume."
            if can_continue
            else None
        ),
    }


def _response_from_session(
    project_id: str,
    session: dict[str, Any] | None,
    goal_text: str,
    *,
    stop_reason: StopReason,
    final_text: str,
    turn_transcript: list[dict[str, Any]],
    settings: Any,
) -> dict[str, Any]:
    mode = settings.inference_mode
    cumulative = list((session or {}).get("transcript") or [])
    return {
        "controller": (session or {}).get("controller") or "playbook",
        "goal_text": goal_text,
        "turn": (session or {}).get("turn") or 0,
        "stop_reason": stop_reason,
        "phase": (session or {}).get("phase") or "idle",
        "can_continue": bool((session or {}).get("can_continue")),
        "running_plan": (session or {}).get("running_plan") or [],
        "turn_transcript": turn_transcript,
        "transcript": cumulative,
        "inference": {"mode": mode, "model": None, "note": final_text, "error": None},
        "final_text": final_text,
        "disclaimer": (
            "The agent does not record lab results. Ranking came from generate_batch "
            "(Gaussian process + expected improvement), not from Nemotron."
        ),
        "continue_hint": None,
        "live_enable_hint": LIVE_ENABLE_HINT if mode != "live" else None,
    }


def _running_plan_from_transcript(transcript: list[dict[str, Any]], stop_reason: StopReason) -> list[dict[str, Any]]:
    ok_tools = {step["tool"] for step in transcript if step.get("ok") and step.get("tool")}
    plan: list[dict[str, Any]] = []
    for block in RUNNING_PLAN_TEMPLATE:
        tools = block["tools"]
        if not tools:
            status = (
                "done"
                if stop_reason in {"human_checkpoint", "awaiting_lab_results"}
                else "pending"
            )
            if stop_reason == "awaiting_lab_results":
                status = "running"
            plan.append({"id": block["id"], "label": block["label"], "status": status})
            continue
        if all(t in ok_tools for t in tools):
            status = "done"
        elif any(t in ok_tools for t in tools):
            status = "running"
        else:
            status = "pending"
        plan.append({"id": block["id"], "label": block["label"], "status": status})
    return plan


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
        "n_observations": len(payload.get("observations") or []),
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
                "source": row.get("source", "surrogate_prediction"),
            }
        )
    return {
        "batch_id": batch.get("batch_id"),
        "strategy": batch.get("strategy"),
        "n_observed": batch.get("n_observed"),
        "baseline_comparison": batch.get("baseline_comparison"),
        "warnings": batch.get("warnings") or [],
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


def _playbook_summary(transcript: list[dict[str, Any]], mode: str, stop_reason: str) -> str:
    names = [step["tool"] for step in transcript if step.get("ok")]
    failed = next((step for step in transcript if not step.get("ok")), None)
    if failed:
        return (
            f"Playbook stopped at {failed.get('tool')}: {failed.get('error')}. "
            f"Completed tools: {', '.join(names) or 'none'}. Mode={mode}."
        )
    if stop_reason == "awaiting_lab_results":
        return (
            f"Waiting for new lab measurements (tools this turn: {', '.join(names) or 'inspect only'}). "
            f"Mode={mode}."
        )
    return (
        f"Campaign turn finished ({', '.join(names)}). stop_reason={stop_reason}. "
        f"Ranking was generate_batch (GP + EI). Mode={mode}. "
        "Record furnace results on Plan — the agent will not invent them."
    )
