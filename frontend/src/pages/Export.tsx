import { useMangaStore } from "../store/mangaStore";
import { CopyrightNotice } from "../components/CopyrightNotice";

export function Export() {
  const {
    storyboard, sessionId, assembledPages, exportManga, exportUrl, exportFilename,
    isLoading, loadingMessage, error, setCurrentStep,
  } = useMangaStore();

  if (!storyboard) return null;

  const assembledCount = Object.keys(assembledPages).length;
  const totalPages = storyboard.pages.length;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">エクスポート</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            漫画をPDFまたはKindle用CBZ（コミックアーカイブ）として出力します。
          </p>
        </div>
        <button className="btn-secondary" onClick={() => setCurrentStep(3)}>
          ← プレビュー
        </button>
      </div>

      <CopyrightNotice />

      {/* 合成状況 */}
      <div className="card">
        <h3 className="font-semibold text-gray-700 mb-3">合成状況</h3>
        <div className="flex items-center gap-3">
          <div className="w-full bg-gray-100 rounded-full h-3">
            <div
              className={[
                "h-3 rounded-full transition-all",
                assembledCount === totalPages ? "bg-green-500" : "bg-manga-500",
              ].join(" ")}
              style={{ width: totalPages > 0 ? `${(assembledCount / totalPages) * 100}%` : "0%" }}
            />
          </div>
          <span className={[
            "text-sm font-semibold flex-shrink-0",
            assembledCount === totalPages ? "text-green-600" : "text-manga-600",
          ].join(" ")}>
            {assembledCount} / {totalPages}
          </span>
        </div>
        {assembledCount < totalPages && (
          <p className="text-sm text-amber-600 mt-2">
            ⚠️ 未合成のページがあります。未合成ページはエクスポートに含まれません。
          </p>
        )}
      </div>

      {/* エクスポートボタン */}
      <div className="card space-y-4">
        <h3 className="font-semibold text-gray-700">出力形式を選択</h3>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* PDF */}
          <div className="border border-gray-200 rounded-xl p-4 hover:border-manga-300 transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-3xl">📄</span>
              <div>
                <div className="font-semibold text-gray-800">PDF</div>
                <div className="text-xs text-gray-500">A4縦・印刷・電子書籍向け</div>
              </div>
            </div>
            <ul className="text-xs text-gray-500 space-y-0.5 mb-4 list-disc list-inside">
              <li>Adobe Acrobat、ブラウザで閲覧可能</li>
              <li>印刷に適したA4フォーマット</li>
              <li>ページ番号付き</li>
            </ul>
            <button
              className="btn-primary w-full"
              onClick={() => exportManga("pdf")}
              disabled={isLoading || assembledCount === 0}
            >
              PDFを生成
            </button>
          </div>

          {/* CBZ/ZIP */}
          <div className="border border-gray-200 rounded-xl p-4 hover:border-manga-300 transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-3xl">📦</span>
              <div>
                <div className="font-semibold text-gray-800">Kindle用CBZ</div>
                <div className="text-xs text-gray-500">コミックアーカイブ形式</div>
              </div>
            </div>
            <ul className="text-xs text-gray-500 space-y-0.5 mb-4 list-disc list-inside">
              <li>Kindle Previewerで確認可能</li>
              <li>ComicRack / CDisplayEx 等で閲覧可</li>
              <li>右から左（日本語）設定済み</li>
            </ul>
            <button
              className="btn-primary w-full"
              onClick={() => exportManga("zip")}
              disabled={isLoading || assembledCount === 0}
            >
              CBZを生成
            </button>
          </div>
        </div>

        {/* ローディング */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-2 text-gray-600">
            <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
            {loadingMessage}
          </div>
        )}

        {/* エラー */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
            ⛔ {error}
          </div>
        )}

        {/* ダウンロードリンク */}
        {exportUrl && exportFilename && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl">✅</span>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-green-800">エクスポート完了！</div>
                <div className="text-sm text-green-600">{exportFilename}</div>
              </div>
              <a
                href={exportUrl}
                download={exportFilename}
                className="btn-primary text-sm"
              >
                ダウンロード
              </a>
            </div>
          </div>
        )}
      </div>

      {/* セッション情報 */}
      <div className="card text-sm text-gray-500 space-y-1">
        <div className="font-medium text-gray-600">セッション情報</div>
        <div>作品: <span className="text-gray-800 font-medium">{storyboard.title}</span></div>
        <div>セッションID: <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{sessionId}</code></div>
        <div className="text-xs text-gray-400">
          ※ データは <code>backend/output/{sessionId}/</code> に保存されています。
        </div>
      </div>
    </div>
  );
}
