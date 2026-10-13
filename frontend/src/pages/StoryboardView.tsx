import { useState } from "react";
import { PanelLayoutPreview } from "../components/PanelLayoutPreview";
import { useMangaStore } from "../store/mangaStore";
import type { Panel } from "../types/manga";

function BubbleTypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    normal: "bg-blue-100 text-blue-700",
    thought: "bg-purple-100 text-purple-700",
    shout: "bg-red-100 text-red-700",
    whisper: "bg-gray-100 text-gray-600",
    narration: "bg-amber-100 text-amber-700",
  };
  const label: Record<string, string> = {
    normal: "通常", thought: "思考", shout: "叫び", whisper: "ひそひそ", narration: "ナレーション",
  };
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${map[type] ?? "bg-gray-100 text-gray-600"}`}>
      {label[type] ?? type}
    </span>
  );
}

export function StoryboardView() {
  const { storyboard, panelImages, setCurrentStep, sessionId } = useMangaStore();
  const [selectedPage, setSelectedPage] = useState(0);
  const [selectedPanel, setSelectedPanel] = useState<Panel | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  if (!storyboard) return null;

  const page = storyboard.pages[selectedPage];

  const copyToClipboard = async (text: string, key: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            ネーム確認 — {storyboard.title}
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {storyboard.genre} / {storyboard.style} / {storyboard.pages.length}ページ
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => setCurrentStep(2)}
        >
          画像管理へ →
        </button>
      </div>

      {/* キャラクター情報 */}
      {storyboard.characters.length > 0 && (
        <div className="card">
          <h3 className="font-bold text-gray-700 mb-3">登場キャラクター</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {storyboard.characters.map((ch, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-3">
                <div className="font-semibold text-gray-800">{ch.name}</div>
                <div className="text-sm text-gray-600 mt-0.5">{ch.description}</div>
                <div className="mt-2">
                  <div className="text-xs text-gray-400 mb-1">画像生成キーワード（英語）:</div>
                  <div className="flex items-start gap-2">
                    <code className="text-xs bg-white border border-gray-200 rounded px-2 py-1 flex-1 break-all">
                      {ch.prompt_keywords}
                    </code>
                    <button
                      onClick={() => copyToClipboard(ch.prompt_keywords, `char-${i}`)}
                      className="text-xs text-manga-600 hover:text-manga-700 flex-shrink-0"
                    >
                      {copied === `char-${i}` ? "✓ コピー済" : "コピー"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-4">
        {/* ページ一覧（左サイドバー） */}
        <div className="flex-shrink-0 w-48 space-y-3">
          <h3 className="font-semibold text-gray-700 text-sm">ページ一覧</h3>
          {storyboard.pages.map((p, i) => (
            <div
              key={p.page_number}
              className={[
                "cursor-pointer rounded-lg p-2 transition-all",
                selectedPage === i
                  ? "ring-2 ring-manga-500 bg-manga-50"
                  : "hover:bg-gray-100",
              ].join(" ")}
              onClick={() => {
                setSelectedPage(i);
                setSelectedPanel(null);
              }}
            >
              <PanelLayoutPreview
                page={p}
                panelImages={panelImages}
                width={160}
                selectedPanel={selectedPanel?.panel_number}
                onClickPanel={setSelectedPanel}
              />
              <div className="text-center text-xs text-gray-500 mt-1">
                {p.page_number}ページ ({p.panels.length}コマ)
              </div>
            </div>
          ))}
        </div>

        {/* 右側: パネル詳細 */}
        <div className="flex-1 min-w-0 space-y-4">
          <div className="card">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-bold text-gray-800">
                {page.page_number}ページ
                {page.page_notes && (
                  <span className="ml-2 text-sm font-normal text-gray-500">
                    — {page.page_notes}
                  </span>
                )}
              </h3>
              <PanelLayoutPreview
                page={page}
                panelImages={panelImages}
                width={120}
                selectedPanel={selectedPanel?.panel_number}
                onClickPanel={setSelectedPanel}
              />
            </div>

            {/* パネル一覧 */}
            <div className="space-y-3">
              {page.panels.map((panel) => {
                const isActive = selectedPanel?.panel_number === panel.panel_number;
                return (
                  <div
                    key={panel.panel_number}
                    className={[
                      "border rounded-lg p-3 cursor-pointer transition-all",
                      isActive
                        ? "border-manga-400 bg-manga-50"
                        : "border-gray-200 hover:border-manga-300",
                    ].join(" ")}
                    onClick={() => setSelectedPanel(isActive ? null : panel)}
                  >
                    <div className="flex justify-between items-start gap-2">
                      <div className="font-semibold text-gray-800 text-sm">
                        コマ {panel.panel_number}
                        <span className="ml-2 text-xs font-normal text-gray-500">
                          [{panel.camera_angle}]
                        </span>
                      </div>
                      <div className="text-xs text-gray-400 flex-shrink-0">
                        x:{panel.layout.x}% y:{panel.layout.y}%
                        {" "}w:{panel.layout.width}% h:{panel.layout.height}%
                      </div>
                    </div>

                    <div className="mt-1 text-sm text-gray-600">{panel.composition}</div>

                    {panel.dialogue && (
                      <div className="mt-2 text-sm">
                        <span className="text-gray-500">セリフ: </span>
                        <span className="font-medium">{panel.dialogue}</span>
                      </div>
                    )}
                    {panel.sound_effect && (
                      <div className="text-sm">
                        <span className="text-gray-500">効果音: </span>
                        <span className="font-bold text-gray-700">{panel.sound_effect}</span>
                      </div>
                    )}

                    {/* 吹き出し */}
                    {panel.speech_bubbles.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {panel.speech_bubbles.map((b, bi) => (
                          <div key={bi} className="flex items-center gap-1 bg-white border border-gray-200 rounded px-2 py-0.5">
                            <BubbleTypeBadge type={b.type} />
                            {b.orientation === "vertical" && (
                              <span className="text-[10px] text-gray-500">縦</span>
                            )}
                            {b.orientation === "horizontal" && (
                              <span className="text-[10px] text-gray-500">横</span>
                            )}
                            <span className="text-xs">{b.text}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 展開: 画像プロンプト */}
                    {isActive && (
                      <div className="mt-3 space-y-2 border-t border-gray-200 pt-3">
                        <div>
                          <div className="text-xs text-gray-500 mb-1">背景:</div>
                          <div className="text-sm text-gray-700">{panel.background}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 mb-1">表情/ポーズ:</div>
                          <div className="text-sm text-gray-700">{panel.expression}</div>
                        </div>
                        <div>
                          <div className="flex justify-between items-center mb-1">
                            <div className="text-xs font-medium text-gray-600">画像生成プロンプト（英語）</div>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                copyToClipboard(panel.image_prompt_en, `prompt-en-${panel.panel_number}`);
                              }}
                              className="text-xs text-manga-600 hover:text-manga-700"
                            >
                              {copied === `prompt-en-${panel.panel_number}` ? "✓ コピー済" : "コピー"}
                            </button>
                          </div>
                          <pre className="text-xs bg-gray-50 border border-gray-200 rounded p-2 whitespace-pre-wrap break-all">
                            {panel.image_prompt_en}
                          </pre>
                        </div>
                        <div>
                          <div className="flex justify-between items-center mb-1">
                            <div className="text-xs font-medium text-gray-600">画像生成プロンプト（日本語）</div>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                copyToClipboard(panel.image_prompt_ja, `prompt-ja-${panel.panel_number}`);
                              }}
                              className="text-xs text-manga-600 hover:text-manga-700"
                            >
                              {copied === `prompt-ja-${panel.panel_number}` ? "✓ コピー済" : "コピー"}
                            </button>
                          </div>
                          <pre className="text-xs bg-gray-50 border border-gray-200 rounded p-2 whitespace-pre-wrap break-all">
                            {panel.image_prompt_ja}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
