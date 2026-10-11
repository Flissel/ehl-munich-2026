import type { WebAction } from "./lib/design";

export type PromptResponse = {
  engine: string;
  summary: string;
  actions: WebAction[];
  rejected: { action: unknown; error: string }[];
  unsupported: { request: string; category: string; reason: string }[];
};

export type FeedbackDetail = {
  score: number;
  positive_share: number;
  basis: "specific" | "general exterior";
  n: number;
  counts: Record<string, number>;
  classes: string[];
  quotes: { type: string; series: string; country: string; text: string }[];
};

export type FeedbackScores = {
  series: string;
  series_label: string;
  rows_used: number;
  method: string;
  components: Record<string, FeedbackDetail>;
  no_geometry: { feature: string; reason: string; n: number; positive_share: number }[];
};

export type UnrealStatus = {
  configured: boolean;
  phase: "not_configured" | "not_running" | "starting" | "loading_model" | "ready" | "error";
  message: string;
  error?: string | null;
};

/** Preset ids the Unreal viewer understands (it only supports paint/wheel presets). */
export type UnrealDesign = { paint: string | null; wheel_style: string | null };

async function call<T>(path: string, body?: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, body === undefined ? undefined : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Backend not reachable. Start it with: cd backend; .\\.venv\\Scripts\\python -m uvicorn app:app --port 8000");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = (data as { detail?: unknown }).detail;
    throw new Error(typeof d === "string" ? d : `Request failed (${r.status})`);
  }
  return data as T;
}

export const api = {
  prompt: (model_id: string, prompt: string, selected: { id: string; name: string } | null,
           components: { id: string; name: string }[]) =>
    call<PromptResponse>("/api/web/design", {
      model_id, prompt, component_id: selected?.id ?? null, component_name: selected?.name ?? null, components,
    }),
  feedbackScores: (series: string | null) =>
    call<FeedbackScores>(`/api/feedback/scores${series ? `?series=${encodeURIComponent(series)}` : ""}`),
  unrealStatus: () => call<UnrealStatus>("/api/unreal/status"),
  unrealVisualize: (model_id: string, design: UnrealDesign) =>
    call<UnrealStatus>("/api/unreal/visualize", { model_id, design }),
};
