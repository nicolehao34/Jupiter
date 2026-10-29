# Agent UI references (scientific discovery systems)

Jupiter’s **Agent** workspace borrows patterns from public autonomous chemistry / lab systems. We do not copy their backends; we align the UX with what researchers expect from tool-using agents and self-driving-lab dashboards.

| System | What we borrowed | Link |
| --- | --- | --- |
| **ChemCrow** | Sidebar listing available tools; main panel for goal + streamed tool activity; chemistry agent is tool-augmented, not chat-only. | [HF Space](https://huggingface.co/spaces/doncamilom/ChemCrow), [paper/repo](https://github.com/ur-whitelab/chemcrow-public) |
| **Coscientist** | Multi-step plan → execute loop; human remains responsible for physical lab steps; emphasis on explainable tool use. | [Nature 2023](https://doi.org/10.1038/s41586-023-06792-0) |
| **Open Coscientist Viewer** | Workflow / iteration visualization and monitoring agent activity in a web UI. | [GitHub](https://github.com/jataware/open-coscientist-viewer) |
| **AlabOS** | Experiment progress bar (running / complete / error); per-task status messages; operator handoff for maintenance and recovery. | [Dashboard description](https://www.researchgate.net/publication/380821486_AlabOS_A_Python-based_Reconfigurable_Workflow_Management_Framework_for_Autonomous_Laboratories) |
| **IvoryOS** | Phased workflow (prepare → experiment → cleanup); drag-and-drop mental model mapped here to observe → plan → propose → handoff → report. | [Nat. Commun. 2025](https://doi.org/10.1038/s41467-025-60514-w) |

## Jupiter-specific choices

1. **Agent is the default route** (`#/agent`), not a copilot sidebar — the product is “run the campaign,” not “ask a question.”
2. **Persistent campaign session** in SQLite — transcript and (in live mode) Nemotron message history survive across turns; **Continue campaign** re-enters the loop after Plan records results.
3. **Running plan** panel — plan-step status derived from tool outcomes (Open Coscientist / AlabOS task progress).
4. **Tool transcript** shows each server-side tool call with done/stop chips and an explicit **stop reason** (human checkpoint, awaiting lab results, tool error).
5. **Human checkpoint** after the run sheet — the agent never writes measured furnace results (honest self-driving-lab handoff).
6. **Ask panel** is optional and below the agent output (ChemCrow chat is secondary to acting).
7. **Ranking** always comes from `generate_batch` (GP + EI), never from Nemotron text.
8. **Inference honesty** — UI distinguishes live Token Factory, offline demo, and unconfigured playbook; unconfigured never pretends to be live.
