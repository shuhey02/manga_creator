"""
API 共通: セッションの存在確認（session_id は UUID の標準形だけを受け付ける）
"""
from pathlib import Path

from fastapi import HTTPException

from ..models.schemas import Storyboard
from ..services.session_store import SessionNotFoundError, load_storyboard, session_dir

_NOT_FOUND = "セッションが見つかりません。"


def existing_session_dir(session_id: str) -> Path:
    try:
        directory = session_dir(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    if not (directory / "storyboard.json").exists():
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return directory


def load_session_storyboard(session_id: str) -> Storyboard:
    try:
        return load_storyboard(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
