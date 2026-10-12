# 🎌 AI漫画生成アプリ MVP

テキストのストーリーを入力するだけで、**コマ割り・セリフ・画像プロンプト・吹き出し付きの漫画ページ**を生成するWebアプリケーション。

## 機能

| 機能 | 説明 |
|------|------|
| ネーム自動生成 | Claude AI がストーリーからコマ割り・構図・セリフ・効果音を生成 |
| 画像プロンプト出力 | 各コマのStable Diffusion/DALL-E向けプロンプト（英日両語）を生成 |
| **AI ページ生成** | ChatGPT（gpt-image-2）がコマ割りガイドに沿って1ページを丸ごと描く（Codex CLI 経由・ChatGPT サブスク枠） |
| キャラ参照シート | 登場キャラ全員の設定画を先に作り、ページ間で顔・服装をそろえる |
| MCP サーバー | Claude Code / Codex からネーム登録〜生成〜書き出しをツールとして呼べる |
| 手動画像アップロード | 外部生成した画像をコマ単位でアップロード |
| ページ自動合成 | コマ配置・吹き出し・効果音をPillowで自動合成。セリフは**縦書き**（吹き出しの `orientation`: auto / vertical / horizontal）。効果音も縦書き（`sound_effect_orientation`） |
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

- AI 画像生成を使う場合: [Codex CLI](https://github.com/openai/codex) v0.123 以上を ChatGPT Plus/Pro アカウントで `codex login` 済みであること（API キー不要）
- ANTHROPIC_API_KEY は Web 画面でネームを自動生成するときだけ必要。Claude Code で作ったネーム JSON を読み込めば無くても使える

---

## AI 画像生成のしくみ

```
ネーム(JSON) ─▶ layout_guide: コマ枠＋吹き出し予定域(灰色)の下絵 1024x1536
             ─▶ page_prompt : 各コマの構図・人物・背景を1ページ分のプロンプトに（文字は描かせない）
             ─▶ codex exec '$imagegen' --image 下絵 --image キャラ参照シート  （gpt-image-2）
             ─▶ panel_detect: 実際に描かれたコマ枠を白い溝から測り直す（数%ずれるため）
             ─▶ image_assembler: 測った枠を基準に吹き出し・効果音を重ねて A4 に
```

- 1枚あたり約3〜4分。ChatGPT の利用枠を使うので、同時実行は1つに制限している
- セリフを画像に描かせないのは、小さい日本語が崩れやすく修正も効かないため
- ChatGPT の利用枠の上限に達すると、画像管理画面に再開の目安時刻つきの案内を出し、「全ページを生成」はそこで止まる
- 追加の環境変数（`backend/.env`）: `IMAGE_PROVIDER=codex`、`CODEX_BIN=codex`、`IMAGE_TIMEOUT_SEC=600`、`CORS_ORIGINS`

### Claude Code から使う（MCP）

リポジトリ直下の `.mcp.json` に `manga-app` サーバーを登録してある。manga-app で Claude Code を開き、
サーバーの有効化を承認すると次のツールが使える（`backend/venv` を作成済みであること）。

| ツール | 内容 |
|---|---|
| `storyboard_guidelines` | ネーム JSON のルールとスキーマ |
| `create_session` | ネーム JSON からセッションを作る（Claude Code 自身がネームを書けるので API キー不要） |
| `create_storyboard_with_claude_api` | Anthropic API でネームを自動生成 |
| `generate_character_sheet` / `generate_page_image` | ChatGPT で参照シート・ページを描く（返る画像パスを Read で確認できる） |
| `assemble_pages` / `assemble_page_image` / `export_manga` | 吹き出しを重ねて完成ページ化（全ページ／1ページ）、PDF / CBZ に書き出し |
| `update_panel` / `update_speech_bubble` / `add_speech_bubble` / `remove_speech_bubble` / `update_character` | 既存のネームを部分的に直す。文字まわりは合成し直すだけで反映（数秒・無料）、絵に関わる項目は `needs_redraw` で知らせる |
| `redraw_panel` | 今のコマを切り出して参照に渡し、1コマだけ描き直して元の枠へ貼る（ほかのコマは1画素も変えない） |
| `list_page_versions` / `use_page_version` | 描き直した絵は `page_001_v2.png` のように版として残り、いつでも前の版に戻せる |

### 微修正の進め方

1. ネーム（文字・コマ割り）を先に固める。ここまでは何度直しても無料
2. キャラ参照シートを1枚作って確認する
3. ページの絵を生成する
4. セリフ・吹き出し・効果音の修正は、絵を描き直さず `assemble_page_image` で合成し直す
5. 1コマだけ絵がおかしいときは `redraw_panel`（例:「目を見開いて驚いた表情に」）。気に入らなければ `use_page_version` で戻す

Web 画面でも、画像管理のページカードから版の切り替えと「1コマだけ描き直す」ができる。

例:「〇〇という話で2ページの漫画を作って」と頼むと、ネーム作成→生成→合成→PDF まで進む。
Codex から使う場合は `~/.codex/config.toml` に同じコマンドを `[mcp_servers.manga-app]` として登録する。

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
# backend/.env を作り、下の例を参考に ANTHROPIC_API_KEY 等を設定
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
- 「AI でページを描く」で、キャラ参照シート（任意）→ 各ページを生成。気に入らなければ「描き直す」
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
│   └── .env                ← 自分で作る（git 管理外）
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
| POST | `/api/storyboard/import` | ネーム JSON からセッション作成 |
| POST | `/api/generation/characters` | キャラ参照シート生成ジョブ開始 |
| POST | `/api/generation/page` | ページ画像生成ジョブ開始 |
| GET | `/api/generation/job/{job_id}` | 生成ジョブの状態 |
| POST | `/api/export/generate` | PDF/CBZ生成 |
| GET | `/api/export/download/{id}/{file}` | ファイルダウンロード |

---

## 出力データ形式

### セッションディレクトリ構造
```
backend/output/{session-uuid}/
├── storyboard.json     ← 生成されたネーム（JSON）
├── characters/         ← キャラ参照シート（AI 生成）
├── guides/             ← 画像生成 AI に渡したコマ割りガイド
├── generated/          ← AI 生成ページ（文字なし）と使ったプロンプト
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
- 装飾フォント
- クラウドデプロイ・SaaS化
