import { create } from "zustand";
import * as api from "../api/client";
import type {
  AssembledPageMap,
  PanelImageMap,
  Storyboard,
  StoryInput,
} from "../types/manga";

interface MangaStore {
  // ─── 入力 ───────────────────────────────────────────────────
  storyInput: StoryInput;
  setStoryInput: (input: Partial<StoryInput>) => void;

  // ─── ネーム ─────────────────────────────────────────────────
  sessionId: string | null;
  storyboard: Storyboard | null;
  setStoryboard: (sessionId: string, storyboard: Storyboard) => void;
  updateStoryboard: (storyboard: Storyboard) => void;

  // ─── アップロード済み画像 ────────────────────────────────────
  panelImages: PanelImageMap;
  setPanelImage: (pageNum: number, panelNum: number, url: string) => void;

  // ─── 合成済みページ ──────────────────────────────────────────
  assembledPages: AssembledPageMap;
  setAssembledPage: (pageNum: number, url: string) => void;

  // ─── エクスポート ────────────────────────────────────────────
  exportUrl: string | null;
  exportFilename: string | null;

  // ─── UI状態 ─────────────────────────────────────────────────
  currentStep: number;
  setCurrentStep: (n: number) => void;
  isLoading: boolean;
  loadingMessage: string;
  error: string | null;
  setError: (e: string | null) => void;

  // ─── アクション ──────────────────────────────────────────────
  generateStoryboard: () => Promise<void>;
  uploadImage: (pageNum: number, panelNum: number, file: File) => Promise<void>;
  assembleAllPages: () => Promise<void>;
  exportManga: (format: "pdf" | "zip") => Promise<void>;
}

export const useMangaStore = create<MangaStore>((set, get) => ({
  // ─── 初期状態 ─────────────────────────────────────────────────────────────
  storyInput: {
    title: "",
    story: "",
    genre: "少年漫画",
    style: "標準的な漫画スタイル",
    num_pages: 4,
  },
  setStoryInput: (input) =>
    set((s) => ({ storyInput: { ...s.storyInput, ...input } })),

  sessionId: null,
  storyboard: null,
  setStoryboard: (sessionId, storyboard) => set({ sessionId, storyboard }),
  updateStoryboard: (storyboard) => set({ storyboard }),

  panelImages: {},
  setPanelImage: (pageNum, panelNum, url) =>
    set((s) => ({
      panelImages: {
        ...s.panelImages,
        [`p${pageNum}_panel${panelNum}`]: url,
      },
    })),

  assembledPages: {},
  setAssembledPage: (pageNum, url) =>
    set((s) => ({ assembledPages: { ...s.assembledPages, [pageNum]: url } })),

  exportUrl: null,
  exportFilename: null,

  currentStep: 0,
  setCurrentStep: (n) => set({ currentStep: n }),
  isLoading: false,
  loadingMessage: "",
  error: null,
  setError: (e) => set({ error: e }),

  // ─── ネーム生成 ───────────────────────────────────────────────────────────
  generateStoryboard: async () => {
    const { storyInput } = get();
    set({ isLoading: true, loadingMessage: "Claude AIがネームを生成中…", error: null });
    try {
      const res = await api.generateStoryboard(storyInput);
      set({
        sessionId: res.session_id,
        storyboard: res.storyboard,
        currentStep: 1,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "ネーム生成に失敗しました";
      set({ error: msg });
    } finally {
      set({ isLoading: false, loadingMessage: "" });
    }
  },

  // ─── 画像アップロード ─────────────────────────────────────────────────────
  uploadImage: async (pageNum, panelNum, file) => {
    const { sessionId } = get();
    if (!sessionId) return;
    try {
      const res = await api.uploadPanelImage(sessionId, pageNum, panelNum, file);
      get().setPanelImage(pageNum, panelNum, res.image_url);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "アップロードに失敗しました";
      set({ error: msg });
    }
  },

  // ─── 全ページ合成 ─────────────────────────────────────────────────────────
  assembleAllPages: async () => {
    const { sessionId } = get();
    if (!sessionId) return;
    set({ isLoading: true, loadingMessage: "ページを合成中…", error: null });
    try {
      const res = await api.assembleAll(sessionId);
      for (const page of res.pages) {
        get().setAssembledPage(page.page_number, page.image_url);
      }
      set({ currentStep: 3 });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "ページ合成に失敗しました";
      set({ error: msg });
    } finally {
      set({ isLoading: false, loadingMessage: "" });
    }
  },

  // ─── エクスポート ─────────────────────────────────────────────────────────
  exportManga: async (format) => {
    const { sessionId } = get();
    if (!sessionId) return;
    const label = format === "pdf" ? "PDF" : "Kindle用ZIP";
    set({ isLoading: true, loadingMessage: `${label}を生成中…`, error: null });
    try {
      const res = await api.generateExport(sessionId, format);
      set({
        exportUrl: res.download_url,
        exportFilename: res.filename,
        currentStep: 4,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "エクスポートに失敗しました";
      set({ error: msg });
    } finally {
      set({ isLoading: false, loadingMessage: "" });
    }
  },
}));
