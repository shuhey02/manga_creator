"""
画像生成 AI に渡すコマ割りガイド画像を描く。

gpt-image-2 の縦長出力（2:3）に合わせた 1024x1536 の白地に、コマ枠と
吹き出し予定域（薄い灰色）を描く。生成画像はこの枠に沿って描かれる前提で、
実際の枠位置は panel_detect で後から測り直す。
"""
from pathlib import Path

from PIL import Image, ImageDraw

from ..models.schemas import MangaPage, PanelLayout

GUIDE_WIDTH = 1024
GUIDE_HEIGHT = 1536
GUIDE_MARGIN = 40
GUIDE_GUTTER = 16
GUIDE_BORDER = 6
RESERVED_FILL = (215, 215, 215)

Box = tuple[int, int, int, int]


def panel_box(layout: PanelLayout, width: int = GUIDE_WIDTH, height: int = GUIDE_HEIGHT) -> Box:
    """ページ内パーセント座標のコマを、ガイド画像上のピクセル枠に変換する"""
    inner_w = width - 2 * GUIDE_MARGIN
    inner_h = height - 2 * GUIDE_MARGIN
    half = GUIDE_GUTTER // 2
    x0 = GUIDE_MARGIN + round(inner_w * layout.x / 100) + half
    y0 = GUIDE_MARGIN + round(inner_h * layout.y / 100) + half
    x1 = GUIDE_MARGIN + round(inner_w * (layout.x + layout.width) / 100) - half
    y1 = GUIDE_MARGIN + round(inner_h * (layout.y + layout.height) / 100) - half
    return x0, y0, x1, y1


def render_guide(page: MangaPage, out_path: Path) -> Path:
    img = Image.new("RGB", (GUIDE_WIDTH, GUIDE_HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    for panel in page.panels:
        x0, y0, x1, y1 = panel_box(panel.layout)
        pw, ph = x1 - x0, y1 - y0
        for bubble in panel.speech_bubbles:
            pos = bubble.position
            bx = x0 + round(pw * pos.x / 100)
            by = y0 + round(ph * pos.y / 100)
            draw.rectangle(
                [bx, by, bx + round(pw * pos.width / 100), by + round(ph * pos.height / 100)],
                fill=RESERVED_FILL,
            )
        draw.rectangle([x0, y0, x1, y1], outline="black", width=GUIDE_BORDER)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path
