"""
Export API: PDF / Kindle用ZIPを生成してダウンロードするエンドポイント
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..models.schemas import ExportRequest, ExportResponse
from ..services.export_service import create_kindle_zip, create_pdf
from .deps import existing_session_dir, load_session_storyboard

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/generate", response_model=ExportResponse)
async def generate_export(request: ExportRequest):
    """PDFまたはCBZ(Kindle用ZIP)を生成してダウンロードURLを返す"""
    session_dir = existing_session_dir(request.session_id)
    storyboard = load_session_storyboard(request.session_id)

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

    file_path = existing_session_dir(session_id) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません。先にエクスポートを生成してください。")

    media_type = "application/pdf" if filename.endswith(".pdf") else "application/zip"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )
