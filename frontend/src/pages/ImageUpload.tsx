import { useRef, useState } from "react";
import toast from "react-hot-toast";
import { PanelLayoutPreview } from "../components/PanelLayoutPreview";
import { useMangaStore } from "../store/mangaStore";
import type { Panel } from "../types/manga";

interface PanelCardProps {
  pageNum: number;
  panel: Panel;
  imageUrl?: string;
  onUpload: (file: File) => Promise<void>;
}

function PanelCard({ pageNum, panel, imageUrl, onUpload }: PanelCardProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [copied, setCopied] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (!file.type.startsWith("image/")) {
      toast.error("画像ファイルを選択してください");
      return;
    }
    setUploading(true);
    try {
      await onUpload(file);
      toast.success(`ページ${pageNum} コマ${panel.panel_number} アップロード完了`);
    } catch {
      toast.error("アップロードに失敗しました");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const copyPrompt = async () => {
    await navigator.clipboard.writeText(panel.image_prompt_en);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("プロンプトをコピーしました");
  };

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden bg-white">
      {/* ヘッダー */}
      <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex justify-between items-center">
        <div>
          <span className="font-semibold text-gray-800">コマ {panel.panel_number}</span>
          <span className="ml-2 text-xs text-gray-500">[{panel.camera_angle}]</span>
        </div>
        {imageUrl && (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
            ✓ アップロード済み
          </span>
        )}
      </div>

      <div className="p-4 space-y-3">
        {/* 構図説明 */}
        <p className="text-sm text-gray-700">{panel.composition}</p>

        {/* ドロップゾーン */}
        <div
          className={[
            "relative border-2 border-dashed rounded-lg transition-all cursor-pointer",
            dragging ? "border-manga-400 bg-manga-50" : "border-gray-300 hover:border-manga-400 hover:bg-gray-50",
          ].join(" ")}
          style={{ minHeight: 120 }}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
        >
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={`コマ${panel.panel_number}`}
              className="w-full rounded-lg object-contain max-h-48"
              style={{ background: "#f8f8f8" }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-gray-400">
              {uploading ? (
                <div className="flex items-center gap-2">
                  <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span className="text-sm">アップロード中…</span>
                </div>
              ) : (
                <>
                  <span className="text-3xl">🖼️</span>
                  <span className="text-sm mt-2">クリックまたはドラッグ＆ドロップ</span>
                  <span className="text-xs mt-1">JPG / PNG / WebP</span>
                </>
              )}
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
              e.target.value = "";
            }}
          />
        </div>

        {/* プロンプト */}
        <div className="space-y-1">
          <div className="flex justify-between items-center">
            <span className="text-xs font-medium text-gray-500">画像生成プロンプト（英語）</span>
            <button
              onClick={copyPrompt}
              className="text-xs text-manga-600 hover:text-manga-700"
            >
              {copied ? "✓ コピー済" : "📋 コピー"}
            </button>
          </div>
          <div className="text-xs bg-gray-50 border border-gray-200 rounded p-2 text-gray-600 break-all line-clamp-3">
            {panel.image_prompt_en}
          </div>
        </div>

        {/* セリフ・効果音 */}
        <div className="flex flex-wrap gap-2 text-xs">
          {panel.dialogue && (
            <div className="bg-blue-50 text-blue-700 px-2 py-1 rounded">
              💬 {panel.dialogue}
            </div>
          )}
          {panel.sound_effect && (
            <div className="bg-yellow-50 text-yellow-700 px-2 py-1 rounded font-bold">
              ⚡ {panel.sound_effect}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ImageUpload() {
  const {
    storyboard, panelImages, uploadImage,
    assembleAllPages, isLoading, loadingMessage, error, setCurrentStep,
  } = useMangaStore();

  if (!storyboard) return null;

  const totalPanels = storyboard.pages.reduce((acc, p) => acc + p.panels.length, 0);
  const uploadedCount = Object.keys(panelImages).length;

  return (
    <div className="space-y-5">
      <div className="flex justify-between items-start flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">画像管理</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            各コマに画像をアップロードしてください。
            プロンプトをコピーして外部の画像生成AIで生成した画像を使用できます。
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-secondary"
            onClick={() => setCurrentStep(1)}
          >
            ← ネーム確認
          </button>
          <button
            className="btn-primary"
            onClick={assembleAllPages}
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                </svg>
                {loadingMessage}
              </span>
            ) : (
              "ページを合成する →"
            )}
          </button>
        </div>
      </div>

      {/* 進捗バー */}
      <div className="card py-3">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-gray-600">アップロード進捗</span>
          <span className="font-semibold text-manga-600">
            {uploadedCount} / {totalPanels} コマ
          </span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className="bg-manga-500 h-2 rounded-full transition-all"
            style={{ width: totalPanels > 0 ? `${(uploadedCount / totalPanels) * 100}%` : "0%" }}
          />
        </div>
        <p className="text-xs text-gray-400 mt-1.5">
          ※ 未アップロードのコマはプレースホルダー（グレー背景）で合成されます
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          ⛔ {error}
        </div>
      )}

      {/* ページ別パネルカード */}
      {storyboard.pages.map((page) => (
        <div key={page.page_number}>
          <div className="flex items-center gap-3 mb-3">
            <h3 className="font-bold text-gray-800">
              {page.page_number}ページ
            </h3>
            <PanelLayoutPreview page={page} panelImages={panelImages} width={60} />
            {page.page_notes && (
              <span className="text-sm text-gray-500">{page.page_notes}</span>
            )}
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {page.panels.map((panel) => (
              <PanelCard
                key={`${page.page_number}-${panel.panel_number}`}
                pageNum={page.page_number}
                panel={panel}
                imageUrl={panelImages[`p${page.page_number}_panel${panel.panel_number}`]}
                onUpload={(file) => uploadImage(page.page_number, panel.panel_number, file)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
