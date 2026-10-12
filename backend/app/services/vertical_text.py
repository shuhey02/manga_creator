"""
吹き出し用の縦書き描画。

Pillow の縦書き（direction="ttb"）は libraqm が要り、Windows の標準 wheel には入っていない。
そのため1文字ずつ置く：列は右から左、句読点は右上、長音・三点リーダ・括弧は90°回転、
小書き仮名は右上へ寄せ、行頭禁則の文字は前の列にぶら下げる。
2文字までの英数字と「!?」は縦中横（1マスに横向き）、3文字以上の英数字は全角にして縦に並べる。
"""
import re
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
# 全角英数字は半角にそろえてから、縦中横にするか全角で立てるかを決める
FULL_ALNUM_TO_HALF = str.maketrans(
    {chr(c + 0xFEE0): chr(c) for c in range(0x21, 0x7F) if chr(c).isalnum()}
)
TATE_CHU_YOKO_MAX = 2
# 英数字の連続、または「!?」「!!」などの2文字の組
_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z]+|[!?！？]{2}")

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


def _to_full_width(text: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in text)


def tokenize(paragraph: str) -> list[str]:
    """
    1マス分ずつの文字列に分ける。普通は1文字だが、縦中横にするものは2文字で1マスになる。
    """
    text = paragraph.translate(FULL_ALNUM_TO_HALF)
    cells: list[str] = []
    pos = 0
    for match in _TOKEN_PATTERN.finditer(text):
        cells += list(text[pos:match.start()].translate(HALF_TO_FULL))
        token = match.group()
        if token[0] in "!?！？":
            cells.append(token.translate({ord("！"): "!", ord("？"): "?"}))
        elif len(token) <= TATE_CHU_YOKO_MAX:
            cells.append(token)
        else:
            cells += list(_to_full_width(token))
        pos = match.end()
    cells += list(text[pos:].translate(HALF_TO_FULL))
    return cells


def is_tate_chu_yoko(cell: str) -> bool:
    return len(cell) > 1


def _is_line_head_ng(cell: str) -> bool:
    return cell in LINE_HEAD_NG or (is_tate_chu_yoko(cell) and cell[0] in "!?")


def split_columns(text: str, chars_per_column: int) -> list[list[str]]:
    """
    右の列から順に、1列 chars_per_column マスで区切る。改行は列の区切りとして扱う。
    行頭禁則の文字は前の列の末尾にぶら下げるので、その列だけ1マス長くなることがある。
    """
    columns: list[list[str]] = []
    for paragraph in text.split("\n"):
        current: list[str] = []
        for cell in tokenize(paragraph):
            if len(current) >= chars_per_column:
                if _is_line_head_ng(cell):
                    current.append(cell)
                    continue
                columns.append(current)
                current = []
            current.append(cell)
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


def _draw_tate_chu_yoko(
    draw: ImageDraw.ImageDraw, cell: str, font: ImageFont.ImageFont, size: int,
    center: tuple[float, float], fill: str, stroke: dict,
) -> None:
    """1マスに横向きで収める。升目の幅を超えるなら文字を縮める"""
    width = font.getlength(cell)
    if width > size * 0.95 and hasattr(font, "font_variant"):
        font = font.font_variant(size=max(8, int(font.size * size * 0.95 / width)))
    draw.text(center, cell, fill=fill, font=font, anchor="mm", **stroke)


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
            if is_tate_chu_yoko(ch):
                _draw_tate_chu_yoko(draw, ch, font, size, (cx, cy), fill, stroke)
                continue
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
