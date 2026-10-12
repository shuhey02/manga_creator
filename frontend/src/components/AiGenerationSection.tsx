import { useMangaStore } from "../store/mangaStore";
import type { GenerationJob } from "../types/manga";

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
              {job?.status === "error" && <p className="text-xs text-red-600">{job.error}</p>}
              <button
                className="btn-secondary w-full"
                disabled={anyActive}
                onClick={() => generatePageImage(page.page_number)}
              >
                {page.generated_image ? "描き直す" : "このページを生成"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
