"""
ネームから画像生成プロンプトを組み立てる。

セリフ・効果音は Pillow で後から重ねるので、画像には文字を一切描かせない。
gpt-image-2 は小さい日本語で崩れることがあり、修正も効かないため。
"""
from ..models.schemas import Character, MangaPage, Panel, PanelLayout, Storyboard

_NO_TEXT = (
    "Absolutely no text anywhere: no letters, no speech bubbles, no sound effects, "
    "no captions, no signatures, no panel numbers."
)
# ローアングル（アオリ）指定でスカートの中を描くことがあったため明示的に止める
_MODESTY = (
    "Keep every character modestly and fully clothed and never sexualized: no underwear "
    "visible, no upskirt or cleavage-focused framing, even in low-angle shots."
)


def _position_label(layout: PanelLayout) -> str:
    cy = layout.y + layout.height / 2
    vertical = "top" if cy < 34 else "bottom" if cy > 66 else "middle"
    if layout.width >= 90:
        return f"{vertical}, full width"
    cx = layout.x + layout.width / 2
    horizontal = "left" if cx < 45 else "right" if cx > 55 else "center"
    return f"{vertical} {horizontal}"


def _character_lookup(storyboard: Storyboard) -> dict[str, Character]:
    return {c.name: c for c in storyboard.characters}


def _describe_panel(panel: Panel, characters: dict[str, Character]) -> str:
    parts = [f"Panel {panel.panel_number} ({_position_label(panel.layout)}):"]
    if panel.image_prompt_en:
        parts.append(panel.image_prompt_en.rstrip(". ") + ".")
    if panel.composition:
        parts.append(f"Composition: {panel.composition}.")
    if panel.camera_angle:
        parts.append(f"Camera: {panel.camera_angle}.")
    if panel.background:
        parts.append(f"Background: {panel.background}.")
    for name in panel.characters:
        character = characters.get(name)
        looks = f" ({character.prompt_keywords})" if character else ""
        parts.append(f"Character {name}{looks}.")
    if panel.expression:
        parts.append(f"Expression/pose: {panel.expression}.")
    return " ".join(parts)


def build_page_prompt(storyboard: Storyboard, page: MangaPage, reference_names: list[str]) -> str:
    """
    reference_names: 2枚目の入力画像（キャラ参照シート）に左から並んでいるキャラ名。
    空なら参照画像なしのプロンプトになる。
    """
    characters = _character_lookup(storyboard)
    lines = [
        "Create one finished Japanese manga page in portrait orientation (2:3).",
        f"Style: {storyboard.style}; genre: {storyboard.genre}. Black-and-white ink, clean "
        "confident lineart, screentone shading, professional published-manga quality.",
        "",
        "Input image 1 is the panel layout guide. Reproduce its panel borders exactly: the same "
        "number of panels at the same positions and sizes, thick black borders, white gutters "
        "between panels and a white page margin. Draw nothing outside the panels.",
        "The light gray rectangles in image 1 mark where speech bubbles will be pasted later. "
        "Keep those areas as calm, uncluttered background (sky, wall, plain space) with no faces "
        "or important details, and do not draw the gray rectangles themselves.",
    ]
    if reference_names:
        lines.append(
            "Input image 2 is the character reference sheet showing, from left to right: "
            + ", ".join(reference_names)
            + ". Keep each character's face, hairstyle, body type and outfit identical to it."
        )
    lines += ["", _NO_TEXT, _MODESTY, "", "Panels:"]
    if page.page_notes:
        lines.append(f"Page direction: {page.page_notes}")
    lines += [_describe_panel(p, characters) for p in page.panels]
    return "\n".join(lines)


def build_character_sheet_prompt(storyboard: Storyboard) -> str:
    names = [c.name for c in storyboard.characters]
    lines = [
        "Create a character reference sheet for a black-and-white Japanese manga, "
        "portrait orientation (2:3), plain white background.",
        f"Style: {storyboard.style}. Clean ink lineart with screentone shading.",
        f"Show these {len(names)} characters standing side by side, from left to right: "
        + ", ".join(names) + ".",
        "For each character draw a full-body front view, with a large close-up of the face "
        "directly above it, so the face and outfit are easy to copy later.",
    ]
    for c in storyboard.characters:
        lines.append(f"- {c.name}: {c.prompt_keywords}. {c.description}")
    lines += ["", _NO_TEXT, _MODESTY]
    return "\n".join(lines)


def panel_orientation(width: float, height: float) -> str:
    """描き直すコマの形に近い、gpt-image-2 の出力の向き"""
    ratio = width / height
    if ratio > 1.25:
        return "landscape (3:2)"
    if ratio < 0.8:
        return "portrait (2:3)"
    return "square (1:1)"


def build_panel_redraw_prompt(
    storyboard: Storyboard, panel: Panel, instruction: str, reference_names: list[str],
    orientation: str,
) -> str:
    """
    1コマだけを新しい1枚の絵として描かせる（入力画像1は今のそのコマの切り抜き）。
    できた絵は元のページのコマ枠に貼るので、枠線やほかのコマは描かせない。
    ページ全体を「同じものを描き直して」と頼むと、既存画像の再現として安全フィルタに止められた。
    """
    characters = _character_lookup(storyboard)
    lines = [
        "Draw one new black-and-white Japanese manga panel illustration, "
        f"{orientation}, filling the whole canvas with no border, no frame and no white margin.",
        "Input image 1 is the current version of this panel. Match its art style, line weight, "
        "screentone shading, camera framing and lighting so the new panel fits the same page, "
        "and apply the requested change.",
    ]
    if reference_names:
        lines.append(
            "Input image 2 is the character reference sheet showing, from left to right: "
            + ", ".join(reference_names)
            + ". Keep each character's face, hairstyle, body type and outfit identical to it."
        )
    lines += ["", "What the panel should show:", _describe_panel(panel, characters)]
    if instruction.strip():
        lines += ["", f"Requested change (highest priority): {instruction.strip()}"]
    lines += ["", _NO_TEXT, _MODESTY]
    return "\n".join(lines)
