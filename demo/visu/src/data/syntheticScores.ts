/**
 * SYNTHETIC DEMO SCORES (0-100) for UI demonstration only.
 * They are fixed, hand-picked values (deterministic across reloads). They are NOT engineering
 * analysis, damage detection, safety measurements or AI output. Replace with backend data later
 * via getScores().
 */
export const SYNTHETIC_SCORES: Record<string, Record<string, number>> = {
  default: {
    "hood": 76,
    "roof": 92,
    "trunk-lid": 68,
    "fender-front-left": 44,
    "fender-front-right": 71,
    "quarter-rear-left": 55,
    "quarter-rear-right": 81,
    "pillars-sills": 63,
    "underbody": 29,
    "front-splitter": 12,
    "front-bumper": 18,
    "rear-diffuser": 64,
    "rear-bumper": 37,
    "side-skirt-left": 47,
    "side-skirt-right": 52,
    "rear-spoiler": 88,
    "kidney-grille": 33,
    "lower-intake": 24,
    "mirror-left": 61,
    "mirror-right": 74,
    "door-left": 58,
    "door-right": 83,
    "windshield": 95,
    "rear-window": 86,
    "window-left": 90,
    "window-right": 79,
    "headlight-left": 41,
    "headlight-right": 66,
    "taillight-left": 72,
    "taillight-right": 49,
    "wheel-front-left": 27,
    "wheel-front-right": 39,
    "wheel-rear-left": 84,
    "wheel-rear-right": 70,
    "exhaust": 57,
    "roof-fin": 97,
    "badges": 100,
    "license-plate": 8,
    "seat-driver": 82, "seat-passenger": 77, "rear-seats": 69, "instrument-cluster": 58, "central-display": 35,
    "climate-controls": 22, "center-console": 46, "dashboard": 64, "steering-wheel": 88, "pedals": 71,
    "door-trim-left": 54, "door-trim-right": 51, "overhead-console": 40, "headliner": 93, "interior-side-panels": 61,
    "seat-belts": 75, "interior-mirror": 66, "sun-visors": 85,
  },
};

export async function getScores(modelId: string): Promise<Record<string, number>> {
  return SYNTHETIC_SCORES[modelId] ?? SYNTHETIC_SCORES.default; // component ids are shared by all cars
}
