import { Color } from "three";

/** Heat map stops: 0 red -> 25 orange-red -> 50 yellow -> 75 yellow-green -> 100 green. */
const STOPS: [number, string][] = [
  [0, "#ff2020"],
  [25, "#ff7a1a"],
  [50, "#ffe600"],
  [75, "#9be22d"],
  [100, "#20d65a"],
];
const STOP_COLORS = STOPS.map(([s, hex]) => [s, new Color(hex)] as const);

export function clampScore(score: number): number {
  return Math.max(0, Math.min(100, Number.isFinite(score) ? score : 0));
}

/** Smoothly interpolated heat map color for a 0-100 score (interpolated in sRGB for predictable hues). */
export function scoreToColor(score: number): Color {
  const s = clampScore(score);
  for (let i = 1; i < STOP_COLORS.length; i++) {
    const [s1, c1] = STOP_COLORS[i];
    if (s <= s1) {
      const [s0, c0] = STOP_COLORS[i - 1];
      const t = (s - s0) / (s1 - s0);
      return new Color().setRGB(c0.r + (c1.r - c0.r) * t, c0.g + (c1.g - c0.g) * t, c0.b + (c1.b - c0.b) * t);
    }
  }
  return STOP_COLORS[STOP_COLORS.length - 1][1].clone();
}

export function scoreToHex(score: number): string {
  return `#${scoreToColor(score).getHexString()}`;
}

export const LEGEND_GRADIENT = `linear-gradient(90deg, ${STOPS.map(([s, c]) => `${c} ${s}%`).join(", ")})`;
