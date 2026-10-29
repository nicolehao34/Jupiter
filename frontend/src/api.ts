import type {
  AgentRun,
  AskReply,
  CampaignBrief,
  CampaignReview,
  OptimizationConfig,
  PlotData,
  ProjectState,
  RecommendResponse,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = response.statusText;
    const raw = await response.text();
    try {
      const body = JSON.parse(raw) as { detail?: string };
      detail = body.detail || raw || detail;
    } catch {
      detail = raw || detail;
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/csv")) {
    return (await response.text()) as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ ok: boolean; inference: ProjectState["inference"] }>("/api/health"),
  createProject: (name?: string) =>
    request<ProjectState>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name || "NMC811 processing campaign" }),
    }),
  getProject: (id: string) => request<ProjectState>(`/api/projects/${id}`),
  loadSample: (id: string) =>
    request<ProjectState>(`/api/projects/${id}/dataset/sample`, { method: "POST" }),
  uploadDataset: async (id: string, file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<ProjectState>(`/api/projects/${id}/dataset/upload`, { method: "POST", body: data });
  },
  saveConfig: (id: string, config: OptimizationConfig) =>
    request<ProjectState>(`/api/projects/${id}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }),
  proposeGoal: (id: string, goalText: string, columns: string[]) =>
    request<{
      proposed_config: Partial<OptimizationConfig>;
      summary: string;
      caveats: string[];
      inference: RecommendResponse["inference"];
    }>(`/api/projects/${id}/goal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal_text: goalText, available_columns: columns }),
    }),
  recommend: (id: string) =>
    request<RecommendResponse>(`/api/projects/${id}/recommend`, { method: "POST" }),
  exportCsv: async (id: string) => {
    const response = await fetch(`/api/projects/${id}/export`);
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  },
  exportRunSheet: async (id: string) => {
    const response = await fetch(`/api/projects/${id}/run-sheet.csv`);
    if (!response.ok) throw new Error("Run sheet export failed");
    return response.blob();
  },
  addResults: (id: string, rows: { parameters: Record<string, number>; observed: number; experiment_id?: string }[]) =>
    request<ProjectState>(`/api/projects/${id}/results`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows }),
    }),
  uploadResults: async (id: string, file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<ProjectState>(`/api/projects/${id}/results/upload`, { method: "POST", body: data });
  },
  plot: (id: string) => request<PlotData>(`/api/projects/${id}/plot`),
  review: (id: string) => request<CampaignReview>(`/api/projects/${id}/review`),
  brief: (id: string) => request<CampaignBrief>(`/api/projects/${id}/brief`),
  ask: (id: string, question: string) =>
    request<AskReply>(`/api/projects/${id}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  runAgent: (id: string, goalText: string) =>
    request<AgentRun>(`/api/projects/${id}/agent/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal_text: goalText }),
    }),
  simulate: (c_rate: number, temperature_C: number) =>
    request<Record<string, unknown>>("/api/simulate/pybamm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ c_rate, temperature_C }),
    }),
  materialsLookup: (formula: string) =>
    request<Record<string, unknown>>(`/api/materials/lookup?formula=${encodeURIComponent(formula)}`),
};
