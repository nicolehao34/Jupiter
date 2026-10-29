# Agent UI references (scientific discovery systems)

Jupiter’s workspace borrows patterns from public **AI-for-science**, lab-orchestration, experiment-campaign, and scientific workbench products. We do not copy backends. Claims below are from the linked official docs, papers, or product pages.

## Systems consulted

| System | Concrete UI pattern (as published) | What Jupiter uses | Link |
| --- | --- | --- | --- |
| **ChemCrow** | Streamlit Space: sidebar lists available tools (name + description); main panel is goal + streamed tool callbacks; OpenAI key is an explicit input, not implied live. | Tool rail; tool transcript; unconfigured vs live Token Factory is labeled. | [HF Space `app.py`](https://huggingface.co/spaces/doncamilom/ChemCrow/blob/main/app.py), [public repo](https://github.com/ur-whitelab/chemcrow-public) |
| **Coscientist** | Planner LLM calls named tools (`GOOGLE`, `PYTHON`, `DOCUMENTATION`, `EXPERIMENT`); human remains responsible for physical lab steps; tool outputs are the audit trail. | Goal → tool loop; `generate_batch` is the numerical engine; agent cannot record furnace results. | [Nature 2023](https://doi.org/10.1038/s41586-023-06792-0) |
| **Open Coscientist Viewer** | Web UI for running/monitoring a multi-agent research workflow: plan/activity visualization, ranking, iteration tracking. | Running-plan stepper updated from tool outcomes. | [GitHub README](https://github.com/jataware/open-coscientist-viewer) |
| **FutureHouse Platform** | Science agents with a **visible multi-stage process** so a user can see how a conclusion was reached; Phoenix is a chemistry-tool agent (ChemCrow deployment). | Persistent campaign HUD + per-tool provenance lines. | [Launch post (1 May 2025)](https://www.futurehouse.org/research-announcements/launching-futurehouse-platform-ai-agents), [platform](https://platform.futurehouse.org) |
| **AlabOS** | Dashboard experiment rows with progress colors (running / complete / error); each task has a name, status, and human-readable message; notification page for operator choices and error recovery. | Campaign progress + stop-reason + recoverable tool-error copy. | [Digital Discovery 2024](https://pubs.rsc.org/en/content/articlehtml/2024/dd/d4dd00129j), [docs](https://cedergrouphub.github.io/alabos/) |
| **IvoryOS** | Prep / experiment / cleanup phases; progress label says **where** the run is and **how** it ended (finished / stopped / error); workflows can pause for human intervention or after an error with rerun / continue / stop. | One campaign-progress list; human checkpoint is “your turn,” not a completed measurement. | [Nat. Commun. 2025](https://doi.org/10.1038/s41467-025-60514-w), [Run behavior](https://ivoryos.readthedocs.io/en/latest/users/run-behavior.html) |
| **Atinary SDLabs** | Campaign details: for a **manually operated** workstation, measurement input sits above the Campaign Results table; analytics as the campaign progresses; budget is a campaign iteration limit. | Plan “record results” is the human measurement step after a ranked batch. | [Campaigns docs](https://enterprise.atinary.com/documentation/docs/sdlabs_gui/campaign.html), [overview](https://enterprise.atinary.com/documentation/index.html) |
| **Citrine Platform** | Sequential learning: ranked candidates with **uncertainty**; researchers import measured results and retrain; product copy distinguishes predicted properties from lab tests. | μ / σ / EI labeled as GP predictions; origin chips for measured vs predicted. | [DOE / sequential learning](https://citrine.io/doe/), [VirtualLab](https://citrine.io/platform/citrine-virtuallab/) |
| **Rowan** | Scientist web workbench (`labs.rowansci.com`) to submit, view, and analyze calculations; methods are named engines, not a chat transcript. | Plan/Review as inspect surfaces; PyBaMM stays an optional **simulated** extra. | [Product / web interface](https://www.rowansci.com/features) |

## Judge-visible mapping (this UI pass)

1. **Campaign status strip** (all tabs) — AlabOS experiment status + IvoryOS “where / how it ended” + FutureHouse visible process: Token Factory mode, turn/stop reason, data-origin mix, budget, next action.
2. **Human checkpoint as operator handoff** — AlabOS notifications / IvoryOS pause-for-human / Atinary manual workstation input. Continue without new observations stays `awaiting_lab_results`.
3. **Tool provenance** — ChemCrow / Coscientist / FutureHouse: each tool row states what it read or wrote (dataset origin, GP strategy, run-sheet count), not only “done.”
4. **Measured vs predicted vs synthetic vs simulated** — Citrine uncertainty lists + Rowan/PyBaMM method labels + this repo’s existing `PointSource`. Demo CSV is never shown as lab data.
5. **Live vs unconfigured** — ChemCrow key prompt; Jupiter never paints a playbook as live Token Factory.
6. **Recoverable errors** — AlabOS red experiment + IvoryOS error dialog (inspect / retry / do not invent a workaround).

## Jupiter-specific choices

1. **Agent is the default route** (`#/agent`), not a copilot sidebar — the product is “run the campaign,” not “ask a question.”
2. **Persistent campaign session** in SQLite — transcript and (in live mode) Nemotron message history survive across turns; **Continue campaign** re-enters the loop after Plan records results.
3. **Running plan** panel — plan-step status derived from tool outcomes (Open Coscientist / AlabOS task progress). The human step is labeled as a checkpoint, not “done work.”
4. **Tool transcript** shows each server-side tool call with done/stop chips, provenance, and an explicit **stop reason**.
5. **Human checkpoint** after the run sheet — the agent never writes measured furnace results.
6. **Ask panel** is optional and below the agent output (ChemCrow chat is secondary to acting).
7. **Ranking** always comes from `generate_batch` (GP + EI), never from Nemotron text.
8. **Inference honesty** — UI distinguishes live Token Factory, offline demo, and unconfigured playbook; unconfigured never pretends to be live.
9. **Simulated bench robot** — after the run sheet, `plan_robot_motion` plays an RRT-Connect-style 2D path on a 3-link arm canvas ([`docs/robot-lab-simulation.md`](robot-lab-simulation.md)); labeled **Simulated arm**, not hardware.

## Out of scope (not claimed)

- We did not inspect behind-login Citrine or Atinary screens beyond public docs.
- FutureHouse’s literature agents are not part of Jupiter; only the “visible stages / tool provenance” pattern is reused.
- AlabOS device pause and IvoryOS hardware cleanup are not implemented; Jupiter’s handoff is typing a measurement on Plan.
