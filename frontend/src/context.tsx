import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";
import type { PlotData, ProjectState, RecommendResponse } from "./types";

const STORAGE_KEY = "jupiter.projectId";

type Status = { kind: "idle" | "loading" | "error" | "ok"; text: string };

interface ProjectContextValue {
  project: ProjectState | null;
  plot: PlotData | null;
  latest: RecommendResponse | null;
  status: Status;
  setProject: (next: ProjectState) => void;
  wrap: <T>(label: string, fn: () => Promise<T>) => Promise<T | undefined>;
  refresh: (next: ProjectState) => Promise<void>;
  reload: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<ProjectState | null>(null);
  const [plot, setPlot] = useState<PlotData | null>(null);
  const [latest, setLatest] = useState<RecommendResponse | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle", text: "" });

  const wrap = useCallback(async <T,>(label: string, fn: () => Promise<T>) => {
    setStatus({ kind: "loading", text: label });
    try {
      const value = await fn();
      setStatus({ kind: "ok", text: "Done." });
      return value;
    } catch (err) {
      setStatus({ kind: "error", text: err instanceof Error ? err.message : String(err) });
      return undefined;
    }
  }, []);

  const refresh = useCallback(async (next: ProjectState) => {
    setProject(next);
    sessionStorage.setItem(STORAGE_KEY, next.id);
    if (next.batches?.length) setLatest(next.batches[0]);
    const plotted = await api.plot(next.id);
    setPlot(plotted);
  }, []);

  const bootstrap = useCallback(async () => {
    const existing = sessionStorage.getItem(STORAGE_KEY);
    if (existing) {
      try {
        const loaded = await api.getProject(existing);
        await refresh(loaded);
        return;
      } catch {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    }
    const created = await wrap("Creating workspace…", () => api.createProject());
    if (!created) return;
    const loaded = await wrap("Loading seeded NMC811 demonstration dataset…", () =>
      api.loadSample(created.id),
    );
    if (loaded) await refresh(loaded);
  }, [refresh, wrap]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const reload = useCallback(async () => {
    if (!project) return;
    const fresh = await api.getProject(project.id);
    await refresh(fresh);
  }, [project, refresh]);

  const value = useMemo(
    () => ({ project, plot, latest, status, setProject, wrap, refresh, reload }),
    [project, plot, latest, status, wrap, refresh, reload],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used inside ProjectProvider");
  return ctx;
}
