import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app
from app.services import generation_service, storyboard_edit
from app.services.layout_guide import GUIDE_HEIGHT, GUIDE_WIDTH, panel_box
from app.services.session_store import create_session, load_storyboard, session_dir

client = TestClient(app)


class PaintGenerator:
    """
    生成 AI の代わり。ページ生成ではガイドの枠を描いて中を color で塗る。
    1コマの描き直しでも同じ絵を返すので、貼られた範囲が color になる。
    """

    def __init__(self, color: tuple[int, int, int]) -> None:
        self.color = color
        self.prompts: list[str] = []

    async def generate(self, prompt: str, refs: list[Path], out_path: Path) -> Path:
        self.prompts.append(prompt)
        page = load_storyboard(out_path.parent.parent.name).pages[0]
        img = Image.new("RGB", (GUIDE_WIDTH, GUIDE_HEIGHT), "white")
        draw = ImageDraw.Draw(img)
        for panel in page.panels:
            draw.rectangle(panel_box(panel.layout), fill=self.color, outline="black", width=6)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path)
        return out_path


def _pixel_in_panel(session_id: str, panel_index: int) -> tuple[int, int, int]:
    page = load_storyboard(session_id).pages[0]
    with Image.open(session_dir(session_id) / page.generated_image) as img:
        x0, y0, x1, y1 = panel_box(page.panels[panel_index].layout, *img.size)
        return img.convert("RGB").getpixel(((x0 + x1) // 2, (y0 + y1) // 2))


@pytest.fixture
def session_id(storyboard, output_dir) -> str:
    return create_session(storyboard)


def test_text_edit_does_not_ask_for_redraw(session_id):
    asyncio.run(generation_service.generate_page(session_id, 1, generator=PaintGenerator((100, 100, 100))))
    result = storyboard_edit.update_panel(session_id, 1, 1, sound_effect="ドン")
    assert result.changed == ["sound_effect"]
    assert not result.needs_redraw
    assert load_storyboard(session_id).pages[0].panels[0].sound_effect == "ドン"


def test_art_edit_on_drawn_page_asks_for_redraw(session_id):
    asyncio.run(generation_service.generate_page(session_id, 1, generator=PaintGenerator((100, 100, 100))))
    assert storyboard_edit.update_panel(session_id, 1, 1, composition="俯瞰").needs_redraw


def test_unknown_field_is_rejected(session_id):
    with pytest.raises(ValueError, match="変更できない"):
        storyboard_edit.update_panel(session_id, 1, 1, layout="x")


def test_bubble_add_update_remove(session_id):
    index = storyboard_edit.add_speech_bubble(session_id, 1, 1, "おはよう", 70, 5, 15, 40)
    storyboard_edit.update_speech_bubble(session_id, 1, 1, index, text="こんにちは", y=10)
    bubble = load_storyboard(session_id).pages[0].panels[0].speech_bubbles[index]
    assert (bubble.text, bubble.position.y, bubble.position.width) == ("こんにちは", 10, 15)
    storyboard_edit.remove_speech_bubble(session_id, 1, 1, index)
    assert len(load_storyboard(session_id).pages[0].panels[0].speech_bubbles) == index


def test_bubble_position_out_of_range_is_rejected(session_id):
    index = storyboard_edit.add_speech_bubble(session_id, 1, 1, "a", 70, 5, 15, 40)
    with pytest.raises(ValueError, match="不正"):
        storyboard_edit.update_speech_bubble(session_id, 1, 1, index, x=150)


def test_missing_bubble_reports_how_many_exist(session_id):
    with pytest.raises(LookupError, match="個です"):
        storyboard_edit.update_speech_bubble(session_id, 1, 1, 99, text="x")


def test_redrawing_keeps_old_versions_and_can_switch_back(session_id):
    asyncio.run(generation_service.generate_page(session_id, 1, generator=PaintGenerator((100, 100, 100))))
    asyncio.run(generation_service.generate_page(session_id, 1, generator=PaintGenerator((180, 180, 180))))
    versions, current = generation_service.list_page_versions(session_id, 1)
    assert [Path(v).name for v in versions] == ["page_001_v1.png", "page_001_v2.png"]
    assert current == 2
    generation_service.use_page_version(session_id, 1, 1)
    assert _pixel_in_panel(session_id, 0) == (100, 100, 100)


def test_page_drawn_before_versioning_counts_as_v1(session_id):
    storyboard = load_storyboard(session_id)
    legacy = session_dir(session_id) / "generated" / "page_001.png"
    legacy.parent.mkdir(parents=True)
    Image.new("RGB", (GUIDE_WIDTH, GUIDE_HEIGHT), "white").save(legacy)
    storyboard.pages[0].generated_image = "generated/page_001.png"
    from app.services.session_store import save_storyboard
    save_storyboard(session_id, storyboard)

    asyncio.run(generation_service.generate_page(session_id, 1, generator=PaintGenerator((100, 100, 100))))
    versions, current = generation_service.list_page_versions(session_id, 1)
    assert versions[0] == "generated/page_001.png" and current == 2


def test_redraw_changes_only_the_target_panel(session_id):
    asyncio.run(generation_service.generate_page(session_id, 1, generator=PaintGenerator((100, 100, 100))))
    redrawer = PaintGenerator((200, 50, 50))
    asyncio.run(generation_service.redraw_panel(session_id, 1, 2, "もっと笑顔に", generator=redrawer))

    assert _pixel_in_panel(session_id, 1) == (200, 50, 50)
    # 描き直したコマ以外は元の版のまま
    assert _pixel_in_panel(session_id, 0) == (100, 100, 100)
    assert "もっと笑顔に" in redrawer.prompts[0]
    assert generation_service.list_page_versions(session_id, 1)[1] == 2


def test_redraw_needs_a_drawn_page(session_id):
    with pytest.raises(ValueError, match="まだ描かれていません"):
        asyncio.run(generation_service.redraw_panel(session_id, 1, 1, generator=PaintGenerator((0, 0, 0))))


def test_version_api_switches_and_rejects_missing(session_id):
    asyncio.run(generation_service.generate_page(session_id, 1, generator=PaintGenerator((100, 100, 100))))
    ok = client.post("/api/generation/page/version", json={"session_id": session_id, "page_number": 1, "version": 1})
    assert ok.status_code == 200
    missing = client.post("/api/generation/page/version", json={"session_id": session_id, "page_number": 1, "version": 5})
    assert missing.status_code == 404
