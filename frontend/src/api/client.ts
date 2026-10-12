import axios from "axios";
import type {
  AssembleAllResponse,
  AssemblePageResponse,
  ExportResponse,
  StoryboardRequest,
  StoryboardResponse,
} from "../types/manga";

const api = axios.create({
  baseURL: "",
  timeout: 120000, // LLM呼び出しに時間がかかるため2分
});

// ─── Storyboard API ───────────────────────────────────────────────────────────

export const generateStoryboard = async (
  req: StoryboardRequest
): Promise<StoryboardResponse> => {
  const res = await api.post<StoryboardResponse>("/api/storyboard/generate", req);
  return res.data;
};

export const getSession = async (sessionId: string): Promise<StoryboardResponse> => {
  const res = await api.get<StoryboardResponse>(`/api/storyboard/session/${sessionId}`);
  return res.data;
};

// ─── Assembly API ─────────────────────────────────────────────────────────────

export const uploadPanelImage = async (
  sessionId: string,
  pageNumber: number,
  panelNumber: number,
  file: File
): Promise<{ image_url: string }> => {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("page_number", String(pageNumber));
  form.append("panel_number", String(panelNumber));
  form.append("image", file);
  const res = await api.post("/api/assembly/upload-image", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const assemblePage = async (
  sessionId: string,
  pageNumber: number
): Promise<AssemblePageResponse> => {
  const res = await api.post<AssemblePageResponse>("/api/assembly/assemble-page", {
    session_id: sessionId,
    page_number: pageNumber,
  });
  return res.data;
};

export const assembleAll = async (
  sessionId: string
): Promise<AssembleAllResponse> => {
  const res = await api.post<AssembleAllResponse>("/api/assembly/assemble-all", {
    session_id: sessionId,
  });
  return res.data;
};

export const getUploadStatus = async (
  sessionId: string
): Promise<{ uploaded: string[] }> => {
  const res = await api.get(`/api/assembly/status/${sessionId}`);
  return res.data;
};

// ─── Export API ───────────────────────────────────────────────────────────────

export const generateExport = async (
  sessionId: string,
  format: "pdf" | "zip"
): Promise<ExportResponse> => {
  const res = await api.post<ExportResponse>("/api/export/generate", {
    session_id: sessionId,
    format,
  });
  return res.data;
};
