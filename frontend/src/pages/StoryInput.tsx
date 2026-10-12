import { CopyrightNotice } from "../components/CopyrightNotice";
import { useMangaStore } from "../store/mangaStore";

const GENRE_OPTIONS = [
  "少年漫画", "少女漫画", "青年漫画", "ホラー", "SF", "ファンタジー",
  "恋愛", "スポーツ", "日常系", "ミステリー",
];

const STYLE_OPTIONS = [
  "標準的な漫画スタイル", "リアル調", "デフォルメ・ちびキャラ",
  "少女漫画風（花・キラキラ）", "劇画調", "4コマ漫画風",
];

const SAMPLE_STORY = `高校生の田中ケンジは、朝の教室で不思議な光る石を拾う。
石を手に取った瞬間、教室の風景が消え、見知らぬ古代の世界に転送されてしまった。
目の前には剣を持った少女・アリアが立っており、「勇者よ、やっと来てくれた」と言う。
ケンジは混乱しながらも、アリアの言葉の意味を理解しようとする。
その時、遠くから巨大なドラゴンの鳴き声が響いた。`;

export function StoryInput() {
  const { storyInput, setStoryInput, generateStoryboard, isLoading, loadingMessage, error } =
    useMangaStore();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!storyInput.title.trim() || !storyInput.story.trim()) return;
    generateStoryboard();
  };

  const fillSample = () => {
    setStoryInput({ title: "異世界転送の少年", story: SAMPLE_STORY });
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">ストーリー入力</h2>
        <p className="text-gray-500 mt-1 text-sm">
          漫画にしたいストーリーを入力してください。Claude AIがコマ割り・セリフ・画像プロンプトを生成します。
        </p>
      </div>

      <CopyrightNotice />

      <form onSubmit={handleSubmit} className="space-y-5 card">
        {/* タイトル */}
        <div>
          <label className="label">作品タイトル *</label>
          <input
            type="text"
            className="input-field"
            placeholder="例: 異世界転送の少年"
            value={storyInput.title}
            onChange={(e) => setStoryInput({ title: e.target.value })}
            required
          />
        </div>

        {/* ストーリー */}
        <div>
          <div className="flex justify-between items-center mb-1">
            <label className="label mb-0">ストーリー *</label>
            <button
              type="button"
              onClick={fillSample}
              className="text-xs text-manga-600 hover:text-manga-700 underline"
            >
              サンプルを使う
            </button>
          </div>
          <textarea
            className="input-field resize-none"
            rows={8}
            placeholder="ストーリーのあらすじや場面を入力してください。人物・状況・感情を具体的に書くと、より良いネームが生成されます。"
            value={storyInput.story}
            onChange={(e) => setStoryInput({ story: e.target.value })}
            required
          />
          <p className="text-xs text-gray-400 mt-1">{storyInput.story.length}文字</p>
        </div>

        {/* ジャンル・スタイル・ページ数 */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">ジャンル</label>
            <select
              className="input-field"
              value={storyInput.genre}
              onChange={(e) => setStoryInput({ genre: e.target.value })}
            >
              {GENRE_OPTIONS.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">作画スタイル</label>
            <select
              className="input-field"
              value={storyInput.style}
              onChange={(e) => setStoryInput({ style: e.target.value })}
            >
              {STYLE_OPTIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="w-32">
          <label className="label">ページ数</label>
          <input
            type="number"
            className="input-field"
            min={1}
            max={20}
            value={storyInput.num_pages}
            onChange={(e) => setStoryInput({ num_pages: Number(e.target.value) })}
          />
        </div>

        {/* エラー表示 */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
            ⛔ {error}
          </div>
        )}

        <button
          type="submit"
          className="btn-primary w-full py-3 text-base"
          disabled={isLoading || !storyInput.title.trim() || !storyInput.story.trim()}
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              {loadingMessage || "生成中…"}
            </span>
          ) : (
            "🤖 ネームを生成する"
          )}
        </button>
      </form>
    </div>
  );
}
