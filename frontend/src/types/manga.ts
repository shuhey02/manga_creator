// ─── ネームデータ型 ────────────────────────────────────────────────────────────

export interface SpeechBubblePosition {
  x: number;      // コマ内 % (0-100)
  y: number;
  width: number;
  height: number;
}

export type BubbleType = "normal" | "thought" | "shout" | "whisper";

// auto は吹き出しが縦長なら縦書き、横長なら横書き
export type BubbleOrientation = "auto" | "vertical" | "horizontal";

export interface SpeechBubble {
  text: string;
  type: BubbleType;
  position: SpeechBubblePosition;
  orientation?: BubbleOrientation;
}

export interface PanelLayout {
  x: number;      // ページ内 % (0-100)
  y: number;
  width: number;
  height: number;
}

export interface Panel {
  panel_number: number;
  layout: PanelLayout;
  composition: string;
  camera_angle: string;
  background: string;
  characters: string[];
  expression: string;
  dialogue: string;
  sound_effect: string;
  sound_effect_orientation?: "vertical" | "horizontal";
  image_prompt_en: string;
  image_prompt_ja: string;
  speech_bubbles: SpeechBubble[];
  // AI 生成ページ上で実際に描かれたコマ枠（生成画像全体に対する %）
  rendered_layout?: PanelLayout | null;
}

export interface MangaPage {
  page_number: number;
  page_notes: string;
  panels: Panel[];
  // AI 生成したページ画像（セッションディレクトリからの相対パス）
  generated_image?: string | null;
}

export interface Character {
  name: string;
  description: string;
  prompt_keywords: string;
  reference_image?: string | null;
}

export interface Storyboard {
  title: string;
  genre: string;
  style: string;
  characters: Character[];
  pages: MangaPage[];
}

// ─── API リクエスト/レスポンス型 ──────────────────────────────────────────────

export interface StoryboardRequest {
  title: string;
  story: string;
  genre: string;
  style: string;
  num_pages: number;
}

export interface StoryboardResponse {
  session_id: string;
  storyboard: Storyboard;
}

export interface AssemblePageResponse {
  session_id: string;
  page_number: number;
  image_url: string;
}

export interface AssembleAllResponse {
  session_id: string;
  pages: AssemblePageResponse[];
}

export type GenerationStatus = "queued" | "running" | "done" | "error";

export interface GenerationJob {
  job_id: string;
  session_id: string;
  kind: "page" | "characters";
  page_number: number | null;
  status: GenerationStatus;
  image_urls: string[];
  error: string | null;
}

export interface ExportResponse {
  session_id: string;
  download_url: string;
  filename: string;
}

// ─── UI 用の状態型 ────────────────────────────────────────────────────────────

export interface StoryInput {
  title: string;
  story: string;
  genre: string;
  style: string;
  num_pages: number;
}

// panel key: `p${pageNum}_panel${panelNum}`
export type PanelImageMap = Record<string, string>;
// page key: page_number (number)
export type AssembledPageMap = Record<number, string>;
// key: "characters" または `page_${pageNum}`
export type GenerationJobMap = Record<string, GenerationJob>;
