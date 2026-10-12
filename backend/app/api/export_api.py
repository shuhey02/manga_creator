"""
Export API: PDF / Kindle用ZIPを生成してダウンロードするエンドポイント
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..models.schemas import ExportRequest, ExportResponse, Storyboard
from ..services.export_service import create_kindle_zip, create_pdf

router = APIRouter(prefix="/api/export", tags=["export"])


def _load_storyboard(session_id: str) -> Storyboard:
    path = settings.output_path / session_id / "storyboard.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="セッションが見つかりません。")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Storyboard(**data)


@router.post("/generate", response_model=ExportResponse)
async def generate_export(request: ExportRequest):
    """PDFまたはCBZ(Kindle用ZIP)を生成してダウンロードURLを返す"""
    storyboard = _load_storyboard(request.session_id)
    session_dir = settings.output_path / request.session_id

    try:
        if request.format == "pdf":
            out_path = create_pdf(session_dir, storyboard)
            filename = "manga.pdf"
        else:
            out_path = create_kindle_zip(session_dir, storyboard)
            filename = "manga_kindle.cbz"
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"エクスポートエラー: {e}")

    download_url = f"/api/export/download/{request.session_id}/{filename}"
    return ExportResponse(
        session_id=request.session_id,
        download_url=download_url,
        filename=filename,
    )


@router.get("/download/{session_id}/{filename}")
async def download_export(session_id: str, filename: str):
    """生成済みエクスポートファイルをダウンロードする"""
    # ファイル名のサニタイズ（パストラバーサル防止）
    safe_names = {"manga.pdf", "manga_kindle.cbz"}
    if filename not in safe_names:
        raise HTTPException(status_code=400, detail="不正なファイル名です。")

    file_path = settings.output_path / session_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません。先にエクスポートを生成してください。")

    media_type = "application/pdf" if filename.endswith(".pdf") else "application/zip"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )
