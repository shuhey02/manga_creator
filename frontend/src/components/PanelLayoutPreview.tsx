import type { MangaPage, Panel } from "../types/manga";

interface Props {
  page: MangaPage;
  panelImages?: Record<string, string>; // key: `p${pageNum}_panel${panelNum}`
  selectedPanel?: number;
  onClickPanel?: (panel: Panel) => void;
  width?: number;
}

const PAGE_ASPECT = 1754 / 1240; // H/W

export function PanelLayoutPreview({
  page,
  panelImages = {},
  selectedPanel,
  onClickPanel,
  width = 200,
}: Props) {
  const height = Math.round(width * PAGE_ASPECT);
  const margin = Math.round(width * 0.023);
  const contentW = width - margin * 2;
  const contentH = height - margin * 2;
  const gutter = 3;

  return (
    <div
      className="relative bg-white border-2 border-gray-800 shadow-md rounded-sm flex-shrink-0"
      style={{ width, height }}
    >
      {/* ページ外枠 */}
      <div
        className="absolute border border-gray-700"
        style={{ left: margin, top: margin, width: contentW, height: contentH }}
      />

      {page.panels.map((panel) => {
        const lo = panel.layout;
        const px = margin + Math.round((lo.x / 100) * contentW) + gutter;
        const py = margin + Math.round((lo.y / 100) * contentH) + gutter;
        const pw = Math.round((lo.width / 100) * contentW) - gutter * 2;
        const ph = Math.round((lo.height / 100) * contentH) - gutter * 2;

        const key = `p${page.page_number}_panel${panel.panel_number}`;
        const imgUrl = panelImages[key];
        const isSelected = selectedPanel === panel.panel_number;

        return (
          <div
            key={panel.panel_number}
            className={[
              "absolute border-2 overflow-hidden cursor-pointer transition-all",
              isSelected
                ? "border-manga-500 ring-2 ring-manga-400 z-10"
                : "border-gray-800 hover:border-manga-400",
            ].join(" ")}
            style={{ left: px, top: py, width: pw, height: ph }}
            onClick={() => onClickPanel?.(panel)}
            title={`コマ${panel.panel_number}: ${panel.composition}`}
          >
            {imgUrl ? (
              <img
                src={imgUrl}
                alt={`コマ${panel.panel_number}`}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full bg-gray-100 flex items-center justify-center">
                <span className="text-gray-400 font-bold" style={{ fontSize: Math.max(8, pw / 4) }}>
                  {panel.panel_number}
                </span>
              </div>
            )}

            {/* 吹き出し位置インジケーター */}
            {panel.speech_bubbles.map((bubble, bi) => (
              <div
                key={bi}
                className="absolute bg-white border border-gray-600 rounded opacity-70"
                style={{
                  left: `${bubble.position.x}%`,
                  top: `${bubble.position.y}%`,
                  width: `${bubble.position.width}%`,
                  height: `${bubble.position.height}%`,
                }}
              />
            ))}
          </div>
        );
      })}

      {/* ページ番号 */}
      <div
        className="absolute bottom-1 left-0 right-0 text-center text-gray-500"
        style={{ fontSize: Math.max(8, width / 14) }}
      >
        {page.page_number}
      </div>
    </div>
  );
}
