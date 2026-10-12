"""
Storyboard API: ストーリーからネームを生成するエンドポイント
"""
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models.schemas import Storyboard, StoryboardRequest, StoryboardResponse
from ..services.llm_service import generate_storyboard
from ..services.session_store import (
    SessionNotFoundError,
    create_session,
    load_storyboard,
    save_storyboard,
)

router = APIRouter(prefix="/api/storyboard", tags=["storyboard"])


@router.post("/generate", response_model=StoryboardResponse)
async def generate(request: StoryboardRequest):
    """
    ストーリーテキストからネームを生成する。

    - Claude API を呼び出してコマ割り・セリフ・プロンプト等を生成
    - セッションIDを発行してサーバー側に保存
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY が設定されていません。backend/.env を確認するか、"
            "Claude Code の MCP ツールでネームを作ってください。",
        )

    try:
        storyboard = await generate_storyboard(
            title=request.title,
            story=request.story,
            genre=request.genre,
            style=request.style,
            num_pages=request.num_pages,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ネーム生成中にエラーが発生しました: {e}")

    session_id = create_session(storyboard)
    return StoryboardResponse(session_id=session_id, storyboard=storyboard)


@router.post("/import", response_model=StoryboardResponse)
async def import_storyboard(storyboard: Storyboard):
    """外部（Claude Code・手書き JSON 等）で作ったネームから新しいセッションを作る"""
    session_id = create_session(storyboard)
    return StoryboardResponse(session_id=session_id, storyboard=storyboard)


@router.get("/session/{session_id}", response_model=StoryboardResponse)
async def get_session(session_id: str):
    """保存済みセッションのネームを取得する"""
    try:
        storyboard = load_storyboard(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="セッションが見つかりません。")
    return StoryboardResponse(session_id=session_id, storyboard=storyboard)


@router.put("/session/{session_id}")
async def update_session(session_id: str, storyboard: Storyboard):
    """編集済みネームを上書き保存する"""
    try:
        load_storyboard(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="セッションが見つかりません。")
    save_storyboard(session_id, storyboard)
    return {"status": "saved"}
