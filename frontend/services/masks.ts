import { api } from "./api";

export type MaskTool = "rectangle" | "polygon" | "brush";

/** Persisted tool: the editor's simple tools, or "multi" — a composite of
 * several simple shapes saved as one mask (geometry.shapes). */
export type PersistedMaskTool = MaskTool | "multi";

export interface MaskGeometry {
  // rectangle: {x,y,w,h}; polygon: {points:[x,y]...}; brush: {strokes:[{x,y,r}]}
  // multi: {shapes:[{tool, geometry}...]}
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  points?: [number, number][];
  strokes?: { x: number; y: number; r: number }[];
  shapes?: { tool: MaskTool; geometry: MaskGeometry }[];
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
  tool: PersistedMaskTool;
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
