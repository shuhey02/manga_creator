"""
吹き出し用の縦書き描画。

Pillow の縦書き（direction="ttb"）は libraqm が要り、Windows の標準 wheel には入っていない。
そのため1文字ずつ置く：列は右から左、句読点は右上、長音・三点リーダ・括弧は90°回転、
小書き仮名は右上へ寄せ、行頭禁則の文字は前の列にぶら下げる。
2文字までの英数字と「!?」は縦中横（1マスに横向き）、3文字以上の英数字は全角にして縦に並べる。
列は空白・句読点・感嘆符の位置で改め、語の途中で折ったり最後の列が1文字だけになったりするのを避ける。
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
# 句の区切り。空白の位置と、これらの文字の直後で列を改めてよい
SPACES = {" ", "　"}
BREAK_AFTER = PUNCTUATION | set("…‥！？」』）)】〕］]")
# 読みやすい列分けのために、収まる最大の文字サイズからどこまで小さくしてよいか
AWKWARD_SHRINK = 0.75
# 全角英数字は半角にそろえてから、縦中横にするか全角で立てるかを決める
FULL_ALNUM_TO_HALF = str.maketrans(
    {chr(c + 0xFEE0): chr(c) for c in range(0x21, 0x7F) if chr(c).isalnum()}
)
TATE_CHU_YOKO_MAX = 2
# 英数字の連続、または「!?」「!!」などの2文字の組
_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z]+|[!?！？]{2}")
_THOUSANDS_SEPARATOR = re.compile(r"(?<=[0-9])[,，](?=[0-9]{3}(?![0-9]))")

COLUMN_GAP = 0.25   # 列の間隔（文字サイズに対する比）
PUNCT_SHIFT = 0.55
SMALL_KANA_SHIFT = 0.12


@dataclass
class VerticalLayout:
    font_size: int
    columns: list[list[str]]
    # 句の途中で折った・最後の列が1文字だけ、のどちらかがある（吹き出しを広げる目安）
    awkward: bool = False
    # どの文字サイズでも枠に収まらず、はみ出している
    overflow: bool = False

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
    # 桁区切りのカンマは縦書きで数字を分断するので外す（13,800 → 13800 を1つの数として立てる）
    text = _THOUSANDS_SEPARATOR.sub("", paragraph.translate(FULL_ALNUM_TO_HALF))
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


def _is_hiragana(cell: str) -> bool:
    return len(cell) == 1 and "ぁ" <= cell <= "ゟ"


def _is_kanji_or_katakana(cell: str) -> bool:
    return len(cell) == 1 and ("ァ" <= cell <= "ヺ" or "一" <= cell <= "鿿" or cell == "々")


def _ends_with_particle(cell: str, following: str) -> bool:
    """
    ひらがなの後に漢字・カタカナが続く位置（「カードも｜キャッシュ」「番号の｜入力」）を語の切れ目とみなす。
    形態素解析を使わない近似。接頭語の「お」「ご」（お金・ご利用）の後では切らない。
    """
    return _is_hiragana(cell) and cell not in "おご" and _is_kanji_or_katakana(following)


@dataclass
class _Phrase:
    cells: list[str]
    spaced: bool = False  # 前の句と空白で区切られていた
    weak: bool = False    # 前の句との境が「ひらがな→漢字・カタカナ」の弱い切れ目


def _phrases(cells: list[str]) -> list[_Phrase]:
    """
    改行してよい位置で区切った句の一覧。
    空白の位置、句読点・感嘆符・閉じ括弧の直後を強い切れ目、ひらがなから漢字・カタカナに変わる位置を弱い切れ目とする。
    """
    phrases: list[_Phrase] = []
    current = _Phrase([])
    for i, cell in enumerate(cells):
        if cell in SPACES:
            if current.cells:
                phrases.append(current)
            current = _Phrase([], spaced=True)
            continue
        current.cells.append(cell)
        following = cells[i + 1] if i + 1 < len(cells) else None
        if not following or following in SPACES or _is_line_head_ng(following):
            continue
        strong = cell in BREAK_AFTER or (is_tate_chu_yoko(cell) and cell[0] in "!?")
        if strong or _ends_with_particle(cell, following):
            phrases.append(current)
            current = _Phrase([], weak=not strong)
    if current.cells:
        phrases.append(current)
    return phrases


def _fits(length: int, last_cell: str, chars_per_column: int) -> bool:
    # 行頭禁則の文字で終わるなら、その1マスは列の下にぶら下げてよい
    return length <= chars_per_column or (
        length == chars_per_column + 1 and _is_line_head_ng(last_cell)
    )


# 列分けの読みやすさ。小さいほど良い
CLEAN, WEAK_BREAK, AWKWARD = 0, 1, 2


def _split_paragraph(paragraph: str, chars_per_column: int) -> tuple[list[list[str]], int]:
    """1段落を列に分け、読みやすさ（CLEAN / WEAK_BREAK / AWKWARD）も返す"""
    columns: list[list[str]] = []
    current: list[str] = []
    level = CLEAN
    for p in _phrases(tokenize(paragraph)):
        phrase = p.cells
        # 空白は台本で「ここで列を改める」の意味なので、空白の後は必ず次の列から始める
        if p.spaced and current:
            columns.append(current)
            current = []
        joined = current + phrase
        if _fits(len(joined), phrase[-1], chars_per_column):
            current = joined
            continue
        if current:
            columns.append(current)
            current = []
            if p.weak:
                level = max(level, WEAK_BREAK)
        if _fits(len(phrase), phrase[-1], chars_per_column):
            current = phrase
            continue
        # 1列に収まらない長い句だけは、文字単位で折る（行頭禁則の文字はぶら下げる）
        level = AWKWARD
        for cell in phrase:
            if len(current) >= chars_per_column:
                if _is_line_head_ng(cell):
                    current.append(cell)
                    continue
                columns.append(current)
                current = []
            current.append(cell)
    columns.append(current)
    columns = [c for c in columns if c]
    if len(columns) > 1 and len(columns[-1]) == 1:
        level = AWKWARD  # 最後の列が1文字だけ
    return columns, level


def _split(text: str, chars_per_column: int) -> tuple[list[list[str]], int]:
    """列分けと、その読みやすさ（全段落のうち最も悪いもの）を返す"""
    columns: list[list[str]] = []
    level = CLEAN
    for paragraph in text.split("\n"):
        paragraph_columns, paragraph_level = _split_paragraph(paragraph, chars_per_column)
        level = max(level, paragraph_level)
        columns += paragraph_columns
    return columns or [[]], level


def split_columns(text: str, chars_per_column: int) -> list[list[str]]:
    """
    右の列から順に、1列 chars_per_column マスで区切る。改行は列の区切りとして扱う。
    句（空白・句読点・感嘆符で区切ったまとまり）が丸ごと入らなければ次の列へ送り、語の途中で折らない。
    行頭禁則の文字は前の列の末尾にぶら下げるので、その列だけ1マス長くなることがある。
    """
    return _split(text, chars_per_column)[0]


def fit_vertical(
    text: str, box_w: int, box_h: int, get_font: Callable[[int], ImageFont.ImageFont],
    max_size: int = 34, min_size: int = 14, max_columns: int | None = None,
    shrink: float = AWKWARD_SHRINK,
) -> VerticalLayout:
    """
    box に収まる最大の文字サイズと列分けを選ぶ。収まらなければはみ出したまま返す（overflow）。
    max_columns を渡すと、その列数以内に収まるサイズだけを候補にする。
    収まる最大サイズの列分けが読みにくければ、文字を少し（最大 shrink 倍まで）小さくして、
    強い切れ目（空白・句読点）だけで改行できる列分け、次に語の途中で折らない列分けを探す。
    shrink=1.0 なら max_size だけを試す（ページ内で文字サイズをそろえるとき）。
    """
    best: dict[int, VerticalLayout] = {}
    largest: VerticalLayout | None = None
    for size in range(max_size, min_size - 1, -2):
        if largest and size < largest.font_size * shrink:
            break
        per_column = max(1, box_h // size)
        columns, level = _split(text, per_column)
        layout = VerticalLayout(size, columns, awkward=level == AWKWARD)
        # ぶら下げた1文字は余白にはみ出してよい
        fits_columns = max_columns is None or len(columns) <= max_columns
        fits = fits_columns and layout.width <= box_w and layout.rows <= per_column + 1
        if fits and level == CLEAN:
            return layout
        if fits:
            best.setdefault(level, layout)
            largest = largest or layout
        if shrink >= 1.0:
            break
    for level in (WEAK_BREAK, AWKWARD):
        if level in best:
            return best[level]
    size = max_size if shrink >= 1.0 else min_size
    columns, level = _split(text, max(1, box_h // size))
    return VerticalLayout(size, columns, awkward=level == AWKWARD, overflow=True)


def _rotated_glyph(ch: str, font: ImageFont.ImageFont, box: int, stroke_width: int) -> Image.Image:
    glyph = Image.new("L", (box, box), 0)
    ImageDraw.Draw(glyph).text((box / 2, box / 2), ch, fill=255, font=font, anchor="mm",
                               stroke_width=stroke_width, stroke_fill=255)
    return glyph.rotate(-90)


def _draw_tate_chu_yoko(
    draw: ImageDraw.ImageDraw, cell: str, font: ImageFont.ImageFont, size: int,
    center: tuple[float, float], fill: str, stroke: dict,
    resize: Callable[[int], ImageFont.ImageFont] | None,
) -> None:
    """1マスに横向きで収める。升目の幅を超えるなら文字を縮める"""
    width = font.getlength(cell)
    if width > size * 0.95 and hasattr(font, "font_variant"):
        smaller = max(8, int(font.size * size * 0.95 / width))
        font = resize(smaller) if resize else font.font_variant(size=smaller)
    draw.text(center, cell, fill=fill, font=font, anchor="mm", **stroke)


def draw_vertical(
    draw: ImageDraw.ImageDraw, layout: VerticalLayout, font: ImageFont.ImageFont,
    center: tuple[int, int], fill: str = "black",
    stroke_width: int = 0, stroke_fill: str | None = None,
    resize: Callable[[int], ImageFont.ImageFont] | None = None,
) -> None:
    """
    layout を center を中心に描く。列は右から左、全列とも上端をそろえる。
    stroke_width を渡すと stroke_fill の縁取りを付ける（効果音の白抜き文字用）。
    resize は縦中横を縮めるときに同じ書体・太さのフォントを返す関数。
    可変フォントは font_variant で太さが既定値に戻るため、太さを指定し直せる側から渡す。
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
                _draw_tate_chu_yoko(draw, ch, font, size, (cx, cy), fill, stroke, resize)
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
