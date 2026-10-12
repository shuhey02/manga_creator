from PIL import Image, ImageDraw

from app.models.schemas import SpeechBubble, SpeechBubblePosition
from app.services.image_assembler import _draw_bubble, _get_font, _is_vertical
from app.services.vertical_text import draw_vertical, fit_vertical, split_columns


def _ink_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


def test_line_head_punctuation_hangs_on_previous_column():
    assert split_columns("なんだ、これ", 3) == [list("なんだ、"), list("これ")]


def test_newline_starts_a_new_column():
    assert split_columns("勇者よ\nやっと", 10) == [list("勇者よ"), list("やっと")]


def test_half_width_marks_become_full_width():
    assert split_columns("え?!", 10) == [list("え？！")]


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
