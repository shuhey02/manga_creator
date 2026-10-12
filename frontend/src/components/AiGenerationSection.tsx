import { useState } from "react";
import { useMangaStore } from "../store/mangaStore";
import type { GenerationJob, MangaPage } from "../types/manga";

// 版の仕組みより前に描いたページは、その1枚を v1 とみなす（バックエンドと同じ扱い）
const pageVersions = (page: MangaPage): string[] => {
  const versions = page.generated_versions ?? [];
  if (page.generated_image && !versions.includes(page.generated_image)) {
    return [page.generated_image, ...versions];
  }
  return versions;
};

function PageEditTools({ page, disabled }: { page: MangaPage; disabled: boolean }) {
  const { selectPageVersion, redrawPanel } = useMangaStore();
  const [panelNumber, setPanelNumber] = useState(page.panels[0]?.panel_number ?? 1);
  const [instruction, setInstruction] = useState("");
  const versions = pageVersions(page);
  const current = versions.indexOf(page.generated_image ?? "") + 1;

  return (
    <div className="space-y-2">
      {versions.length > 1 && (
        <div className="flex items-center gap-1 flex-wrap text-xs">
          <span className="text-gray-500">版:</span>
          {versions.map((_, i) => (
            <button
              key={i}
              disabled={disabled || i + 1 === current}
              onClick={() => selectPageVersion(page.page_number, i + 1)}
              className={[
                "px-2 py-0.5 rounded border",
                i + 1 === current
                  ? "bg-manga-500 text-white border-manga-500"
                  : "border-gray-300 text-gray-600 hover:border-manga-400",
              ].join(" ")}
            >
              v{i + 1}
            </button>
          ))}
        </div>
      )}
      <details className="text-xs">
        <summary className="cursor-pointer text-gray-600">1コマだけ描き直す</summary>
        <div className="mt-2 space-y-2">
          <select
            className="w-full border border-gray-300 rounded px-2 py-1"
            value={panelNumber}
            onChange={(e) => setPanelNumber(Number(e.target.value))}
          >
            {page.panels.map((p) => (
              <option key={p.panel_number} value={p.panel_number}>
                コマ {p.panel_number}：{p.composition.slice(0, 20)}
              </option>
            ))}
          </select>
          <textarea
            className="w-full border border-gray-300 rounded px-2 py-1"
            rows={2}
            placeholder="直したい内容（例: もっと驚いた表情に、背景を夕方に）"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
          />
          <button
            className="btn-secondary w-full"
            disabled={disabled}
            onClick={() => redrawPanel(page.page_number, panelNumber, instruction)}
          >
            このコマを描き直す（ほかのコマはそのまま）
          </button>
        </div>
      </details>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

const isActive = (job?: GenerationJob) => job?.status === "queued" || job?.status === "running";

function JobBadge({ job }: { job?: GenerationJob }) {
  if (!job) return null;
  const label = {
    queued: "順番待ち",
    running: "生成中（数分かかります）",
    done: "完了",
    error: "失敗",
  }[job.status];
  const color = {
    queued: "bg-gray-100 text-gray-600",
    running: "bg-blue-100 text-blue-700",
    done: "bg-green-100 text-green-700",
    error: "bg-red-100 text-red-700",
  }[job.status];
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium inline-flex items-center gap-1 ${color}`}>
      {isActive(job) && <Spinner />}
      {label}
    </span>
  );
}

export function AiGenerationSection() {
  const {
    sessionId, storyboard, generationJobs, imageVersion,
    generateCharacterSheet, generatePageImage, generateAllPageImages,
  } = useMangaStore();
  if (!storyboard || !sessionId) return null;

  const fileUrl = (relative: string) => `/output/${sessionId}/${relative}?v=${imageVersion}`;
  const anyActive = Object.values(generationJobs).some(isActive);
  // 最後に起きた利用枠切れ・未ログインのエラー（どのジョブでも同じ対処になる）
  const blocking = Object.values(generationJobs)
    .filter((j) => j.status === "error" && (j.error_kind === "quota" || j.error_kind === "auth"))
    .slice(-1)[0];
  const retryAt = blocking?.error?.match(/再開の目安: ([^）]+)/)?.[1];
  const sheet = storyboard.characters.find((c) => c.reference_image)?.reference_image;
  const sheetJob = generationJobs["characters"];

  return (
    <div className="card space-y-4">
      <div className="flex justify-between items-start flex-wrap gap-3">
        <div>
          <h3 className="font-bold text-gray-900">AI でページを描く（ChatGPT / gpt-image-2）</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            コマ割りの下絵とキャラ参照シートを渡し、1ページを丸ごと描かせます。
            セリフ・効果音は合成時に重ねます。Codex CLI 経由で ChatGPT の利用枠を使います。
          </p>
        </div>
        <button className="btn-primary" disabled={anyActive} onClick={generateAllPageImages}>
          全ページを生成
        </button>
      </div>

      {blocking && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-3 text-sm text-amber-900 space-y-1">
          <p className="font-semibold">
            {blocking.error_kind === "quota"
              ? `ChatGPT の画像生成の利用枠の上限に達しました${retryAt ? `（再開の目安: ${retryAt}）` : ""}`
              : "Codex に ChatGPT アカウントでログインしていません"}
          </p>
          <p className="text-xs">
            {blocking.error_kind === "quota"
              ? "時間をおいてから、もう一度生成してください。残量は Codex の Usage 画面で確認できます。"
              : "ターミナルで codex login を実行してから、もう一度生成してください。"}
          </p>
          <details className="text-xs text-amber-800">
            <summary className="cursor-pointer">詳細</summary>
            <p className="mt-1 break-all">{blocking.error}</p>
          </details>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* キャラ参照シート */}
        <div className="border border-gray-200 rounded-xl p-3 space-y-2">
          <div className="flex justify-between items-center">
            <span className="font-semibold text-sm text-gray-800">キャラ参照シート</span>
            <JobBadge job={sheetJob} />
          </div>
          {sheet ? (
            <img src={fileUrl(sheet)} alt="キャラ参照シート" className="w-full rounded border" />
          ) : (
            <p className="text-xs text-gray-500">
              先に作っておくと、ページ間でキャラの顔・服装がそろいやすくなります（任意）。
            </p>
          )}
          <button
            className="btn-secondary w-full"
            disabled={anyActive || storyboard.characters.length === 0}
            onClick={generateCharacterSheet}
          >
            {sheet ? "作り直す" : "参照シートを作る"}
          </button>
        </div>

        {storyboard.pages.map((page) => {
          const job = generationJobs[`page_${page.page_number}`];
          return (
            <div key={page.page_number} className="border border-gray-200 rounded-xl p-3 space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-semibold text-sm text-gray-800">{page.page_number}ページ</span>
                <JobBadge job={job} />
              </div>
              {page.generated_image ? (
                <img
                  src={fileUrl(page.generated_image)}
                  alt={`${page.page_number}ページ`}
                  className="w-full rounded border"
                />
              ) : (
                <p className="text-xs text-gray-500">{page.panels.length}コマ・未生成</p>
              )}
              {job?.status === "error" && job.error_kind !== "quota" && job.error_kind !== "auth" && (
                <p className="text-xs text-red-600">{job.error}</p>
              )}
              <button
                className="btn-secondary w-full"
                disabled={anyActive}
                onClick={() => generatePageImage(page.page_number)}
              >
                {page.generated_image ? "ページ全体を描き直す" : "このページを生成"}
              </button>
              {page.generated_image && <PageEditTools page={page} disabled={anyActive} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
