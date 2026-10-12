# 🎌 AI漫画生成アプリ MVP

テキストのストーリーを入力するだけで、**コマ割り・セリフ・画像プロンプト・吹き出し付きの漫画ページ**を生成するWebアプリケーション。

## 機能

| 機能 | 説明 |
|------|------|
| ネーム自動生成 | Claude AI がストーリーからコマ割り・構図・セリフ・効果音を生成 |
| 画像プロンプト出力 | 各コマのStable Diffusion/DALL-E向けプロンプト（英日両語）を生成 |
| 手動画像アップロード | 外部生成した画像をコマ単位でアップロード |
| ページ自動合成 | コマ配置・吹き出し・効果音をPillowで自動合成 |
| PDF/CBZエクスポート | Kindle用CBZ（コミックアーカイブ）またはPDFとして出力 |

## スクリーンショット

```
① ストーリー入力 → ② ネーム確認 → ③ 画像管理 → ④ プレビュー → ⑤ エクスポート
```

---

## 必要環境

- Python 3.11+
- Node.js 18+
- [Anthropic APIキー](https://console.anthropic.com/)

---

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <your-repo-url>
cd manga-app
```

### 2. バックエンドのセットアップ

```bash
cd backend

# 仮想環境作成（推奨）
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

# 依存パッケージのインストール
pip install -r requirements.txt

# 環境変数の設定
cp .env.example .env
# .env を編集して ANTHROPIC_API_KEY を設定
```

`.env` ファイル:
```env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxx
CLAUDE_MODEL=claude-sonnet-4-6
HOST=127.0.0.1
PORT=8000
OUTPUT_DIR=output
```

### 3. フロントエンドのセットアップ

```bash
cd frontend
npm install
```

---

## 起動方法

### バックエンド起動（ターミナル1）

```bash
cd backend
# 仮想環境を有効化している状態で
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### フロントエンド起動（ターミナル2）

```bash
cd frontend
npm run dev
```

### アクセス

- **アプリ**: http://localhost:5173
- **API ドキュメント**: http://localhost:8000/docs

---

## 使い方

### ステップ1: ストーリー入力
- タイトルとストーリーを入力
- ジャンル・スタイル・ページ数を設定
- 「ネームを生成する」をクリック（Claude APIが呼び出されます）

### ステップ2: ネーム確認
- 生成されたページ・コマ割りを確認
- 各コマの構図・セリフ・プロンプトを確認
- プロンプトをコピーして画像生成AIで画像を生成

### ステップ3: 画像管理
- 各コマに画像をアップロード（JPG/PNG/WebP）
- 未アップロードのコマはプレースホルダーで合成されます
- 「ページを合成する」をクリック

### ステップ4: プレビュー
- 合成済みページを確認
- 個別ページのダウンロードも可能

### ステップ5: エクスポート
- **PDF**: 印刷・電子書籍向け
- **CBZ**: Kindle/コミックビューアー向け

---

## ディレクトリ構造

```
manga-app/
├── backend/                    # FastAPI バックエンド
│   ├── app/
│   │   ├── main.py             # アプリエントリポイント
│   │   ├── config.py           # 設定（.envから読み込み）
│   │   ├── models/
│   │   │   └── schemas.py      # Pydanticモデル
│   │   ├── services/
│   │   │   ├── llm_service.py      # Claude API呼び出し
│   │   │   ├── image_assembler.py  # Pillowページ合成
│   │   │   └── export_service.py   # PDF/CBZ生成
│   │   └── api/
│   │       ├── storyboard.py   # ネーム生成API
│   │       ├── assembly.py     # 画像アップロード・合成API
│   │       └── export_api.py   # エクスポートAPI
│   ├── output/                 # セッション別出力ディレクトリ（gitignore）
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                   # React + TypeScript + Vite
│   └── src/
│       ├── App.tsx             # メインアプリ（5ステップウィザード）
│       ├── types/manga.ts      # 型定義
│       ├── api/client.ts       # APIクライアント
│       ├── store/mangaStore.ts # Zustand状態管理
│       ├── components/
│       │   ├── StepIndicator.tsx       # ステップ表示
│       │   ├── PanelLayoutPreview.tsx  # コマ割りプレビュー
│       │   └── CopyrightNotice.tsx     # 著作権注意表示
│       └── pages/
│           ├── StoryInput.tsx      # ストーリー入力
│           ├── StoryboardView.tsx  # ネーム確認
│           ├── ImageUpload.tsx     # 画像管理
│           ├── Preview.tsx         # ページプレビュー
│           └── Export.tsx          # エクスポート
│
├── sample/
│   ├── story_input.txt         # サンプルストーリー入力
│   └── storyboard_output.json  # サンプルネーム出力
│
├── docs/
│   └── roadmap.md              # 今後の拡張計画
└── README.md
```

---

## API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/storyboard/generate` | ネーム生成 |
| GET | `/api/storyboard/session/{id}` | セッション取得 |
| PUT | `/api/storyboard/session/{id}` | ネーム更新保存 |
| POST | `/api/assembly/upload-image` | パネル画像アップロード |
| POST | `/api/assembly/assemble-page` | 1ページ合成 |
| POST | `/api/assembly/assemble-all` | 全ページ合成 |
| GET | `/api/assembly/status/{id}` | アップロード状況確認 |
| POST | `/api/export/generate` | PDF/CBZ生成 |
| GET | `/api/export/download/{id}/{file}` | ファイルダウンロード |

---

## 出力データ形式

### セッションディレクトリ構造
```
backend/output/{session-uuid}/
├── storyboard.json     ← 生成されたネーム（JSON）
├── uploads/            ← アップロードされたパネル画像
│   ├── p1_panel1.jpg
│   ├── p1_panel2.jpg
│   └── ...
└── pages/              ← 合成済みページ画像
    ├── page_001.png
    ├── page_002.png
    └── ...
```

### ページ画像仕様
- サイズ: 1240 × 1754 px (A4 @ 150dpi)
- フォーマット: PNG
- 色空間: RGB

---

## 注意事項・商用利用について

> ⚠️ 本アプリで生成した画像・テキストを商用利用する際は、以下を確認してください:
>
> - **Claude (Anthropic)**: [利用規約](https://www.anthropic.com/legal/consumer-terms) を確認
> - **画像生成AI**: 使用するサービス（Stable Diffusion, DALL-E等）各サービスの規約を確認
> - **既存著作物**: 既存キャラクター・作品名等の入力は著作権侵害になる可能性があります

---

## 今後の拡張計画

詳細は [docs/roadmap.md](docs/roadmap.md) を参照。

主な予定:
- Stable Diffusion / DALL-E API直接連携
- キャラ固定LoRA/IP-Adapter対応
- 縦書きテキスト・装飾フォント
- クラウドデプロイ・SaaS化
