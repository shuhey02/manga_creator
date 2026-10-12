import { useState } from "react";
import { useMangaStore } from "../store/mangaStore";

export function Preview() {
  const { storyboard, assembledPages, setCurrentStep, exportManga, isLoading, loadingMessage, error } =
    useMangaStore();
  const [currentPage, setCurrentPage] = useState(0);

  if (!storyboard) return null;

  const pages = storyboard.pages;
  const pageNum = pages[currentPage]?.page_number;
  const assembledUrl = pageNum != null ? assembledPages[pageNum] : undefined;

  return (
    <div className="space-y-5">
      <div className="flex justify-between items-start flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">プレビュー</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            合成済みページを確認できます。
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setCurrentStep(2)}>
            ← 画像管理
          </button>
          <button
            className="btn-primary"
            onClick={() => setCurrentStep(4)}
          >
            エクスポートへ →
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          ⛔ {error}
        </div>
      )}

      <div className="flex gap-5">
        {/* ページサムネイルリスト */}
        <div className="flex-shrink-0 w-32 space-y-2">
          {pages.map((page, i) => {
            const url = assembledPages[page.page_number];
            return (
              <button
                key={page.page_number}
                onClick={() => setCurrentPage(i)}
                className={[
                  "w-full rounded-lg overflow-hidden border-2 transition-all",
                  currentPage === i
                    ? "border-manga-500 ring-2 ring-manga-300"
                    : "border-gray-200 hover:border-manga-300",
                ].join(" ")}
              >
                {url ? (
                  <img
                    src={url}
                    alt={`${page.page_number}ページ`}
                    className="w-full"
                    style={{ aspectRatio: "1240/1754" }}
                  />
                ) : (
                  <div
                    className="w-full bg-gray-100 flex items-center justify-center text-gray-400 text-xs"
                    style={{ aspectRatio: "1240/1754" }}
                  >
                    未合成
                  </div>
                )}
                <div className="text-center text-xs py-0.5 text-gray-500">
                  {page.page_number}P
                </div>
              </button>
            );
          })}
        </div>

        {/* メインプレビュー */}
        <div className="flex-1 min-w-0">
          <div className="card p-2">
            {assembledUrl ? (
              <div className="space-y-2">
                <img
                  src={assembledUrl}
                  alt={`${pageNum}ページ`}
                  className="w-full rounded-lg shadow-md"
                  style={{ maxHeight: "80vh", objectFit: "contain" }}
                />
                <div className="flex justify-between items-center text-sm text-gray-500 px-2">
                  <span>{pageNum}ページ目</span>
                  <a
                    href={assembledUrl}
                    download={`page_${pageNum}.png`}
                    className="text-manga-600 hover:text-manga-700 underline"
                  >
                    このページをDL
                  </a>
                </div>
              </div>
            ) : (
              <div
                className="bg-gray-100 rounded-lg flex flex-col items-center justify-center text-gray-400"
                style={{ minHeight: 400 }}
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <svg className="animate-spin w-6 h-6" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                    </svg>
                    <span>{loadingMessage}</span>
                  </div>
                ) : (
                  <>
                    <span className="text-4xl mb-3">🖼️</span>
                    <span>このページはまだ合成されていません</span>
                    <span className="text-xs mt-1">「画像管理」で画像をアップロードして合成してください</span>
                  </>
                )}
              </div>
            )}
          </div>

          {/* ナビゲーション */}
          <div className="flex justify-center items-center gap-4 mt-3">
            <button
              className="btn-secondary px-3 py-1.5 text-sm"
              disabled={currentPage === 0}
              onClick={() => setCurrentPage((p) => p - 1)}
            >
              ← 前へ
            </button>
            <span className="text-sm text-gray-600">
              {currentPage + 1} / {pages.length}
            </span>
            <button
              className="btn-secondary px-3 py-1.5 text-sm"
              disabled={currentPage === pages.length - 1}
              onClick={() => setCurrentPage((p) => p + 1)}
            >
              次へ →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
