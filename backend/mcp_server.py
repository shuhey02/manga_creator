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
from app.services import generation_service, storyboard_edit  # noqa: E402
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
        "1枚に数分かかる。返るパスの画像は Read で確認できる。\n"
        "微修正は新しいセッションを作らず同じセッションを直す: セリフ・吹き出し・効果音は update_panel / "
        "update_speech_bubble / add_speech_bubble / remove_speech_bubble で直して assemble_page_image "
        "（数秒・無料）。1コマだけ絵を直すなら redraw_panel、ページ全体なら generate_page_image。"
        "描き直した絵は版として残るので、気に入らなければ use_page_version で戻せる。"
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
async def redraw_panel(
    session_id: str, page_number: int, panel_number: int, instruction: str = "",
    use_character_refs: bool = True,
) -> dict:
    """
    今の絵を元に1コマだけ描き直す（instruction に直したい内容を書く。日本語可）。
    ほかのコマは元の絵のまま残し、新しい版として保存する。気に入らなければ use_page_version で戻す。
    """
    out = await generation_service.redraw_panel(
        session_id, page_number, panel_number, instruction, use_character_refs
    )
    versions, current = generation_service.list_page_versions(session_id, page_number)
    return {"image": str(out.resolve()), "version": current, "versions": len(versions)}


@mcp.tool()
def list_page_versions(session_id: str, page_number: int) -> dict:
    """ページの絵の版の一覧（古い順、1始まり）と、使っている版の番号を返す。画像は Read で比べられる。"""
    versions, current = generation_service.list_page_versions(session_id, page_number)
    directory = session_dir(session_id)
    return {
        "current": current,
        "versions": [{"version": i, "image": str((directory / v).resolve())} for i, v in enumerate(versions, 1)],
    }


@mcp.tool()
def use_page_version(session_id: str, page_number: int, version: int) -> dict:
    """ページの絵を指定の版（1始まり）に切り替える。合成し直すと反映される。"""
    relative = generation_service.use_page_version(session_id, page_number, version)
    return {"image": str((session_dir(session_id) / relative).resolve()),
            "message": "assemble_page_image で合成し直すと反映されます。"}


@mcp.tool()
def assemble_pages(session_id: str) -> list[str]:
    """全ページに吹き出し・効果音を重ねて完成ページを作る。完成画像の絶対パスを返す。"""
    storyboard = load_storyboard(session_id)
    directory = session_dir(session_id)
    return [str(assemble_page(directory, page).resolve()) for page in storyboard.pages]


@mcp.tool()
def assemble_page_image(session_id: str, page_number: int) -> str:
    """1ページだけ吹き出し・効果音を重ねて合成し直す（ネームを直した後の確認用。数秒）。完成画像の絶対パスを返す。"""
    storyboard = load_storyboard(session_id)
    page = next((p for p in storyboard.pages if p.page_number == page_number), None)
    if page is None:
        raise LookupError(f"ページ {page_number} が見つかりません")
    return str(assemble_page(session_dir(session_id), page).resolve())


def _edit_result(result: storyboard_edit.EditResult) -> dict:
    return {"changed": result.changed, "needs_redraw": result.needs_redraw, "message": result.message}


@mcp.tool()
def update_panel(
    session_id: str, page_number: int, panel_number: int,
    dialogue: str | None = None, sound_effect: str | None = None,
    sound_effect_orientation: str | None = None,
    composition: str | None = None, camera_angle: str | None = None, background: str | None = None,
    characters: list[str] | None = None, expression: str | None = None,
    image_prompt_en: str | None = None,
) -> dict:
    """
    コマの項目を部分的に直す（指定しない項目はそのまま）。効果音・セリフメモは合成し直せば反映される。
    構図・背景・人物・表情・画像プロンプトは絵に関わるので、反映には描き直しが要る（needs_redraw で返す）。
    吹き出しの文字は update_speech_bubble で直す。
    """
    return _edit_result(storyboard_edit.update_panel(
        session_id, page_number, panel_number, dialogue=dialogue, sound_effect=sound_effect,
        sound_effect_orientation=sound_effect_orientation, composition=composition,
        camera_angle=camera_angle, background=background, characters=characters,
        expression=expression, image_prompt_en=image_prompt_en,
    ))


@mcp.tool()
def update_speech_bubble(
    session_id: str, page_number: int, panel_number: int, bubble_index: int,
    text: str | None = None, type: str | None = None, orientation: str | None = None,
    x: float | None = None, y: float | None = None, width: float | None = None, height: float | None = None,
) -> dict:
    """
    吹き出しを部分的に直す。bubble_index は get_session の speech_bubbles の順番（0から）。
    type は normal / thought / shout / whisper、orientation は auto / vertical / horizontal。
    x, y, width, height はコマ内の 0〜100%（左上が 0,0）。直したら assemble_page_image で確認する。
    """
    return _edit_result(storyboard_edit.update_speech_bubble(
        session_id, page_number, panel_number, bubble_index, text=text, type=type,
        orientation=orientation, x=x, y=y, width=width, height=height,
    ))


@mcp.tool()
def add_speech_bubble(
    session_id: str, page_number: int, panel_number: int, text: str,
    x: float, y: float, width: float, height: float,
    type: str = "normal", orientation: str = "vertical",
) -> dict:
    """吹き出しを足す。位置と大きさはコマ内の 0〜100%（縦書きなら縦長に: width 12〜22, height 25〜45 が目安）。"""
    index = storyboard_edit.add_speech_bubble(
        session_id, page_number, panel_number, text, x, y, width, height, type, orientation
    )
    return {"bubble_index": index, "message": "合成し直せば反映されます。"}


@mcp.tool()
def remove_speech_bubble(session_id: str, page_number: int, panel_number: int, bubble_index: int) -> dict:
    """吹き出しを1つ消す。以降の吹き出しの番号は1つずつ詰まる。"""
    storyboard_edit.remove_speech_bubble(session_id, page_number, panel_number, bubble_index)
    return {"message": "合成し直せば反映されます。"}


@mcp.tool()
def update_character(
    session_id: str, name: str, description: str | None = None, prompt_keywords: str | None = None
) -> dict:
    """キャラの外見設定（日本語の説明・英語の画像用キーワード）を直す。反映には参照シートとページの描き直しが要る。"""
    return _edit_result(storyboard_edit.update_character(session_id, name, description, prompt_keywords))


@mcp.tool()
def export_manga(session_id: str, format: str = "pdf") -> str:
    """完成ページを PDF（format="pdf"）か CBZ（format="cbz"）にまとめ、ファイルの絶対パスを返す。"""
    storyboard = load_storyboard(session_id)
    directory = session_dir(session_id)
    out = create_pdf(directory, storyboard) if format == "pdf" else create_kindle_zip(directory, storyboard)
    return str(Path(out).resolve())


if __name__ == "__main__":
    mcp.run()
