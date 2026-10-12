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
    max_size: int = 34, min_size: int = 14,
) -> VerticalLayout:
    """box に収まる最大の文字サイズと列分けを選ぶ。収まらなければ最小サイズで返す"""
    for size in range(max_size, min_size - 1, -2):
        per_column = max(1, box_h // size)
        columns = split_columns(text, per_column)
        width = len(columns) * size + (len(columns) - 1) * size * COLUMN_GAP
        # ぶら下げた1文字は余白にはみ出してよい
        if width <= box_w and max(len(c) for c in columns) <= per_column + 1:
            return VerticalLayout(size, columns)
    return VerticalLayout(min_size, split_columns(text, max(1, box_h // min_size)))


def _rotated_glyph(ch: str, font: ImageFont.ImageFont, size: int) -> Image.Image:
    glyph = Image.new("L", (size, size), 0)
    ImageDraw.Draw(glyph).text((size / 2, size / 2), ch, fill=255, font=font, anchor="mm")
    return glyph.rotate(-90)


def draw_vertical(
    draw: ImageDraw.ImageDraw, layout: VerticalLayout, font: ImageFont.ImageFont,
    center: tuple[int, int], fill: str = "black",
) -> None:
    """layout を center を中心に描く。列は右から左、全列とも上端をそろえる"""
    size = layout.font_size
    pitch = size * (1 + COLUMN_GAP)
    block_w = len(layout.columns) * size + (len(layout.columns) - 1) * size * COLUMN_GAP
    block_h = layout.rows * size
    right = center[0] + block_w / 2
    top = center[1] - block_h / 2

    for col_index, column in enumerate(layout.columns):
        cx = right - col_index * pitch - size / 2
        for row, ch in enumerate(column):
            cy = top + row * size + size / 2
            if ch in ROTATED:
                draw.bitmap((round(cx - size / 2), round(cy - size / 2)),
                            _rotated_glyph(ch, font, size), fill=fill)
            elif ch in PUNCTUATION:
                # 横書き用の字形は升目の左下にあるので、升目ごと右上へずらして右上に置く
                draw.text((cx + size * PUNCT_SHIFT, cy - size * PUNCT_SHIFT), ch,
                          fill=fill, font=font, anchor="mm")
            elif ch in SMALL_KANA:
                draw.text((cx + size * SMALL_KANA_SHIFT, cy - size * SMALL_KANA_SHIFT), ch,
                          fill=fill, font=font, anchor="mm")
            else:
                draw.text((cx, cy), ch, fill=fill, font=font, anchor="mm")
