import { create } from "zustand";
import * as api from "../api/client";
import type {
  AssembledPageMap,
  GenerationJob,
  GenerationJobMap,
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

  // ─── AI 画像生成 ────────────────────────────────────────────
  generationJobs: GenerationJobMap;
  // 再生成で同じ URL の画像が変わるので、表示時のキャッシュ回避に使う
  imageVersion: number;

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
  importStoryboard: (storyboard: Storyboard) => Promise<void>;
  generateCharacterSheet: () => Promise<void>;
  generatePageImage: (pageNum: number) => Promise<void>;
  generateAllPageImages: () => Promise<void>;
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

  generationJobs: {},
  imageVersion: Date.now(),

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
      const msg = api.errorMessage(e, "ネーム生成に失敗しました");
      set({ error: msg });
    } finally {
      set({ isLoading: false, loadingMessage: "" });
    }
  },

  // ─── ネーム JSON の読み込み（Claude Code 等で作ったもの） ─────────────────
  importStoryboard: async (storyboard) => {
    set({ isLoading: true, loadingMessage: "ネームを読み込み中…", error: null });
    try {
      const res = await api.importStoryboard(storyboard);
      set({ sessionId: res.session_id, storyboard: res.storyboard, currentStep: 1 });
    } catch (e: unknown) {
      set({ error: api.errorMessage(e, "ネームの読み込みに失敗しました") });
    } finally {
      set({ isLoading: false, loadingMessage: "" });
    }
  },

  // ─── AI 画像生成 ──────────────────────────────────────────────────────────
  generateCharacterSheet: async () => {
    const { sessionId } = get();
    if (!sessionId) return;
    await runGenerationJob(set, get, "characters", () => api.startCharacterSheet(sessionId));
  },

  generatePageImage: async (pageNum) => {
    const { sessionId } = get();
    if (!sessionId) return;
    await runGenerationJob(set, get, `page_${pageNum}`, () =>
      api.startPageGeneration(sessionId, pageNum)
    );
  },

  generateAllPageImages: async () => {
    const { storyboard } = get();
    if (!storyboard) return;
    // サーバー側も1枚ずつしか描かないので、順に投げて進捗を見やすくする
    for (const page of storyboard.pages) {
      await get().generatePageImage(page.page_number);
      // 利用枠切れ・未ログインは次のページでも必ず失敗するので、そこで止める
      const kind = get().generationJobs[`page_${page.page_number}`]?.error_kind;
      if (kind === "quota" || kind === "auth") break;
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
      const msg = api.errorMessage(e, "アップロードに失敗しました");
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
      const msg = api.errorMessage(e, "ページ合成に失敗しました");
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
      const msg = api.errorMessage(e, "エクスポートに失敗しました");
      set({ error: msg });
    } finally {
      set({ isLoading: false, loadingMessage: "" });
    }
  },
}));

const POLL_INTERVAL_MS = 3000;

type SetState = (partial: Partial<MangaStore> | ((s: MangaStore) => Partial<MangaStore>)) => void;

async function runGenerationJob(
  set: SetState,
  get: () => MangaStore,
  key: string,
  start: () => Promise<GenerationJob>
): Promise<void> {
  const putJob = (job: GenerationJob) =>
    set((s) => ({ generationJobs: { ...s.generationJobs, [key]: job } }));
  try {
    let job = await start();
    putJob(job);
    while (job.status === "queued" || job.status === "running") {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      job = await api.getGenerationJob(job.job_id);
      putJob(job);
    }
    if (job.status === "error") {
      // 利用枠切れ・未ログインは生成欄に専用の案内を出すので、ページ上部のエラーには出さない
      if (job.error_kind !== "quota" && job.error_kind !== "auth") {
        set({ error: job.error ?? "画像生成に失敗しました" });
      }
      return;
    }
    // 生成結果（generated_image・検出したコマ枠）はサーバー側の storyboard に入る
    const sessionId = get().sessionId;
    if (sessionId) {
      const res = await api.getSession(sessionId);
      set({ storyboard: res.storyboard, imageVersion: Date.now() });
    }
  } catch (e: unknown) {
    set({ error: api.errorMessage(e, "画像生成に失敗しました") });
  }
}
