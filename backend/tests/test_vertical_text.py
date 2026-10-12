from PIL import Image, ImageDraw

from app.models.schemas import Panel, PanelLayout, SpeechBubble, SpeechBubblePosition
from app.services.image_assembler import _draw_bubble, _draw_sfx, _get_font, _is_vertical
from app.services.vertical_text import draw_vertical, fit_vertical, split_columns, tokenize


def _ink_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


def test_line_head_punctuation_hangs_on_previous_column():
    assert split_columns("なんだ、これ", 3) == [list("なんだ、"), list("これ")]


def test_newline_starts_a_new_column():
    assert split_columns("勇者よ\nやっと", 10) == [list("勇者よ"), list("やっと")]


def test_single_marks_become_full_width():
    assert split_columns("え!", 10) == [list("え！")]


def test_short_alnum_and_mark_pairs_share_one_cell():
    assert tokenize("12時に3Fで!?") == ["12", "時", "に", "3F", "で", "!?"]


def test_long_alnum_stands_upright_in_full_width():
    assert tokenize("2026年") == list("２０２６年")
    assert tokenize("１２時") == ["12", "時"]


def test_mark_pair_at_column_head_hangs_on_previous_column():
    assert split_columns("本当!?", 2) == [["本", "当", "!?"]]


def test_tate_chu_yoko_cell_fits_in_one_column_width():
    img = Image.new("RGB", (200, 200), "white")
    layout = fit_vertical("12", 200, 200, _get_font, max_size=40)
    draw_vertical(ImageDraw.Draw(img), layout, _get_font(layout.font_size), (100, 100))
    x0, _, x1, _ = _ink_bbox(img)
    assert x1 - x0 <= layout.font_size


def test_fit_picks_one_column_for_short_text_in_tall_box():
    layout = fit_vertical("わっ！", 60, 300, _get_font)
    assert len(layout.columns) == 1
    assert layout.font_size == 34


def test_long_text_wraps_into_more_columns_and_fits_width():
    layout = fit_vertical("ここはどこだ。夢じゃないのか。ずっと続いている。", 120, 200, _get_font)
    width = len(layout.columns) * layout.font_size * 1.25 - layout.font_size * 0.25
    assert len(layout.columns) > 1
    assert width <= 120


def test_first_column_is_drawn_on_the_right():
    img = Image.new("RGB", (200, 200), "white")
    layout = fit_vertical("あ\nいいいいい", 200, 200, _get_font)
    draw_vertical(ImageDraw.Draw(img), layout, _get_font(layout.font_size), (100, 100))
    # 2列目（左）だけが縦に長いので、インクの下端は左半分にある
    left_bottom = _ink_bbox(img.crop((0, 0, 100, 200)))[3]
    right_bottom = _ink_bbox(img.crop((100, 0, 200, 200)))[3]
    assert left_bottom > right_bottom


def _bubble(orientation: str, width: float, height: float) -> SpeechBubble:
    return SpeechBubble(
        text="テスト", orientation=orientation,
        position=SpeechBubblePosition(x=0, y=0, width=width, height=height),
    )


def test_auto_orientation_follows_bubble_shape():
    assert _is_vertical(_bubble("auto", 10, 40), 50, 200)
    assert not _is_vertical(_bubble("auto", 40, 10), 200, 50)
    assert _is_vertical(_bubble("vertical", 40, 10), 200, 50)


def test_vertical_bubble_text_is_taller_than_wide():
    img = Image.new("RGB", (400, 400), "white")
    _draw_bubble(ImageDraw.Draw(img), SpeechBubble(
        text="なんだこれは", type="thought",
        position=SpeechBubblePosition(x=40, y=5, width=20, height=80),
    ), 0, 0, 400, 400)
    # 吹き出しの枠を除き、内側の文字だけを測る
    x0, y0, x1, y1 = _ink_bbox(img.crop((175, 60, 225, 330)))
    assert y1 - y0 > 3 * (x1 - x0)


def _sfx_panel(**kwargs) -> Panel:
    return Panel(panel_number=1, layout=PanelLayout(x=0, y=0, width=100, height=100),
                 sound_effect="ドォン", **kwargs)


def _sfx_ink(panel: Panel) -> tuple[int, int, int, int]:
    """灰色の背景に効果音だけを描き、白抜き文字の位置を返す"""
    img = Image.new("RGB", (400, 600), (128, 128, 128))
    _draw_sfx(ImageDraw.Draw(img), panel, 0, 0, 400, 600)
    return img.convert("L").point(lambda v: 255 if v > 200 else 0).getbbox()


def test_sfx_is_vertical_along_the_right_edge_by_default():
    x0, y0, x1, y1 = _sfx_ink(_sfx_panel())
    assert x0 > 200
    assert y1 - y0 > 2 * (x1 - x0)


def test_sfx_moves_to_the_left_edge_when_a_bubble_is_on_the_right():
    bubble = SpeechBubble(text="わっ", position=SpeechBubblePosition(x=75, y=0, width=25, height=60))
    x0, _, x1, _ = _sfx_ink(_sfx_panel(speech_bubbles=[bubble]))
    assert x1 < 200


def test_horizontal_sfx_keeps_the_old_layout():
    x0, y0, x1, y1 = _sfx_ink(_sfx_panel(sound_effect_orientation="horizontal"))
    assert x1 - x0 > y1 - y0


def test_sfx_stays_in_one_column_when_it_fits():
    layout = fit_vertical("ヴォォォン", 120, 420, _get_font, max_size=80, min_size=20, max_columns=1)
    assert len(layout.columns) == 1
    assert layout.height <= 420
