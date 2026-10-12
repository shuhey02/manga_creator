"""
生成されたページ画像から実際のコマ枠を検出し、ネームのコマと対応づける。

gpt-image-2 はガイドの枠を数%ずらして描くことがあるため、吹き出しを
ネーム通りの座標に置くと絵とずれる。枠と枠の間の白い溝（ガター）は
端から端まで白一色になる、という性質を使って XY 分割で枠を求める。
"""
from pathlib import Path

from PIL import Image

from ..models.schemas import MangaPage, PanelLayout
from .layout_guide import panel_box

Box = tuple[int, int, int, int]

WHITE_LEVEL = 225        # これ以上明るい画素を白とみなす
# 溝の行（列）に許す黒画素の数。コマ内の白い空の行も左右の枠線で数px黒くなるので、
# 割合ではなく画素数で見ないと、大きなコマの空を溝と取り違える
MAX_GUTTER_DARK_PX = 5
MIN_GUTTER_PX = 4
MIN_PANEL_RATIO = 0.06   # 画像の辺に対してこれより細い帯はコマとみなさない
MIN_MATCH_IOU = 0.5


def _white_runs(flags: list[bool]) -> list[tuple[int, int]]:
    """True が続く区間 [start, end) の一覧"""
    runs: list[tuple[int, int]] = []
    start = None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(flags)))
    return runs


def _split(mask: Image.Image, box: Box, horizontal_gutters: bool) -> list[tuple[int, int]]:
    """
    box 内を、端から端まで白い溝で区切った帯の一覧（絶対座標）。
    horizontal_gutters=True なら横の溝で上下に分け、False なら縦の溝で左右に分ける。
    """
    x0, y0, x1, y1 = box
    region = mask.crop(box)
    if horizontal_gutters:
        # BOX 縮小で各行の平均＝白画素の割合になる
        means = list(region.resize((1, y1 - y0), Image.BOX).tobytes())
        origin, length, span = y0, y1 - y0, x1 - x0
    else:
        means = list(region.resize((x1 - x0, 1), Image.BOX).tobytes())
        origin, length, span = x0, x1 - x0, y1 - y0
    is_gutter = [(255 - v) * span / 255 <= MAX_GUTTER_DARK_PX for v in means]
    gutters = [r for r in _white_runs(is_gutter) if r[1] - r[0] >= MIN_GUTTER_PX]
    bands: list[tuple[int, int]] = []
    cursor = 0
    for g0, g1 in gutters:
        if g0 > cursor:
            bands.append((origin + cursor, origin + g0))
        cursor = g1
    if cursor < length:
        bands.append((origin + cursor, origin + length))
    return bands


def detect_panel_boxes(image: Image.Image) -> list[Box]:
    mask = image.convert("L").point(lambda v: 255 if v >= WHITE_LEVEL else 0)
    w, h = mask.size
    min_w, min_h = w * MIN_PANEL_RATIO, h * MIN_PANEL_RATIO

    boxes: list[Box] = []
    for y0, y1 in _split(mask, (0, 0, w, h), horizontal_gutters=True):
        if y1 - y0 < min_h:
            continue
        for x0, x1 in _split(mask, (0, y0, w, y1), horizontal_gutters=False):
            if x1 - x0 < min_w:
                continue
            # 列ごとに段組みが違うページ向けに、列の中の横の溝でもう一度分ける
            for sy0, sy1 in _split(mask, (x0, y0, x1, y1), horizontal_gutters=True):
                if sy1 - sy0 >= min_h:
                    boxes.append((x0, sy0, x1, sy1))
    return boxes


def _iou(a: Box, b: Box) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def _to_percent(box: Box, w: int, h: int) -> PanelLayout:
    x0, y0, x1, y1 = box
    return PanelLayout(
        x=100 * x0 / w, y=100 * y0 / h,
        width=max(1.0, 100 * (x1 - x0) / w), height=max(1.0, 100 * (y1 - y0) / h),
    )


def measure_rendered_layouts(page: MangaPage, image: Path | Image.Image) -> list[PanelLayout]:
    """
    各コマが生成画像のどこに描かれたかを、画像全体に対するパーセントで返す。
    検出できなかったコマはガイドで指定した位置を使う。
    """
    if not isinstance(image, Image.Image):
        image = Image.open(image)
    w, h = image.size
    detected = detect_panel_boxes(image)

    results: list[PanelLayout] = []
    used: set[int] = set()
    for panel in page.panels:
        expected = panel_box(panel.layout, w, h)
        best, best_iou = None, MIN_MATCH_IOU
        for i, box in enumerate(detected):
            score = _iou(expected, box)
            if i not in used and score > best_iou:
                best, best_iou = i, score
        if best is None:
            results.append(_to_percent(expected, w, h))
        else:
            used.add(best)
            results.append(_to_percent(detected[best], w, h))
    return results
