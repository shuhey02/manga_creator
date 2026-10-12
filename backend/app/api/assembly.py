"""
Assembly API: 画像アップロード・ページ合成エンドポイント
"""
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..models.schemas import (
    AssembleAllRequest,
    AssembleAllResponse,
    AssemblePageRequest,
    AssemblePageResponse,
    UploadImageResponse,
)
from ..services.image_assembler import assemble_page as _assemble_page
from .deps import existing_session_dir, load_session_storyboard

router = APIRouter(prefix="/api/assembly", tags=["assembly"])


@router.post("/upload-image", response_model=UploadImageResponse)
async def upload_image(
    session_id: str = Form(...),
    page_number: int = Form(...),
    panel_number: int = Form(...),
    image: UploadFile = File(...),
):
    """
    パネル画像をアップロードする。
    同じ session_id / page / panel の場合は上書き。
    """
    session_dir = existing_session_dir(session_id)

    # 拡張子を取得（安全化）
    filename = image.filename or "image.jpg"
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        ext = "jpg"

    save_name = f"p{page_number}_panel{panel_number}.{ext}"
    save_path = session_dir / "uploads" / save_name

    contents = await image.read()
    save_path.write_bytes(contents)

    image_url = f"/output/{session_id}/uploads/{save_name}"
    return UploadImageResponse(
        session_id=session_id,
        page_number=page_number,
        panel_number=panel_number,
        image_url=image_url,
    )


@router.post("/assemble-page", response_model=AssemblePageResponse)
async def assemble_page_endpoint(request: AssemblePageRequest):
    """指定ページを合成する"""
    session_dir = existing_session_dir(request.session_id)
    storyboard = load_session_storyboard(request.session_id)

    page_data = next(
        (p for p in storyboard.pages if p.page_number == request.page_number),
        None,
    )
    if page_data is None:
        raise HTTPException(status_code=404, detail=f"ページ {request.page_number} が見つかりません。")

    try:
        out_path = _assemble_page(session_dir, page_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ページ合成エラー: {e}")

    image_url = f"/output/{request.session_id}/pages/{out_path.name}"
    return AssemblePageResponse(
        session_id=request.session_id,
        page_number=request.page_number,
        image_url=image_url,
    )


@router.post("/assemble-all", response_model=AssembleAllResponse)
async def assemble_all(request: AssembleAllRequest):
    """全ページを合成する"""
    session_dir = existing_session_dir(request.session_id)
    storyboard = load_session_storyboard(request.session_id)

    results = []
    errors = []

    for page_data in storyboard.pages:
        try:
            out_path = _assemble_page(session_dir, page_data)
            image_url = f"/output/{request.session_id}/pages/{out_path.name}"
            results.append(
                AssemblePageResponse(
                    session_id=request.session_id,
                    page_number=page_data.page_number,
                    image_url=image_url,
                )
            )
        except Exception as e:
            errors.append(f"ページ{page_data.page_number}: {e}")

    if errors and not results:
        raise HTTPException(status_code=500, detail="全ページの合成に失敗しました: " + "; ".join(errors))

    return AssembleAllResponse(session_id=request.session_id, pages=results)


@router.get("/status/{session_id}")
async def get_upload_status(session_id: str):
    """アップロード済み画像の一覧を返す"""
    uploads_dir = existing_session_dir(session_id) / "uploads"
    if not uploads_dir.exists():
        return {"uploaded": []}

    uploaded = [f.name for f in uploads_dir.iterdir() if f.is_file()]
    return {"uploaded": uploaded}
