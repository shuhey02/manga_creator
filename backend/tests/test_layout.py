from PIL import Image, ImageDraw

from app.models.schemas import MangaPage, Panel, PanelLayout
from app.services.layout_guide import GUIDE_HEIGHT, GUIDE_WIDTH, panel_box, render_guide
from app.services.panel_detect import detect_panel_boxes, measure_rendered_layouts


def _page(*layouts: tuple[float, float, float, float]) -> MangaPage:
    return MangaPage(
        page_number=1,
        panels=[
            Panel(panel_number=i, layout=PanelLayout(x=x, y=y, width=w, height=h))
            for i, (x, y, w, h) in enumerate(layouts, 1)
        ],
    )


def _shaded_page(boxes: list[tuple[int, int, int, int]]) -> Image.Image:
    """枠の中を灰色で塗った、生成画像の代わり"""
    img = Image.new("RGB", (GUIDE_WIDTH, GUIDE_HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    for box in boxes:
        draw.rectangle(box, fill=(150, 150, 150), outline="black", width=6)
    return img


def test_adjacent_panels_leave_a_gutter_between_them():
    left = panel_box(PanelLayout(x=0, y=0, width=50, height=100))
    right = panel_box(PanelLayout(x=50, y=0, width=50, height=100))
    assert right[0] - left[2] >= 10


def test_guide_draws_borders_inside_white_margin(tmp_path):
    page = _page((0, 0, 100, 100))
    out = render_guide(page, tmp_path / "guide.png")
    img = Image.open(out)
    assert img.size == (GUIDE_WIDTH, GUIDE_HEIGHT)
    assert img.getpixel((5, 5)) == (255, 255, 255)
    x0, y0, _, _ = panel_box(page.panels[0].layout)
    assert img.getpixel((x0 + 2, y0 + 50)) == (0, 0, 0)


def test_detects_grid_with_differently_split_rows():
    boxes = [(40, 40, 984, 500), (40, 520, 500, 1000), (520, 520, 984, 1000), (40, 1020, 984, 1496)]
    assert sorted(detect_panel_boxes(_shaded_page(boxes))) == sorted(
        (x0, y0, x1 + 1, y1 + 1) for x0, y0, x1, y1 in boxes
    )


def test_detects_column_split_into_stacked_panels():
    boxes = [(40, 40, 500, 1496), (520, 40, 984, 760), (520, 780, 984, 1496)]
    assert len(detect_panel_boxes(_shaded_page(boxes))) == 3


def test_measured_layout_follows_shifted_drawing(tmp_path):
    page = _page((0, 0, 100, 40), (0, 40, 100, 60))
    # 生成 AI が上のコマを 60px 低く描いた想定
    top = panel_box(page.panels[0].layout)
    bottom = panel_box(page.panels[1].layout)
    shifted = [(top[0], top[1], top[2], top[3] + 60), (bottom[0], bottom[1] + 60, bottom[2], bottom[3])]
    path = tmp_path / "gen.png"
    _shaded_page(shifted).save(path)

    measured = measure_rendered_layouts(page, path)
    assert abs(measured[0].height * GUIDE_HEIGHT / 100 - (top[3] + 60 - top[1])) < 3
    assert abs(measured[1].y * GUIDE_HEIGHT / 100 - (bottom[1] + 60)) < 3


def test_unmatched_panel_falls_back_to_planned_position(tmp_path):
    page = _page((0, 0, 100, 50), (0, 50, 100, 50))
    path = tmp_path / "blank.png"
    Image.new("RGB", (GUIDE_WIDTH, GUIDE_HEIGHT), "white").save(path)

    measured = measure_rendered_layouts(page, path)
    x0, y0, _, _ = panel_box(page.panels[1].layout)
    assert round(measured[1].y * GUIDE_HEIGHT / 100) == y0
