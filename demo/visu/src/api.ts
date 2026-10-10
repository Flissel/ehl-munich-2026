import type { WebAction } from "./lib/design";
import { MODELS } from "./models/registry";
import { keywordProposal, llmProposal, validateActions, type Unsupported } from "./lib/interpret";

export type PromptResponse = {
  engine: string;
  summary: string;
  actions: WebAction[];
  rejected: { action: unknown; error: string }[];
  unsupported: Unsupported[];
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
  market?: string;
  market_label?: string;
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

// The Unreal viewer is launched by the local visu_pro backend (needs UE 5.8 on this PC); override with ?backend=.
const BACKEND = new URLSearchParams(location.search).get("backend") ?? "http://127.0.0.1:8000";

async function backend<T>(path: string, body?: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(BACKEND + path, body === undefined ? undefined : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch {
    throw new Error(`Unreal backend not reachable at ${BACKEND}. Start it in visu_pro/backend: ` +
      String.raw`.\.venv\Scripts\python -m uvicorn app:app --port 8000`);
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = (data as { detail?: unknown }).detail;
    throw new Error(typeof d === "string" ? d : `Request failed (${r.status})`);
  }
  return data as T;
}

// Static app: feedback scores are precomputed from Dataset/ by demo/visu/prepare_local.py into data/.
export const api = {
  prompt: async (model_id: string, prompt: string, selected: { id: string; name: string } | null,
                 components: { id: string; name: string }[]): Promise<PromptResponse> => {
    const name = MODELS[model_id]?.displayName ?? model_id;
    const llm = await llmProposal(name, prompt, components, selected?.name ?? null);
    const { proposal, engine } = llm ?? { proposal: keywordProposal(prompt),
      engine: "keyword matcher (no Rowboat model reachable)" };
    const { valid, rejected } = validateActions(proposal.actions, components);
    return { engine, summary: proposal.summary, actions: valid, rejected, unsupported: proposal.unsupported };
  },
  unrealStatus: () => backend<UnrealStatus>("/api/unreal/status"),
  unrealVisualize: (model_id: string, design: UnrealDesign) =>
    backend<UnrealStatus>("/api/unreal/visualize", { model_id, design }),
  feedbackScores: async (series: string | null, market: string | null = null): Promise<FeedbackScores> => {
    const name = `feedback-${series ?? "ALL"}${market ? `-${market}` : ""}.json`;
    const r = await fetch(`data/${name}`, { cache: "no-store" }).catch(() => null);
    if (!r || !r.ok) throw new Error("Feedback data missing: run `python demo/visu/prepare_local.py` once");
    return r.json();
  },
};
