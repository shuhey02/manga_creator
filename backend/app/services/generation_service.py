"""
AI 画像生成の手順をまとめる。Web API と MCP サーバーの両方から呼ぶ。

1ページ = 1回の生成：コマ割りガイドとキャラ参照シートを渡してページ全体を描かせ、
描かれたコマ枠を測り直して storyboard.json に記録する。
描き直すたびに新しい版のファイルを作り、前の版は残す（気に入らなければ戻せるように）。
"""
from pathlib import Path

from PIL import Image

from ..models.schemas import MangaPage, PanelLayout, Storyboard
from .image_gen import ImageGenerator, create_image_generator
from .layout_guide import panel_box, render_guide
from .page_prompt import (
    build_character_sheet_prompt,
    build_page_prompt,
    build_panel_redraw_prompt,
    panel_orientation,
)
from .panel_detect import measure_rendered_layouts
from .session_store import load_storyboard, save_storyboard, session_dir

CHARACTER_SHEET = Path("characters") / "characters.png"
# 貼り戻すときに残す元の枠線の太さ（画像幅に対する比）
PANEL_BORDER_RATIO = 0.006


def _find_page(pages: list[MangaPage], page_number: int) -> MangaPage:
    for page in pages:
        if page.page_number == page_number:
            return page
    raise LookupError(f"ページ {page_number} が見つかりません")


def _versions(page: MangaPage) -> list[str]:
    """版の一覧。版の仕組みより前に描いたページは、その1枚を v1 とみなす"""
    if page.generated_image and page.generated_image not in page.generated_versions:
        return [page.generated_image, *page.generated_versions]
    return list(page.generated_versions)


def _next_version_path(page: MangaPage) -> Path:
    return Path("generated") / f"page_{page.page_number:03d}_v{len(_versions(page)) + 1}.png"


def _adopt_version(session_id: str, page_number: int, relative: Path) -> None:
    """新しい版を一覧に足して使う版にし、描かれたコマ枠を測り直す"""
    storyboard = load_storyboard(session_id)
    page = _find_page(storyboard.pages, page_number)
    page.generated_versions = [*_versions(page), relative.as_posix()]
    _use(page, relative.as_posix(), session_dir(session_id))
    save_storyboard(session_id, storyboard)


def _use(page: MangaPage, relative: str, directory: Path) -> None:
    page.generated_image = relative
    for panel, rendered in zip(page.panels, measure_rendered_layouts(page, directory / relative)):
        panel.rendered_layout = rendered


def _reference_sheet(storyboard: Storyboard, directory: Path, use: bool) -> tuple[list[Path], list[str]]:
    sheet = directory / CHARACTER_SHEET
    if use and sheet.exists():
        return [sheet], [c.name for c in storyboard.characters]
    return [], []


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

    sheet_refs, reference_names = _reference_sheet(storyboard, directory, use_character_refs)
    refs = [render_guide(page, directory / "guides" / f"guide_{page_number:03d}.png"), *sheet_refs]

    relative = _next_version_path(page)
    prompt = build_page_prompt(storyboard, page, reference_names)
    (directory / "generated").mkdir(parents=True, exist_ok=True)
    (directory / relative).with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
    out = await generator.generate(prompt, refs, directory / relative)

    _adopt_version(session_id, page_number, relative)
    return out


def list_page_versions(session_id: str, page_number: int) -> tuple[list[str], int | None]:
    """版の一覧（古い順）と、使っている版の番号（1始まり）"""
    page = _find_page(load_storyboard(session_id).pages, page_number)
    versions = _versions(page)
    current = versions.index(page.generated_image) + 1 if page.generated_image in versions else None
    return versions, current


def use_page_version(session_id: str, page_number: int, version: int) -> str:
    """使う版を切り替える（1始まり）。コマ枠はその版の画像から測り直す"""
    storyboard = load_storyboard(session_id)
    page = _find_page(storyboard.pages, page_number)
    versions = _versions(page)
    if not 1 <= version <= len(versions):
        raise LookupError(f"{page_number}ページの版は {len(versions)} 個です")
    page.generated_versions = versions
    _use(page, versions[version - 1], session_dir(session_id))
    save_storyboard(session_id, storyboard)
    return versions[version - 1]


def _to_box(layout: PanelLayout, size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = size
    return (round(w * layout.x / 100), round(h * layout.y / 100),
            round(w * (layout.x + layout.width) / 100), round(h * (layout.y + layout.height) / 100))


def _shrink(box: tuple[int, int, int, int], inset: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return x0 + inset, y0 + inset, x1 - inset, y1 - inset


def panel_inner_box(page: MangaPage, panel_index: int, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """ページ画像上の、そのコマの枠線より内側（貼り替える範囲）"""
    panel = page.panels[panel_index]
    if panel.rendered_layout is not None:
        box = _to_box(panel.rendered_layout, size)
    else:
        box = panel_box(panel.layout, *size)
    return _shrink(box, max(4, round(size[0] * PANEL_BORDER_RATIO)))


def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
    """縦横比を保って枠を覆う大きさにし、はみ出しを中央で切る"""
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left, top = (resized.width - width) // 2, (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def composite_panel(page: MangaPage, panel_index: int, base: Image.Image, redrawn: Image.Image) -> Image.Image:
    """描き直した1コマの絵を、元のページの同じコマの枠内へ貼る。ほかのコマと枠線は元のまま"""
    base = base.convert("RGB")
    x0, y0, x1, y1 = panel_inner_box(page, panel_index, base.size)
    result = base.copy()
    result.paste(_cover(redrawn.convert("RGB"), x1 - x0, y1 - y0), (x0, y0))
    return result


async def redraw_panel(
    session_id: str,
    page_number: int,
    panel_number: int,
    instruction: str = "",
    use_character_refs: bool = True,
    generator: ImageGenerator | None = None,
) -> Path:
    """
    使っている版のページから1コマを切り出して参照に渡し、新しい1コマを描かせてその枠へ貼る。
    ほかのコマは元の版から1ピクセルも変えない。結果は新しい版として保存する。
    """
    storyboard = load_storyboard(session_id)
    page = _find_page(storyboard.pages, page_number)
    if not page.generated_image:
        raise ValueError(f"{page_number}ページはまだ描かれていません。先に generate_page_image で描いてください")
    index = next((i for i, p in enumerate(page.panels) if p.panel_number == panel_number), None)
    if index is None:
        raise LookupError(f"{page_number}ページにコマ {panel_number} はありません")
    directory = session_dir(session_id)
    generator = generator or create_image_generator()

    base_path = directory / page.generated_image
    relative = _next_version_path(page)
    current_panel = (directory / relative).with_name(relative.stem + "_panel_before.png")
    with Image.open(base_path) as base:
        box = panel_inner_box(page, index, base.size)
        base.convert("RGB").crop(box).save(current_panel)

    sheet_refs, reference_names = _reference_sheet(storyboard, directory, use_character_refs)
    orientation = panel_orientation(box[2] - box[0], box[3] - box[1])
    prompt = build_panel_redraw_prompt(storyboard, page.panels[index], instruction, reference_names, orientation)

    raw = (directory / relative).with_name(relative.stem + "_panel_after.png")
    (directory / relative).with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
    await generator.generate(prompt, [current_panel, *sheet_refs], raw)

    with Image.open(base_path) as base, Image.open(raw) as redrawn:
        composite_panel(page, index, base, redrawn).save(directory / relative)
    _adopt_version(session_id, page_number, relative)
    return directory / relative
