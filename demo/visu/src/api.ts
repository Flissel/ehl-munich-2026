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
  method: string;
  components: Record<string, FeedbackDetail>;
  no_geometry: { feature: string; reason: string; n: number; positive_share: number }[];
};

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
  feedbackScores: async (series: string | null): Promise<FeedbackScores> => {
    const r = await fetch(`data/feedback-${series ?? "ALL"}.json`, { cache: "no-store" }).catch(() => null);
    if (!r || !r.ok) throw new Error("Feedback data missing: run `python demo/visu/prepare_local.py` once");
    return r.json();
  },
};
