"""
AI漫画生成アプリ - FastAPI バックエンド
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.assembly import router as assembly_router
from .api.export_api import router as export_router
from .api.generation import router as generation_router
from .api.storyboard import router as storyboard_router
from .config import settings

# ─── アプリ初期化 ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI漫画生成アプリ MVP",
    description="テキストストーリーから漫画ページを生成するシステム",
    version="0.1.0",
)

# ─── CORS設定（開発環境用） ───────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── ルーター登録 ─────────────────────────────────────────────────────────────
app.include_router(storyboard_router)
app.include_router(assembly_router)
app.include_router(export_router)
app.include_router(generation_router)

# ─── 静的ファイル配信（合成済みページ画像・エクスポートファイル） ─────────────
output_dir = settings.output_path
output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")


@app.get("/")
async def root():
    return {
        "message": "AI漫画生成アプリ MVP",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "api_key_set": bool(settings.anthropic_api_key),
        "image_provider": settings.image_provider,
    }
