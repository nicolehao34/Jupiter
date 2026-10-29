# Simulated robot motion in the agent loop

Jupiter adds **`plan_robot_motion`** after the furnace run sheet so the campaign agent can reason about **how** crucible and slurry steps would be executed on a bench — without claiming hardware control.

## What this is

| Layer | Jupiter behavior |
| --- | --- |
| **Task plan** | One pick–place sequence per ranked run (staging → tube furnace → slurry bench → measurement slot), derived from the run sheet. |
| **Motion plan** | 2D top-down **RRT-Connect-style** discrete waypoint chain with a furnace hood keep-out region (not full OMPL). |
| **Kinematics** | 3-link planar arm **inverse kinematics** for UI playback. |
| **Honesty** | `simulation_only: true` on every payload; UI labeled **Simulated arm** (same provenance family as PyBaMM “simulated”). |

## Research touchpoints (not dependencies)

- **BatteryLab** — multi-arm coin-cell assembly lab ([GitHub](https://github.com/legendPerceptor/BatteryLab)).
- **Constrained TAMP for chemistry** — long-horizon task + motion planning with spillage/collision constraints ([arXiv:2212.09672](https://arxiv.org/abs/2212.09672)).
- **MoveIt / OMPL** — industrial pattern for RRT-Connect and collision-free trajectories ([MoveIt](https://moveit.ai/)); Jupiter **does not** ship ROS/MoveIt.

## Agent placement

After **`get_run_sheet`**, the playbook or live Nemotron calls **`plan_robot_motion`**, then stops at the **human checkpoint**. The researcher still types measured capacity on Plan; the robot sim does not invent outcomes.

## UI

The **Agent** tab plays a canvas animation when `plan_robot_motion` succeeds: bench stations, obstacle, arm links, gripper state, and phase label synced to stored frames (~30 FPS playback).
