import axios, { type AxiosProgressEvent } from "axios";

import { api } from "./api";
import type { UploadCompleteResponse, UploadInitiateResponse } from "@/types";

export type UploadCancelSource = {
  token: import("axios").CancelToken;
  cancel: () => void;
};

export const createCancelSource = (): UploadCancelSource => axios.CancelToken.source();

// In-memory handoff of the just-uploaded File from /upload to the mask-editor
// workspace (/projects/[id]). The workspace consumes + clears it on mount so
// it can show an instant local preview (URL.createObjectURL) while the signed
// backend proxy URL is still being fetched. Next App Router has no router
// state, so this singleton is the lightest reliable channel.
let _pendingUploadFile: File | null = null;

export function setPendingUploadFile(file: File | null): void {
  _pendingUploadFile = file;
}

export function takePendingUploadFile(): File | null {
  const f = _pendingUploadFile;
  _pendingUploadFile = null;
  return f;
}

export interface InitiateArgs {
  project_id?: string;
  filename: string;
  total_bytes?: number;
  content_type?: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
  bytesPerSecond: number;
}

export const uploadsApi = {
  initiate: (body: InitiateArgs) =>
    api
      .post<UploadInitiateResponse>("/uploads/initiate", {
        project_id: body.project_id ?? "",
        filename: body.filename,
        total_bytes: body.total_bytes,
        content_type: body.content_type,
      })
      .then((r) => r.data),

  // The multipart body is sent directly to /uploads/{id}/complete, which the
  // backend streams straight to storage. We use a raw axios call (not the
  // pre-configured `api` client) only to pass onUploadProgress + a cancel
  // token; headers (auth bearer) are mirrored from localStorage so the auth
  // dependency still applies.
  complete: (
    uploadId: string,
    file: File,
    opts: {
      onProgress?: (p: UploadProgress) => void;
      cancelToken?: import("axios").CancelToken;
    } = {},
  ): Promise<UploadCompleteResponse> => {
    const form = new FormData();
    form.append("file", file);
    if (file.type) form.append("declared_mime", file.type);

    const token =
      typeof window !== "undefined"
        ? window.localStorage.getItem("vwa_access_token")
        : null;

    const startedAt = Date.now();
    return axios
      .post<UploadCompleteResponse>(`${api.defaults.baseURL}/uploads/${uploadId}/complete`, form, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        cancelToken: opts.cancelToken,
        onUploadProgress: (e: AxiosProgressEvent) => {
          if (!opts.onProgress) return;
          const total = e.total ?? file.size;
          const elapsed = Math.max(1, (Date.now() - startedAt) / 1000);
          opts.onProgress({
            loaded: e.loaded,
            total,
            percent: total ? Math.round((e.loaded / total) * 100) : 0,
            bytesPerSecond: Math.round(e.loaded / elapsed),
          });
        },
      })
      .then((r) => r.data);
  },

  // The BE-004 envelope unwraps on the shared `api` client, but the raw axios
  // call above does not — so callers surface errors from the response body.
  cancel: (uploadId: string) =>
    api.delete(`/uploads/${uploadId}`).then((r) => r.data),
};
