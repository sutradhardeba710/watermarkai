import { api } from "./api";

export type MaskTool = "rectangle" | "polygon" | "brush";

export interface MaskGeometry {
  // rectangle: {x,y,w,h}; polygon: {points:[x,y]...}; brush: {strokes:[{x,y,r}]}
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  points?: [number, number][];
  strokes?: { x: number; y: number; r: number }[];
}

export interface MaskOptions {
  mask_expansion: number;
  mask_feathering: number;
  temporal_smoothing: boolean;
  apply_to_entire: boolean;
  start_time?: number | null;
  end_time?: number | null;
}

export interface Mask extends MaskOptions {
  id: string;
  project_id: string;
  tool: MaskTool;
  geometry: MaskGeometry;
  width: number;
  height: number;
  created_at: string;
}

export const masksApi = {
  get: (projectId: string) =>
    api.get<Mask>(`/projects/${projectId}/mask`).then((r) => r.data),
  put: (projectId: string, body: Omit<Mask, "id" | "project_id" | "created_at">) =>
    api.put<Mask>(`/projects/${projectId}/mask`, body).then((r) => r.data),
  delete: (projectId: string) =>
    api.delete(`/projects/${projectId}/mask`),
};
