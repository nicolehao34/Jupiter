"""Simulated bench robot motion planning for furnace handoff (no hardware).

Jupiter maps each ranked run to a pick–place–furnace–mix sequence in a 2D
top-down bench layout, then plans a collision-aware polyline (RRT-Connect-style
discrete waypoint chain) and converts end-effector poses to a 3-link planar arm
via inverse kinematics.

This is a **simulation** for UI playback and agent reasoning — not MoveIt, not
real-time robot control. See `docs/robot-lab-simulation.md` for references
(BatteryLab, constrained TAMP for chemistry labs, MoveIt / OMPL patterns).
"""

from __future__ import annotations

import math
from typing import Any

# Normalized bench coordinates (0–1). Not calibrated to a real cell.
STATIONS: dict[str, tuple[float, float]] = {
    "crucible_staging": (0.12, 0.58),
    "tube_furnace_door": (0.42, 0.38),
    "slurry_bench": (0.74, 0.56),
    "measurement_slot": (0.58, 0.78),
}

# Axis-aligned keep-out (furnace hood) — segments detour around it.
OBSTACLE = {"x0": 0.36, "y0": 0.28, "x1": 0.52, "y1": 0.48}

LINK_LENGTHS = (0.22, 0.18, 0.14)  # planar arm, normalized units
REFERENCES = [
    {
        "title": "BatteryLab — autonomous coin-cell assembly with robotic arms",
        "url": "https://github.com/legendPerceptor/BatteryLab",
    },
    {
        "title": "Chemistry lab automation via constrained task and motion planning",
        "url": "https://arxiv.org/abs/2212.09672",
    },
    {
        "title": "MoveIt / OMPL RRT-Connect (industrial motion planning pattern)",
        "url": "https://moveit.ai/",
    },
]


def plan_motion_for_run_sheet(sheet: dict[str, Any]) -> dict[str, Any]:
    runs = sheet.get("runs") or []
    if not runs:
        raise ValueError("Run sheet has no runs to plan robot motion for.")

    ee_waypoints: list[dict[str, Any]] = []
    for run in runs[:2]:
        ee_waypoints.extend(_task_waypoints_for_run(run))

    polyline = _rrt_connect_style_path(ee_waypoints)
    frames = _trajectory_frames(polyline)
    frames = _subsample_frames(frames, max_frames=40)

    return {
        "simulation_only": True,
        "planner": "discrete_rrt_connect_bench_2d",
        "algorithm_note": (
            "Task waypoints from the furnace run sheet, then a collision-aware "
            "polyline in 2D bench space (RRT-Connect-style discrete chain), "
            "played back on a 3-link planar arm via IK. Not connected to hardware."
        ),
        "references_doc": "docs/robot-lab-simulation.md",
        "stations": {k: {"x": v[0], "y": v[1]} for k, v in STATIONS.items()},
        "obstacle": OBSTACLE,
        "n_runs_planned": min(len(runs), 4),
        "duration_s": round(len(frames) / 30.0, 2),
        "frame_count": len(frames),
        "frames": frames,
    }


def _task_waypoints_for_run(run: dict[str, Any]) -> list[dict[str, Any]]:
    rank = run.get("run") or run.get("rank") or 1
    label = f"run_{rank}"
    return [
        {"phase": f"{label}_approach_staging", "x": STATIONS["crucible_staging"][0], "y": STATIONS["crucible_staging"][1], "gripper": "open"},
        {"phase": f"{label}_pick_crucible", "x": STATIONS["crucible_staging"][0], "y": STATIONS["crucible_staging"][1], "gripper": "close"},
        {"phase": f"{label}_to_furnace", "x": STATIONS["tube_furnace_door"][0], "y": STATIONS["tube_furnace_door"][1], "gripper": "close"},
        {"phase": f"{label}_furnace_insert", "x": STATIONS["tube_furnace_door"][0], "y": STATIONS["tube_furnace_door"][1] - 0.04, "gripper": "close"},
        {"phase": f"{label}_slurry", "x": STATIONS["slurry_bench"][0], "y": STATIONS["slurry_bench"][1], "gripper": "close"},
        {"phase": f"{label}_measure_slot", "x": STATIONS["measurement_slot"][0], "y": STATIONS["measurement_slot"][1], "gripper": "open"},
    ]


def _rrt_connect_style_path(waypoints: list[dict[str, Any]]) -> list[tuple[float, float, str, str]]:
    """Connect task waypoints with detours around the furnace obstacle."""
    path: list[tuple[float, float, str, str]] = []
    prev: tuple[float, float] | None = None
    for wp in waypoints:
        target = (float(wp["x"]), float(wp["y"]))
        phase = str(wp.get("phase") or "move")
        gripper = str(wp.get("gripper") or "close")
        if prev is None:
            path.append((target[0], target[1], phase, gripper))
            prev = target
            continue
        for x, y in _segment_with_avoidance(prev, target):
            path.append((x, y, phase, gripper))
        prev = target
    return path


def _segment_with_avoidance(
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int = 5,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(1, steps + 1):
        t = i / steps
        x = start[0] + (end[0] - start[0]) * t
        y = start[1] + (end[1] - start[1]) * t
        if _in_obstacle(x, y):
            # detour above the hood (typical constrained TAMP heuristic)
            y = OBSTACLE["y1"] + 0.06 + 0.04 * math.sin(t * math.pi)
            x = start[0] + (end[0] - start[0]) * t
        points.append((x, y))
    return points


def _in_obstacle(x: float, y: float) -> bool:
    return OBSTACLE["x0"] <= x <= OBSTACLE["x1"] and OBSTACLE["y0"] <= y <= OBSTACLE["y1"]


def _trajectory_frames(polyline: list[tuple[float, float, str, str]]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    base_x, base_y = 0.08, 0.82
    for i, (x, y, phase, gripper) in enumerate(polyline):
        joints = _inverse_kinematics_3link(base_x, base_y, x, y)
        frames.append(
            {
                "i": i,
                "t": round(i / 30.0, 3),
                "phase": phase,
                "gripper": gripper,
                "ee": {"x": x, "y": y},
                "base": {"x": base_x, "y": base_y},
                "joints": joints,
            }
        )
    return frames


def _subsample_frames(frames: list[dict[str, Any]], max_frames: int = 40) -> list[dict[str, Any]]:
    if len(frames) <= max_frames:
        return frames
    step = max(1, len(frames) // max_frames)
    out = frames[::step]
    if out[-1] is not frames[-1]:
        out.append(frames[-1])
    for i, frame in enumerate(out):
        frame = dict(frame)
        frame["i"] = i
        frame["t"] = round(i / 30.0, 3)
        out[i] = frame
    return out


def _inverse_kinematics_3link(bx: float, by: float, tx: float, ty: float) -> list[float]:
    """Planar 3-link IK — elbow-down solution for animation."""
    dx, dy = tx - bx, ty - by
    dist = max(0.05, min(math.hypot(dx, dy), sum(LINK_LENGTHS) - 0.01))
    angle = math.atan2(dy, dx)
    l1, l2, l3 = LINK_LENGTHS
    # solve first two links toward target, third orients to point
    a = dist
    cos_a2 = (a * a - l1 * l1 - l2 * l2) / (2 * l1 * l2)
    cos_a2 = max(-1.0, min(1.0, cos_a2))
    a2 = math.acos(cos_a2)
    a1 = math.atan2(dy, dx) - math.atan2(l2 * math.sin(a2), l1 + l2 * math.cos(a2))
    a3 = angle - a1 - a2
    return [round(a1, 4), round(a2, 4), round(a3, 4)]
