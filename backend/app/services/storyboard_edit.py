"""
既存セッションのネームを部分的に直す。MCP（Claude Code）と Web API から呼ぶ。

文字・吹き出し・効果音の修正は合成し直すだけで反映されるが、構図や人物など
絵に関わる項目は描き直さないと反映されない。どちらかを結果で知らせる。
"""
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ..models.schemas import MangaPage, Panel, SpeechBubble, Storyboard
from .session_store import load_storyboard, save_storyboard

# 変えたら絵の描き直しが要る項目
ART_FIELDS = {"composition", "camera_angle", "background", "characters", "expression",
              "image_prompt_en", "image_prompt_ja"}
PANEL_FIELDS = ART_FIELDS | {"dialogue", "sound_effect", "sound_effect_orientation"}
BUBBLE_POSITION_FIELDS = ("x", "y", "width", "height")


@dataclass
class EditResult:
    changed: list[str]
    needs_redraw: bool
    message: str


def _page(storyboard: Storyboard, page_number: int) -> MangaPage:
    for page in storyboard.pages:
        if page.page_number == page_number:
            return page
    raise LookupError(f"ページ {page_number} が見つかりません")


def _panel(page: MangaPage, panel_number: int) -> Panel:
    for panel in page.panels:
        if panel.panel_number == panel_number:
            return panel
    raise LookupError(f"{page.page_number}ページにコマ {panel_number} はありません")


def _bubble(panel: Panel, index: int) -> SpeechBubble:
    if not 0 <= index < len(panel.speech_bubbles):
        raise LookupError(
            f"コマ {panel.panel_number} の吹き出しは {len(panel.speech_bubbles)} 個です（番号は0から）"
        )
    return panel.speech_bubbles[index]


def _validated(model_cls, data: dict[str, Any]):
    try:
        return model_cls.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"値が不正です: {e.errors()[0]['loc']} {e.errors()[0]['msg']}") from e


def _result(changed: list[str], page: MangaPage) -> EditResult:
    redraw = bool(set(changed) & ART_FIELDS) and page.generated_image is not None
    if not changed:
        return EditResult([], False, "変更はありません")
    if redraw:
        message = ("絵に関わる項目を変えたので、反映するには generate_page_image か "
                   "redraw_panel で描き直してください。文字は合成し直せば反映されます。")
    else:
        message = "合成し直せば反映されます（絵の描き直しは不要）。"
    return EditResult(changed, redraw, message)


def update_panel(session_id: str, page_number: int, panel_number: int, **changes: Any) -> EditResult:
    """コマの項目を部分的に書き換える。None の項目は変えない"""
    changes = {k: v for k, v in changes.items() if v is not None}
    unknown = set(changes) - PANEL_FIELDS
    if unknown:
        raise ValueError(f"変更できない項目です: {', '.join(sorted(unknown))}")
    storyboard = load_storyboard(session_id)
    page = _page(storyboard, page_number)
    panel = _panel(page, panel_number)
    updated = _validated(Panel, {**panel.model_dump(), **changes})
    page.panels[page.panels.index(panel)] = updated
    save_storyboard(session_id, storyboard)
    return _result(sorted(changes), page)


def update_speech_bubble(
    session_id: str, page_number: int, panel_number: int, index: int, **changes: Any
) -> EditResult:
    """吹き出しの文字・種類・向き・位置（コマ内 %）を部分的に書き換える"""
    changes = {k: v for k, v in changes.items() if v is not None}
    storyboard = load_storyboard(session_id)
    page = _page(storyboard, page_number)
    panel = _panel(page, panel_number)
    bubble = _bubble(panel, index)
    data = bubble.model_dump()
    for key in BUBBLE_POSITION_FIELDS:
        if key in changes:
            data["position"][key] = changes.pop(key)
    unknown = set(changes) - {"text", "type", "orientation"}
    if unknown:
        raise ValueError(f"変更できない項目です: {', '.join(sorted(unknown))}")
    data.update(changes)
    panel.speech_bubbles[index] = _validated(SpeechBubble, data)
    save_storyboard(session_id, storyboard)
    return _result(["speech_bubbles"], page)


def add_speech_bubble(
    session_id: str, page_number: int, panel_number: int, text: str,
    x: float, y: float, width: float, height: float,
    type: str = "normal", orientation: str = "vertical",
) -> int:
    """吹き出しを足し、その番号を返す"""
    storyboard = load_storyboard(session_id)
    panel = _panel(_page(storyboard, page_number), panel_number)
    panel.speech_bubbles.append(_validated(SpeechBubble, {
        "text": text, "type": type, "orientation": orientation,
        "position": {"x": x, "y": y, "width": width, "height": height},
    }))
    save_storyboard(session_id, storyboard)
    return len(panel.speech_bubbles) - 1


def remove_speech_bubble(session_id: str, page_number: int, panel_number: int, index: int) -> None:
    storyboard = load_storyboard(session_id)
    panel = _panel(_page(storyboard, page_number), panel_number)
    _bubble(panel, index)
    del panel.speech_bubbles[index]
    save_storyboard(session_id, storyboard)


def update_character(
    session_id: str, name: str, description: str | None = None, prompt_keywords: str | None = None
) -> EditResult:
    """キャラの外見設定を直す。参照シートや描いたページには描き直すまで反映されない"""
    storyboard = load_storyboard(session_id)
    character = next((c for c in storyboard.characters if c.name == name), None)
    if character is None:
        names = "、".join(c.name for c in storyboard.characters)
        raise LookupError(f"キャラ「{name}」はいません（登録: {names}）")
    changed = []
    if description is not None:
        character.description = description
        changed.append("description")
    if prompt_keywords is not None:
        character.prompt_keywords = prompt_keywords
        changed.append("prompt_keywords")
    save_storyboard(session_id, storyboard)
    if not changed:
        return EditResult([], False, "変更はありません")
    return EditResult(changed, True, "見た目を変えたので、generate_character_sheet で参照シートを作り直し、"
                                     "ページを描き直すと反映されます。")
