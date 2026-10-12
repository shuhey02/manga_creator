export function CopyrightNotice() {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
      <div className="flex gap-2">
        <span className="text-lg flex-shrink-0">⚠️</span>
        <div className="space-y-1">
          <p className="font-bold">商用利用に関する注意事項</p>
          <ul className="list-disc list-inside space-y-0.5 text-amber-700">
            <li>
              画像生成AIで作成した画像を商用利用する場合は、使用する AIサービスの利用規約を必ず確認してください。
            </li>
            <li>
              生成されたプロンプト・テキストは Claude (Anthropic) の利用規約に従います。
              商用利用の可否は{" "}
              <a
                href="https://www.anthropic.com/legal/consumer-terms"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-amber-900"
              >
                Anthropic利用規約
              </a>{" "}
              をご確認ください。
            </li>
            <li>
              入力ストーリーに既存著作物（キャラクター名・固有名詞等）を含む場合、
              著作権侵害にならないようご注意ください。
            </li>
            <li>
              本アプリはMVP（実験的実装）です。生成物の著作権・品質については利用者ご自身の責任でご確認ください。
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
