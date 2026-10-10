import { bmwM4Competition2021 } from "./bmw-m4-competition-2021";
import type { CarModel } from "./types";

export const MODELS: Record<string, CarModel> = {
  [bmwM4Competition2021.id]: bmwM4Competition2021,
};

export const DEFAULT_MODEL_ID = bmwM4Competition2021.id;
