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


def test_a_space_always_starts_a_new_column():
    columns = split_columns("8月26日 23時45分 新宿発の中央線快速", 9)
    assert ["".join(c) for c in columns] == ["8月26日", "23時45分", "新宿発の中央線快速"]


def test_columns_break_after_ellipsis_instead_of_mid_word():
    columns = split_columns("ないんじゃ…盗まれたんよ", 8)
    assert ["".join(c) for c in columns] == ["ないんじゃ…", "盗まれたんよ"]


def test_fit_avoids_a_one_character_column():
    # 文字単位で詰めると「速」だけが最後の列に回る幅と高さ
    layout = fit_vertical("8月26日 23時45分 新宿発の中央線快速", 200, 9 * 30, _get_font, max_size=34)
    assert all(len(c) > 1 for c in layout.columns)
    assert not layout.awkward


def test_columns_break_where_hiragana_meets_katakana_or_kanji():
    columns = split_columns("クレジットカードもキャッシュカードも全部止めて", 10)
    assert ["".join(c) for c in columns] == ["クレジットカードも", "キャッシュカードも", "全部止めて"]


def test_honorific_prefix_stays_with_its_noun():
    from app.services.vertical_text import _phrases
    assert ["".join(p.cells) for p in _phrases(tokenize("番号のご利用"))] == ["番号のご利用"]


def test_small_bubble_grows_until_text_is_readable():
    from app.services.image_assembler import MIN_READABLE_SIZE, _fit_bubble_text
    bubble = SpeechBubble(text="家の鍵も!?", type="shout",
                          position=SpeechBubblePosition(x=5, y=5, width=16, height=35))
    rect, layout = _fit_bubble_text(bubble, (20, 20, 60, 130), 7, _get_font, 0, 0, 600, 420)
    assert layout.font_size >= MIN_READABLE_SIZE
    assert rect[2] > 60 and rect[3] > 130


def test_bold_font_is_heavier_than_regular():
    def ink(font) -> int:
        img = Image.new("L", (200, 60), 0)
        ImageDraw.Draw(img).text((0, 0), "国国国", fill=255, font=font)
        return sum(img.histogram()[129:])
    assert ink(_get_font(30, bold=True)) > ink(_get_font(30)) * 1.2


def test_single_marks_become_full_width():
    assert split_columns("え!", 10) == [list("え！")]


def test_short_alnum_and_mark_pairs_share_one_cell():
    assert tokenize("12時に3Fで!?") == ["12", "時", "に", "3F", "で", "!?"]


def test_thousands_separator_does_not_split_a_number():
    assert tokenize("13,800円") == list("１３８００円")
    assert tokenize("はい、3,5") == list("はい、") + ["3", ",", "5"]


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


def _panel_with(*bubbles: SpeechBubble) -> Panel:
    return Panel(panel_number=1, layout=PanelLayout(x=0, y=0, width=100, height=100),
                 speech_bubbles=list(bubbles))


def test_page_bubbles_share_one_font_size():
    from app.services.image_assembler import _fit_page_bubbles
    short = SpeechBubble(text="えっ", position=SpeechBubblePosition(x=70, y=5, width=20, height=40))
    long = SpeechBubble(text="ここはどこだ 夢じゃないのか ずっと続いている",
                        position=SpeechBubblePosition(x=10, y=5, width=20, height=40))
    fitted = _fit_page_bubbles([(_panel_with(short, long), (0, 0, 600, 600))])
    assert fitted[id(short)][1].font_size == fitted[id(long)][1].font_size


def test_growing_bubble_does_not_cover_its_neighbour():
    from app.services.image_assembler import _fit_page_bubbles, _rects_overlap
    right = SpeechBubble(text="家の鍵もないんか!?", type="shout",
                         position=SpeechBubblePosition(x=70, y=5, width=10, height=25))
    left = SpeechBubble(text="あれ", position=SpeechBubblePosition(x=52, y=5, width=17, height=40))
    fitted = _fit_page_bubbles([(_panel_with(right, left), (0, 0, 600, 420))])
    assert not _rects_overlap(fitted[id(right)][0], fitted[id(left)][0])


def test_tail_points_toward_the_speaker():
    from app.models.schemas import TailTarget
    img = Image.new("RGB", (400, 400), "white")
    _draw_bubble(ImageDraw.Draw(img), SpeechBubble(
        text="あ", position=SpeechBubblePosition(x=60, y=5, width=20, height=30),
        tail=TailTarget(x=10, y=50),
    ), 0, 0, 400, 400)
    # しっぽは左下（話し手の方）へ伸び、右下には出ない
    assert _ink_bbox(img.crop((150, 125, 240, 220))) is not None
    assert _ink_bbox(img.crop((330, 125, 400, 220))) is None


def test_narration_has_no_tail():
    img = Image.new("RGB", (400, 400), "white")
    _draw_bubble(ImageDraw.Draw(img), SpeechBubble(
        text="翌日", type="narration", position=SpeechBubblePosition(x=40, y=5, width=20, height=30),
    ), 0, 0, 400, 400)
    assert _ink_bbox(img.crop((0, 150, 400, 400))) is None


def test_font_scale_enlarges_one_bubble_relative_to_the_page():
    from app.services.image_assembler import _fit_page_bubbles
    normal = SpeechBubble(text="えっ", position=SpeechBubblePosition(x=70, y=5, width=20, height=40))
    big = SpeechBubble(text="止めて！", font_scale=1.5,
                       position=SpeechBubblePosition(x=10, y=5, width=25, height=60))
    fitted = _fit_page_bubbles([(_panel_with(normal, big), (0, 0, 600, 600))])
    assert fitted[id(big)][1].font_size == round(fitted[id(normal)][1].font_size * 1.5)


def test_horizontal_wrap_breaks_at_explicit_newline():
    from app.services.image_assembler import _wrap_text
    assert _wrap_text("落とし穴に\nはまった", _get_font(20), 1000) == ["落とし穴に", "はまった"]
