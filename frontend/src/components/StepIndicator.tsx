interface Step {
  label: string;
  icon: string;
}

const STEPS: Step[] = [
  { label: "ストーリー入力", icon: "✍️" },
  { label: "ネーム確認", icon: "📋" },
  { label: "画像管理", icon: "🖼️" },
  { label: "プレビュー", icon: "👁️" },
  { label: "エクスポート", icon: "📦" },
];

interface Props {
  current: number;
  onClickStep?: (n: number) => void;
}

export function StepIndicator({ current, onClickStep }: Props) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1">
      {STEPS.map((step, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={i} className="flex items-center">
            <button
              onClick={() => onClickStep?.(i)}
              disabled={i > current}
              className={[
                "flex flex-col items-center px-3 py-2 rounded-lg transition-colors min-w-[80px]",
                active
                  ? "bg-manga-600 text-white shadow-md"
                  : done
                  ? "bg-manga-100 text-manga-700 cursor-pointer hover:bg-manga-200"
                  : "bg-gray-100 text-gray-400 cursor-not-allowed",
              ].join(" ")}
            >
              <span className="text-lg">{step.icon}</span>
              <span className="text-xs font-medium mt-0.5 whitespace-nowrap">{step.label}</span>
            </button>
            {i < STEPS.length - 1 && (
              <div
                className={[
                  "w-6 h-0.5 mx-1 flex-shrink-0",
                  i < current ? "bg-manga-400" : "bg-gray-200",
                ].join(" ")}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
