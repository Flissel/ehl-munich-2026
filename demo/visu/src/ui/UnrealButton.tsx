import { useEffect, useRef, useState } from "react";
import { api, type UnrealStatus } from "../api";
import type { UnrealDesign } from "../api";

const LABEL: Record<UnrealStatus["phase"], string> = {
  not_configured: "Unreal not configured",
  not_running: "Unreal idle",
  starting: "Unreal starting…",
  loading_model: "Unreal loading model…",
  ready: "Unreal ready",
  error: "Unreal error",
};

/** Launches the separate Unreal Engine viewer; never blocks the web heat map. */
export function UnrealButton({ modelId, design }: { modelId: string; design: UnrealDesign }) {
  const [status, setStatus] = useState<UnrealStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const poll = async () => {
    try {
      const s = await api.unrealStatus();
      setStatus(s);
      setError(null);
      window.clearTimeout(timer.current);
      if (s.phase === "starting" || s.phase === "loading_model") timer.current = window.setTimeout(poll, 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(poll, 5000); // retry until the backend is back
    }
  };
  useEffect(() => { poll(); return () => window.clearTimeout(timer.current); }, []);

  const launch = async () => {
    setBusy(true); setError(null);
    try { setStatus(await api.unrealVisualize(modelId, design)); poll(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const phase = status?.phase;
  return (
    <div className="unreal">
      <button className="unreal-btn" onClick={launch} disabled={busy || phase === "not_configured"}
        title={status?.message}>Visualize in Unreal Engine</button>
      <span className={`unreal-status ${phase ?? ""}`} title={status?.message}>
        {error ? "Backend offline" : phase ? LABEL[phase] : "Checking…"}
      </span>
      {(error || (status && phase !== "ready" && phase !== "not_running")) &&
        <p className="unreal-msg small">{error ?? status?.error ?? status?.message}</p>}
    </div>
  );
}
