"""
manga-app の MCP サーバー（stdio）

Claude Code / Codex から、ネーム登録 → キャラ参照シート生成 → ページ画像生成 →
吹き出し合成 → PDF/CBZ 書き出しをツールとして呼べるようにする。
Web UI と同じ backend/output/ のセッションを読み書きするので、途中から UI で続きもできる。

起動: backend/venv/Scripts/python backend/mcp_server.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from app.config import settings  # noqa: E402
from app.models.schemas import Storyboard  # noqa: E402
from app.services import generation_service  # noqa: E402
from app.services.export_service import create_kindle_zip, create_pdf  # noqa: E402
from app.services.image_assembler import assemble_page  # noqa: E402
from app.services.llm_service import (  # noqa: E402
    STORYBOARD_SCHEMA,
    SYSTEM_PROMPT,
    generate_storyboard,
)
from app.services.session_store import create_session as _new_session  # noqa: E402
from app.services.session_store import load_storyboard, session_dir  # noqa: E402

mcp = FastMCP(
    "manga-app",
    instructions=(
        "漫画ページを作るツール群。手順: storyboard_guidelines でルールを読む → ネームJSONを書いて "
        "create_session → (任意) generate_character_sheet → 各ページ generate_page_image → "
        "assemble_pages → export_manga。画像生成は ChatGPT(gpt-image-2) を Codex CLI 経由で使い、"
        "1枚に数分かかる。返るパスの画像は Read で確認できる。"
    ),
)


@mcp.tool()
def storyboard_guidelines() -> str:
    """ネーム（storyboard）JSON の書き方のルールとスキーマを返す。create_session の前に読む。"""
    return f"{SYSTEM_PROMPT}\n\n## スキーマ\n{STORYBOARD_SCHEMA}"


@mcp.tool()
def create_session(storyboard_json: str) -> dict:
    """ネーム JSON（storyboard_guidelines のスキーマ）から新しいセッションを作り、session_id を返す。"""
    storyboard = Storyboard.model_validate_json(storyboard_json)
    session_id = _new_session(storyboard)
    return {"session_id": session_id, "pages": len(storyboard.pages)}


@mcp.tool()
async def create_storyboard_with_claude_api(
    title: str, story: str, genre: str = "少年漫画", style: str = "標準的な漫画スタイル",
    num_pages: int = 2,
) -> dict:
    """Anthropic API（backend/.env の ANTHROPIC_API_KEY）でネームを自動生成してセッションを作る。"""
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY が未設定です。ネームを自分で書いて create_session を使ってください。")
    storyboard = await generate_storyboard(title, story, genre, style, num_pages)
    session_id = _new_session(storyboard)
    return {"session_id": session_id, "storyboard": json.loads(storyboard.model_dump_json())}


@mcp.tool()
def get_session(session_id: str) -> dict:
    """セッションの現在のネーム（生成済み画像・検出したコマ枠を含む）を返す。"""
    return json.loads(load_storyboard(session_id).model_dump_json())


@mcp.tool()
async def generate_character_sheet(session_id: str) -> str:
    """登場キャラ全員の参照シートを1枚生成する（以降のページで顔・服装をそろえるため）。画像の絶対パスを返す。"""
    out = await generation_service.generate_character_sheet(session_id)
    return str(out.resolve())


@mcp.tool()
async def generate_page_image(
    session_id: str, page_number: int, use_character_refs: bool = True
) -> str:
    """コマ割りガイドに沿って1ページ分の絵（文字なし）を生成する。画像の絶対パスを返す。"""
    out = await generation_service.generate_page(session_id, page_number, use_character_refs)
    return str(out.resolve())


@mcp.tool()
def assemble_pages(session_id: str) -> list[str]:
    """全ページに吹き出し・効果音を重ねて完成ページを作る。完成画像の絶対パスを返す。"""
    storyboard = load_storyboard(session_id)
    directory = session_dir(session_id)
    return [str(assemble_page(directory, page).resolve()) for page in storyboard.pages]


@mcp.tool()
def export_manga(session_id: str, format: str = "pdf") -> str:
    """完成ページを PDF（format="pdf"）か CBZ（format="cbz"）にまとめ、ファイルの絶対パスを返す。"""
    storyboard = load_storyboard(session_id)
    directory = session_dir(session_id)
    out = create_pdf(directory, storyboard) if format == "pdf" else create_kindle_zip(directory, storyboard)
    return str(Path(out).resolve())


if __name__ == "__main__":
    mcp.run()
