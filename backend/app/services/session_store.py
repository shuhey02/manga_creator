"""
セッション（backend/output/{session_id}/）の読み書き
"""
import uuid
from pathlib import Path

from ..config import settings
from ..models.schemas import Storyboard


class SessionNotFoundError(LookupError):
    pass


def session_dir(session_id: str) -> Path:
    # session_id はパスに使うので UUID 以外を受け付けない（../ などの混入防止）
    # 標準形以外（"{...}"・"urn:uuid:..."・ハイフンなし等）も UUID として解釈できてしまうので、
    # 解釈し直した文字列と一致するものだけを通す
    try:
        canonical = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError) as e:
        raise SessionNotFoundError(session_id) from e
    if canonical != session_id:
        raise SessionNotFoundError(session_id)
    return settings.output_path / session_id


def create_session(storyboard: Storyboard) -> str:
    session_id = str(uuid.uuid4())
    directory = settings.output_path / session_id
    (directory / "uploads").mkdir(parents=True, exist_ok=True)
    (directory / "pages").mkdir(parents=True, exist_ok=True)
    save_storyboard(session_id, storyboard)
    return session_id


def load_storyboard(session_id: str) -> Storyboard:
    path = session_dir(session_id) / "storyboard.json"
    if not path.exists():
        raise SessionNotFoundError(session_id)
    return Storyboard.model_validate_json(path.read_text(encoding="utf-8"))


def save_storyboard(session_id: str, storyboard: Storyboard) -> None:
    path = session_dir(session_id) / "storyboard.json"
    path.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")


def output_url(session_id: str, relative: str | Path) -> str:
    return f"/output/{session_id}/{Path(relative).as_posix()}"
