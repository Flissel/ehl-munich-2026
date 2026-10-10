import { bmwX1, bmwX5, bmwX7 } from "./cars";
import type { CarModel } from "./types";

export const MODELS: Record<string, CarModel> = {
  [bmwX1.id]: bmwX1,
  [bmwX5.id]: bmwX5,
  [bmwX7.id]: bmwX7,
};

/** The car shown for each model family of the Dataset (Torque's "Successor of"); all series -> the 5 Series' car. */
export const SERIES_MODEL: Record<string, string> = { F70: bmwX1.id, G60: bmwX5.id, G70: bmwX7.id, ALL: bmwX5.id };

export const DEFAULT_MODEL_ID = bmwX5.id;
