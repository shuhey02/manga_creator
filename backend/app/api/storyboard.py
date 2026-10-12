"""
Storyboard API: ストーリーからネームを生成するエンドポイント
"""
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models.schemas import StoryboardRequest, StoryboardResponse
from ..services.llm_service import generate_storyboard

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
            detail="ANTHROPIC_API_KEY が設定されていません。backend/.env を確認してください。",
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

    # セッションディレクトリを作成してネームを保存
    session_id = str(uuid.uuid4())
    session_dir = settings.output_path / session_id
    (session_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (session_dir / "pages").mkdir(parents=True, exist_ok=True)

    storyboard_path = session_dir / "storyboard.json"
    storyboard_path.write_text(
        storyboard.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return StoryboardResponse(session_id=session_id, storyboard=storyboard)


@router.get("/session/{session_id}", response_model=StoryboardResponse)
async def get_session(session_id: str):
    """保存済みセッションのネームを取得する"""
    storyboard_path = settings.output_path / session_id / "storyboard.json"
    if not storyboard_path.exists():
        raise HTTPException(status_code=404, detail="セッションが見つかりません。")

    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    from ..models.schemas import Storyboard
    storyboard = Storyboard(**data)
    return StoryboardResponse(session_id=session_id, storyboard=storyboard)


@router.put("/session/{session_id}")
async def update_session(session_id: str, storyboard_data: dict):
    """編集済みネームを上書き保存する"""
    session_dir = settings.output_path / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="セッションが見つかりません。")

    storyboard_path = session_dir / "storyboard.json"
    import json as _json
    storyboard_path.write_text(
        _json.dumps(storyboard_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"status": "saved"}
