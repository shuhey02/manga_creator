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
│   └── .env / .env.example               # ANTHROPIC_API_KEY 等
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
- **3-A** キャラクター一貫性: リファレンス画像、`character_locked` フラグ、seed 管理
- **3-B** 画像生成 API 直結: `backend/app/services/image_gen/{base,dalle,sd_local}.py` プラガブル設計（着手は Phase 1 完了後に判断）
- **3-C** 縦書き吹き出し: Pillow で縦描画関数、`bubble.orientation` フィールド追加

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

### Phase 1〜2 で追加予定
- `POST /api/storyboard/session/{id}/regenerate-panel`
- `GET /api/sessions`
- `DELETE /api/sessions/{id}`

---

## 7. データ規約

- **ページ画像**: 1240 × 1754 px（A4 @ 150dpi）, PNG, RGB
- **layout / position**: 0〜100 のパーセンテージ
- **アップロード命名**: `p{page}_panel{panel}.{jpg|jpeg|png|webp}`
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
