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
2. **Tool transcript** shows each server-side tool call with done/stop chips (AlabOS-style task rows).
3. **Human checkpoint** after the run sheet — the agent never writes measured furnace results (honest self-driving-lab handoff).
4. **Ask panel** is optional and below the agent output (ChemCrow chat is secondary to acting).
5. **Ranking** always comes from `generate_batch` (GP + EI), never from Nemotron text.
