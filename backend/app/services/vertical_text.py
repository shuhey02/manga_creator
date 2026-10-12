"""
吹き出し用の縦書き描画。

Pillow の縦書き（direction="ttb"）は libraqm が要り、Windows の標準 wheel には入っていない。
そのため1文字ずつ置く：列は右から左、句読点は右上、長音・三点リーダ・括弧は90°回転、
小書き仮名は右上へ寄せ、行頭禁則の文字は前の列にぶら下げる。
"""
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

# 縦書きで向きを変える文字（横書き用の字形を時計回りに90°回して使う）
ROTATED = set("ー―─－-~〜～…‥=＝（）()「」『』【】〔〕［］[]｛｝{}＜＞<>《》〈〉:：")
# 縦書きで升目の右上に置く文字
PUNCTUATION = set("、。，．,.")
SMALL_KANA = set("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ")
# 列の先頭に来てはいけない文字（来たら前の列の末尾にぶら下げる）
LINE_HEAD_NG = PUNCTUATION | SMALL_KANA | set("」』）)】〕］]}｝＞>》〉ー〜～！？!?…‥")
# 半角の記号は縦書きでは全角にそろえる
HALF_TO_FULL = str.maketrans({"!": "！", "?": "？"})

COLUMN_GAP = 0.25   # 列の間隔（文字サイズに対する比）
PUNCT_SHIFT = 0.55
SMALL_KANA_SHIFT = 0.12


@dataclass
class VerticalLayout:
    font_size: int
    columns: list[list[str]]

    @property
    def rows(self) -> int:
        return max((len(c) for c in self.columns), default=0)

    @property
    def width(self) -> float:
        n = len(self.columns)
        return n * self.font_size + (n - 1) * self.font_size * COLUMN_GAP

    @property
    def height(self) -> float:
        return self.rows * self.font_size


def split_columns(text: str, chars_per_column: int) -> list[list[str]]:
    """
    右の列から順に、1列 chars_per_column 文字で区切る。改行は列の区切りとして扱う。
    行頭禁則の文字は前の列の末尾にぶら下げるので、その列だけ1文字長くなることがある。
    """
    columns: list[list[str]] = []
    for paragraph in text.translate(HALF_TO_FULL).split("\n"):
        current: list[str] = []
        for ch in paragraph:
            if len(current) >= chars_per_column:
                if ch in LINE_HEAD_NG:
                    current.append(ch)
                    continue
                columns.append(current)
                current = []
            current.append(ch)
        columns.append(current)
    return [c for c in columns if c] or [[]]


def fit_vertical(
    text: str, box_w: int, box_h: int, get_font: Callable[[int], ImageFont.ImageFont],
    max_size: int = 34, min_size: int = 14, max_columns: int | None = None,
) -> VerticalLayout:
    """
    box に収まる最大の文字サイズと列分けを選ぶ。収まらなければ最小サイズで返す。
    max_columns を渡すと、その列数以内に収まるサイズだけを候補にする。
    """
    for size in range(max_size, min_size - 1, -2):
        per_column = max(1, box_h // size)
        columns = split_columns(text, per_column)
        layout = VerticalLayout(size, columns)
        # ぶら下げた1文字は余白にはみ出してよい
        fits_columns = max_columns is None or len(columns) <= max_columns
        if fits_columns and layout.width <= box_w and layout.rows <= per_column + 1:
            return layout
    return VerticalLayout(min_size, split_columns(text, max(1, box_h // min_size)))


def _rotated_glyph(ch: str, font: ImageFont.ImageFont, box: int, stroke_width: int) -> Image.Image:
    glyph = Image.new("L", (box, box), 0)
    ImageDraw.Draw(glyph).text((box / 2, box / 2), ch, fill=255, font=font, anchor="mm",
                               stroke_width=stroke_width, stroke_fill=255)
    return glyph.rotate(-90)


def draw_vertical(
    draw: ImageDraw.ImageDraw, layout: VerticalLayout, font: ImageFont.ImageFont,
    center: tuple[int, int], fill: str = "black",
    stroke_width: int = 0, stroke_fill: str | None = None,
) -> None:
    """
    layout を center を中心に描く。列は右から左、全列とも上端をそろえる。
    stroke_width を渡すと stroke_fill の縁取りを付ける（効果音の白抜き文字用）。
    """
    size = layout.font_size
    pitch = size * (1 + COLUMN_GAP)
    right = center[0] + layout.width / 2
    top = center[1] - layout.height / 2
    stroke = {"stroke_width": stroke_width, "stroke_fill": stroke_fill} if stroke_width else {}

    for col_index, column in enumerate(layout.columns):
        cx = right - col_index * pitch - size / 2
        for row, ch in enumerate(column):
            cy = top + row * size + size / 2
            if ch in ROTATED:
                box = size + 2 * stroke_width
                corner = (round(cx - box / 2), round(cy - box / 2))
                # 縁取りを先に塗り、その上に文字本体を重ねる
                if stroke_width:
                    draw.bitmap(corner, _rotated_glyph(ch, font, box, stroke_width), fill=stroke_fill)
                draw.bitmap(corner, _rotated_glyph(ch, font, box, 0), fill=fill)
                continue
            if ch in PUNCTUATION:
                # 横書き用の字形は升目の左下にあるので、升目ごと右上へずらして右上に置く
                xy = (cx + size * PUNCT_SHIFT, cy - size * PUNCT_SHIFT)
            elif ch in SMALL_KANA:
                xy = (cx + size * SMALL_KANA_SHIFT, cy - size * SMALL_KANA_SHIFT)
            else:
                xy = (cx, cy)
            draw.text(xy, ch, fill=fill, font=font, anchor="mm", **stroke)
