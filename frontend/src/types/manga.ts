// ─── ネームデータ型 ────────────────────────────────────────────────────────────

export interface SpeechBubblePosition {
  x: number;      // コマ内 % (0-100)
  y: number;
  width: number;
  height: number;
}

export type BubbleType = "normal" | "thought" | "shout" | "whisper";

export interface SpeechBubble {
  text: string;
  type: BubbleType;
  position: SpeechBubblePosition;
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
  image_prompt_en: string;
  image_prompt_ja: string;
  speech_bubbles: SpeechBubble[];
}

export interface MangaPage {
  page_number: number;
  page_notes: string;
  panels: Panel[];
}

export interface Character {
  name: string;
  description: string;
  prompt_keywords: string;
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
