# manga-app プロジェクトメモリ

このファイルは Claude（Cowork / Claude Code）がセッションをまたいで参照するためのプロジェクト記憶です。
新しいセッション開始時に必ずこのファイルを読み、現状・方針・規約を踏まえてから作業を始めてください。

---

## 1. 実装ポリシー

- **MVP 段階の実装は Claude Code（Sonnet）で行う**（コスト削減のため）
- Cowork（Opus）は **設計・リプラン・要件整理・レビュー** に使う
- 実装タスクをユーザーから依頼された場合、規模が大きいものは
  「Claude Code 側でやる前提のタスク分解」を提示してから着手する
- 計画変更・大きな設計判断は Cowork 側に戻して合意してから進める

---

## 2. プロジェクト概要

**AI漫画生成アプリ MVP**：テキストストーリーから漫画ページを自動生成する Web アプリ。

### 技術スタック
- バックエンド: FastAPI + Anthropic SDK + Pillow + ReportLab（A4 / 150dpi）
- フロントエンド: React 18 + Vite + Zustand + Tailwind + Axios
- LLM: Claude Sonnet 4.6（`claude-sonnet-4-6`）
- ストレージ: ローカルファイルシステム `backend/output/{session_uuid}/`

### 5ステップ動線
ストーリー入力 → ネーム確認 → 画像管理 → プレビュー → エクスポート（PDF / CBZ）

---

## 3. ディレクトリ構造（重要ファイル）

```
manga-app/
├── backend/
│   ├── app/
│   │   ├── main.py                       # FastAPI エントリ
│   │   ├── config.py                     # Settings（pydantic-settings）
│   │   ├── models/schemas.py             # Pydantic モデル
│   │   ├── services/
│   │   │   ├── llm_service.py            # Claude API 呼び出し
│   │   │   ├── image_assembler.py        # Pillow ページ合成
│   │   │   └── export_service.py         # PDF / CBZ 生成
│   │   └── api/
│   │       ├── storyboard.py             # ネーム生成 API
│   │       ├── assembly.py               # 画像 UP・合成 API
│   │       └── export_api.py             # エクスポート API
│   ├── output/                           # セッション別出力（gitignore）
│   ├── requirements.txt
│   └── .env                              # ANTHROPIC_API_KEY 等（git 管理外）
└── frontend/
    └── src/
        ├── App.tsx                       # 5ステップウィザード
        ├── store/mangaStore.ts           # Zustand
        ├── api/client.ts                 # Axios
        ├── types/manga.ts
        ├── components/{StepIndicator,PanelLayoutPreview,CopyrightNotice}.tsx
        └── pages/{StoryInput,StoryboardView,ImageUpload,Preview,Export}.tsx
```

---

## 4. 既知のバグ・地雷（Phase 0 で対処）

| # | 場所 | 内容 |
|---|------|------|
| 0-1 | `backend/app/services/llm_service.py` | LLM の JSON 失敗時にリトライ／自己修復なし → 1 回失敗で全工程ロスト |
| 0-2 | `backend/app/config.py` | `Settings` に `extra="ignore"` がない → `.env` の余分なキーで起動失敗の懸念 |
| 0-3 | `frontend/src/pages/ImageUpload.tsx` / `Export.tsx` | `exportManga` の不要 import、export 完了前に `setCurrentStep(4)` |
| 0-4 | `backend/app/main.py` | CORS が `localhost:5173` ハードコード |
| 0-5 | `backend/app/services/image_assembler.py` | フォントが Windows パス前提。同梱フォントなし → デプロイ時にプレースホルダー化 |
| 0-6 | フロント全般 | `error` ステートと `toast.error` が混在 |

---

## 5. アップグレード計画（合意済み・最優先テーマ＝UX）

### Phase 0: バグ修正・地雷除去（3〜5日）
上記の 0-1〜0-6 を全て対応。

### Phase 1: 編集体験のコア（2〜3週間・最優先）
- **1-A** ネームのインライン編集（セリフ・効果音・吹き出し・プロンプト）＋ debounced 自動保存
- **1-B** コマの D&D 並び替え（`@dnd-kit/sortable`）＋ レイアウトリサイズ ＋ レイアウト検証 (`backend/app/services/layout_validator.py` 新設)
- **1-C** 吹き出しの位置をミニキャンバスでドラッグ編集
- **1-D** 1コマ単位のネーム再生成（`POST /api/storyboard/session/{id}/regenerate-panel` 新設）
- **1-E** クライアント画像圧縮（`browser-image-compression`、1240px / WebP）＋ 複数ファイル一括ドロップ＋差し替え UI

### Phase 2: セッション管理（1〜2週間）
- セッション一覧画面（`GET /api/sessions`）
- `react-router` 導入し直リンク・リロード対応（`/session/:id/...`）
- localStorage に直近 10 セッション
- オートセーブインジケータ
- セッション削除 API
- エクスポート履歴の再 DL

### Phase 3: 品質向上（2〜4週間）
- **3-A** キャラクター一貫性: ✅ キャラ参照シート（全員を1枚に描き、ページ生成時に参照画像として渡す）。`character_locked` / seed は未着手
- **3-B** 画像生成直結: ✅ `services/image_gen/codex_cli.py`（Codex CLI の `$imagegen` = gpt-image-2、ChatGPT サブスク枠）。
  方式は「ページ一括＋コマ割りガイド」。生成後に `panel_detect.py` で実際の枠を測り直し、吹き出しはその枠基準で重ねる。
  他プロバイダは `image_gen/base.py` の `ImageGenerator` を実装して `create_image_generator` に足す
- **3-D** MCP サーバー: ✅ `backend/mcp_server.py`（`.mcp.json` で登録）。Web API と同じ `services/generation_service.py` を呼ぶ
- **3-C** 縦書き吹き出し: ✅ `services/vertical_text.py`（libraqm が無いので1文字ずつ配置。句読点は右上、長音・括弧は回転、行頭禁則はぶら下げ）。
  `SpeechBubble.orientation`（auto / vertical / horizontal、auto は縦長なら縦書き）。ネーム生成の指示も縦長・縦書きに変更
  効果音も縦書き（`Panel.sound_effect_orientation`、既定 vertical）。白抜き＋黒縁で右端に1列、吹き出しと重なるなら左端

### Phase 4: 本番化基盤（必要時）
Docker、Postgres + SQLAlchemy + Alembic、pytest / Vitest / GitHub Actions、認証、Railway / Fly.io デプロイ

### 推奨スケジュール（直近2週間）
- Week 1: Phase 0 全部 + Phase 1-A
- Week 2: Phase 1-B + Phase 1-E

---

## 6. 重要な API エンドポイント

| メソッド | パス | 用途 |
|---------|------|------|
| POST | `/api/storyboard/generate` | ネーム生成 |
| GET  | `/api/storyboard/session/{id}` | セッション取得 |
| PUT  | `/api/storyboard/session/{id}` | ネーム更新保存（Phase 1-A で本格活用） |
| POST | `/api/assembly/upload-image` | パネル画像アップロード |
| POST | `/api/assembly/assemble-page` | 1ページ合成 |
| POST | `/api/assembly/assemble-all` | 全ページ合成 |
| GET  | `/api/assembly/status/{id}` | アップロード状況 |
| POST | `/api/export/generate` | PDF / CBZ 生成 |
| GET  | `/api/export/download/{id}/{file}` | DL |
| POST | `/api/storyboard/import` | ネーム JSON からセッション作成 |
| POST | `/api/generation/characters` / `/api/generation/page` | 生成ジョブ開始（メモリ上のジョブ） |
| GET  | `/api/generation/job/{id}` | ジョブ状態 |

### Phase 1〜2 で追加予定
- `POST /api/storyboard/session/{id}/regenerate-panel`
- `GET /api/sessions`
- `DELETE /api/sessions/{id}`

---

## 7. データ規約

- **ページ画像**: 1240 × 1754 px（A4 @ 150dpi）, PNG, RGB
- **layout / position**: 0〜100 のパーセンテージ
- **アップロード命名**: `p{page}_panel{panel}.{jpg|jpeg|png|webp}`
- **AI 生成**: ガイド・生成画像は 1024 × 1536。`Panel.rendered_layout` は生成画像全体に対する %（`layout` はページ内容域に対する %）
- **テスト**: `backend/venv/Scripts/python -m pytest backend/tests`
- **CBZ メタデータ**: `Manga: YesAndRightToLeft`（右綴じ）

---

## 8. コーディング規約

- バックエンド: Python 3.11+ / 型ヒント必須 / Pydantic v2
- フロント: TypeScript strict / 関数コンポーネント / Tailwind ユーティリティ中心
- 状態管理は Zustand に集約（コンポーネント内 useState は UI ローカルのみ）
- API クライアントは `frontend/src/api/client.ts` に集約
- 新機能の Pydantic モデルは `backend/app/models/schemas.py` に追加
- 著作権・商用利用注意は `CopyrightNotice` コンポーネントで一元化

---

## 9. 作業時のチェックリスト（Claude Code 向け）

実装着手前に必ず確認:
- [ ] 該当 Phase のスコープ内か（スコープ外なら Cowork に戻す）
- [ ] 既存 API・型定義を再利用できないか
- [ ] バックエンド変更時は対応する `frontend/src/types/manga.ts` と `api/client.ts` を更新
- [ ] LLM プロンプト変更時は `sample/storyboard_output.json` で動作確認
- [ ] 完了後はこの CLAUDE.md の Phase 進捗を更新
