"""
AI 画像生成の手順をまとめる。Web API と MCP サーバーの両方から呼ぶ。

1ページ = 1回の生成：コマ割りガイドとキャラ参照シートを渡してページ全体を描かせ、
描かれたコマ枠を測り直して storyboard.json に記録する。
"""
from pathlib import Path

from ..models.schemas import MangaPage
from .image_gen import ImageGenerator, create_image_generator
from .layout_guide import render_guide
from .page_prompt import build_character_sheet_prompt, build_page_prompt
from .panel_detect import measure_rendered_layouts
from .session_store import load_storyboard, save_storyboard, session_dir

CHARACTER_SHEET = Path("characters") / "characters.png"


def _find_page(pages: list[MangaPage], page_number: int) -> MangaPage:
    for page in pages:
        if page.page_number == page_number:
            return page
    raise LookupError(f"ページ {page_number} が見つかりません")


async def generate_character_sheet(
    session_id: str, generator: ImageGenerator | None = None
) -> Path:
    storyboard = load_storyboard(session_id)
    if not storyboard.characters:
        raise ValueError("キャラクターが登録されていません")
    directory = session_dir(session_id)
    generator = generator or create_image_generator()

    out = await generator.generate(
        build_character_sheet_prompt(storyboard), [], directory / CHARACTER_SHEET
    )
    # 生成中にネームが編集されている可能性があるので読み直してから書く
    storyboard = load_storyboard(session_id)
    for character in storyboard.characters:
        character.reference_image = CHARACTER_SHEET.as_posix()
    save_storyboard(session_id, storyboard)
    return out


async def generate_page(
    session_id: str,
    page_number: int,
    use_character_refs: bool = True,
    generator: ImageGenerator | None = None,
) -> Path:
    storyboard = load_storyboard(session_id)
    page = _find_page(storyboard.pages, page_number)
    directory = session_dir(session_id)
    generator = generator or create_image_generator()

    refs = [render_guide(page, directory / "guides" / f"guide_{page_number:03d}.png")]
    reference_names: list[str] = []
    sheet = directory / CHARACTER_SHEET
    if use_character_refs and sheet.exists():
        refs.append(sheet)
        reference_names = [c.name for c in storyboard.characters]

    relative = Path("generated") / f"page_{page_number:03d}.png"
    prompt = build_page_prompt(storyboard, page, reference_names)
    (directory / "generated").mkdir(parents=True, exist_ok=True)
    (directory / relative).with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
    out = await generator.generate(prompt, refs, directory / relative)

    storyboard = load_storyboard(session_id)
    page = _find_page(storyboard.pages, page_number)
    page.generated_image = relative.as_posix()
    for panel, rendered in zip(page.panels, measure_rendered_layouts(page, out)):
        panel.rendered_layout = rendered
    save_storyboard(session_id, storyboard)
    return out
