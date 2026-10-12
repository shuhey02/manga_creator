import { Toaster } from "react-hot-toast";
import { StepIndicator } from "./components/StepIndicator";
import { Export } from "./pages/Export";
import { ImageUpload } from "./pages/ImageUpload";
import { Preview } from "./pages/Preview";
import { StoryboardView } from "./pages/StoryboardView";
import { StoryInput } from "./pages/StoryInput";
import { useMangaStore } from "./store/mangaStore";

export default function App() {
  const { currentStep, setCurrentStep, storyboard } = useMangaStore();

  const handleStepClick = (n: number) => {
    // 生成済みの場合のみ前のステップに戻れる
    if (n <= currentStep) setCurrentStep(n);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Toaster position="top-right" />

      {/* ヘッダー */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-20 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🎌</span>
              <div>
                <h1 className="text-lg font-bold text-gray-900 leading-none">
                  AI漫画生成アプリ
                </h1>
                <p className="text-xs text-gray-500 mt-0.5">
                  {storyboard ? `「${storyboard.title}」` : "テキストから漫画ページを自動生成"}
                </p>
              </div>
            </div>
            <StepIndicator current={currentStep} onClickStep={handleStepClick} />
          </div>
        </div>
      </header>

      {/* メインコンテンツ */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {currentStep === 0 && <StoryInput />}
        {currentStep === 1 && <StoryboardView />}
        {currentStep === 2 && <ImageUpload />}
        {currentStep === 3 && <Preview />}
        {currentStep === 4 && <Export />}
      </main>

      {/* フッター */}
      <footer className="mt-16 border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 py-4 text-center text-xs text-gray-400">
          AI漫画生成アプリ MVP v0.1 — Powered by Claude (Anthropic) + FastAPI + React
        </div>
      </footer>
    </div>
  );
}
