"""
Image Assembler: Pillow を使って漫画ページを合成する
"""
import math
import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from ..models.schemas import MangaPage, Panel, SpeechBubble

# ─── ページサイズ設定 (A4 @ 150dpi) ─────────────────────────────────────────
PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
MARGIN = 28       # ページ外枠マージン
GUTTER = 5        # コマ間の隙間
BORDER_W = 3      # コマ枠線の太さ

# ─── 日本語フォントの候補 ─────────────────────────────────────────────────────
JP_FONT_PATHS = [
    "C:/Windows/Fonts/msgothic.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/yugothb.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
]

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _get_font(size: int) -> ImageFont.ImageFont:
    if size in _font_cache:
        return _font_cache[size]
    for path in JP_FONT_PATHS:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[size] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """テキストを max_width px 以内に折り返す"""
    lines: list[str] = []
    current = ""
    for ch in text:
        test = current + ch
        try:
            w = font.getlength(test)
        except AttributeError:
            w = len(test) * 14  # fallback
        if w > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines or [""]


def _resize_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """アスペクト比を保ちながらパネルサイズにフィット（クロップ）"""
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _draw_bubble(draw: ImageDraw.ImageDraw, bubble: SpeechBubble,
                 px: int, py: int, pw: int, ph: int) -> None:
    """吹き出しを描画する"""
    pos = bubble.position
    bx = px + int(pos.x / 100 * pw)
    by = py + int(pos.y / 100 * ph)
    bw = int(pos.width / 100 * pw)
    bh = int(pos.height / 100 * ph)

    if bw < 12 or bh < 10:
        return

    text = bubble.text
    btype = bubble.type

    pad = 7

    if btype == "shout":
        # ギザギザ（星形の近似 - 楕円 + 外側の三角）
        draw.ellipse([bx, by, bx + bw, by + bh], fill="white", outline="black", width=3)
        cx, cy = bx + bw // 2, by + bh // 2
        rx, ry = bw // 2, bh // 2
        spike = 12
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            x1 = cx + int(rx * math.cos(rad))
            y1 = cy + int(ry * math.sin(rad))
            mid_rad = math.radians(deg + 22)
            x2 = cx + int((rx + spike) * math.cos(mid_rad))
            y2 = cy + int((ry + spike) * math.sin(mid_rad))
            draw.line([(cx, cy), (x2, y2)], fill="white", width=2)
        draw.ellipse([bx + 4, by + 4, bx + bw - 4, by + bh - 4],
                     fill="white", outline="black", width=2)

    elif btype == "thought":
        # 雲型（楕円 + 小さい泡）
        try:
            draw.rounded_rectangle([bx, by, bx + bw, by + bh],
                                    radius=bh // 2, fill="white", outline="black", width=2)
        except AttributeError:
            draw.ellipse([bx, by, bx + bw, by + bh], fill="white", outline="black", width=2)
        # 思考の泡
        for i, dot_r in enumerate([7, 5, 3]):
            dx = bx + bw // 4 + i * 6
            dy = by + bh + 2 + i * 6
            draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r],
                         fill="white", outline="black", width=1)

    else:
        # 通常の吹き出し（角丸四角形 + しっぽ）
        try:
            draw.rounded_rectangle([bx, by, bx + bw, by + bh],
                                    radius=14, fill="white", outline="black", width=2)
        except AttributeError:
            draw.rectangle([bx, by, bx + bw, by + bh], fill="white", outline="black", width=2)

        # しっぽ（三角形）
        tail_cx = bx + bw // 3
        tail_top = by + bh - 1
        tail_tip = (tail_cx, by + bh + 18)
        pts = [(tail_cx - 8, tail_top), (tail_cx + 8, tail_top), tail_tip]
        draw.polygon(pts, fill="white")
        draw.line([(tail_cx - 8, tail_top), tail_tip], fill="black", width=2)
        draw.line([(tail_cx + 8, tail_top), tail_tip], fill="black", width=2)
        # しっぽ接合部の線を消す
        draw.line([(tail_cx - 8, tail_top), (tail_cx + 8, tail_top)], fill="white", width=3)

    # テキスト描画
    font_size = max(14, min(22, bh // 2))
    font = _get_font(font_size)
    text_x = bx + bw // 2
    text_y = by + bh // 2

    lines = _wrap_text(text, font, bw - pad * 2)
    try:
        lh = font.getbbox("あ")[3] + 3
    except AttributeError:
        lh = font_size + 4
    total_h = len(lines) * lh
    start_y = text_y - total_h // 2

    for i, line in enumerate(lines):
        draw.text((text_x, start_y + i * lh), line,
                  fill="black", font=font, anchor="mt")


def _draw_sfx(draw: ImageDraw.ImageDraw, text: str,
              px: int, py: int, pw: int, ph: int) -> None:
    """効果音を描画する"""
    font = _get_font(36)
    tx = px + pw - 6
    ty = py + 6
    # 太字風（オフセット重ね描き）
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            draw.text((tx + dx, ty + dy), text, fill="black", font=font, anchor="ra")
    draw.text((tx, ty), text, fill="white", font=font, anchor="ra")


def _assemble_on_generated(generated: Image.Image, page_data: MangaPage) -> Image.Image:
    """AI 生成ページを縦横比を保って A4 に収め、検出済みのコマ枠に吹き出しを重ねる"""
    gw, gh = generated.size
    scale = min(PAGE_WIDTH / gw, PAGE_HEIGHT / gh)
    sw, sh = round(gw * scale), round(gh * scale)
    ox, oy = (PAGE_WIDTH - sw) // 2, (PAGE_HEIGHT - sh) // 2

    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color="white")
    page.paste(generated.convert("RGB").resize((sw, sh), Image.LANCZOS), (ox, oy))
    draw = ImageDraw.Draw(page)

    for panel in page_data.panels:
        lo = panel.rendered_layout or panel.layout
        px = ox + int(lo.x / 100 * sw)
        py = oy + int(lo.y / 100 * sh)
        pw = int(lo.width / 100 * sw)
        ph = int(lo.height / 100 * sh)
        if panel.sound_effect:
            _draw_sfx(draw, panel.sound_effect, px, py, pw, ph)
        for bubble in panel.speech_bubbles:
            _draw_bubble(draw, bubble, px, py, pw, ph)
    return page


def assemble_page(session_dir: Path, page_data: MangaPage) -> Path:
    """
    1ページ分の漫画ページを合成する。

    Args:
        session_dir: セッションディレクトリ（uploads/ サブディレクトリを含む）
        page_data: MangaPage モデル

    Returns:
        合成済みページPNGのパス
    """
    page_num = page_data.page_number
    generated_path = session_dir / page_data.generated_image if page_data.generated_image else None
    if generated_path and generated_path.exists():
        page = _assemble_on_generated(Image.open(generated_path), page_data)
        return _save_page(session_dir, page, page_num)

    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color="white")
    draw = ImageDraw.Draw(page)

    # ページ外枠
    draw.rectangle(
        [MARGIN, MARGIN, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN],
        outline="black", width=2,
    )

    content_w = PAGE_WIDTH - 2 * MARGIN
    content_h = PAGE_HEIGHT - 2 * MARGIN

    for panel in page_data.panels:
        lo = panel.layout
        px = MARGIN + int(lo.x / 100 * content_w) + GUTTER
        py = MARGIN + int(lo.y / 100 * content_h) + GUTTER
        pw = int(lo.width / 100 * content_w) - GUTTER * 2
        ph = int(lo.height / 100 * content_h) - GUTTER * 2

        if pw < 10 or ph < 10:
            continue

        # アップロード済み画像の読み込み（複数拡張子対応）
        img: Optional[Image.Image] = None
        for ext in ["jpg", "jpeg", "png", "webp"]:
            img_path = session_dir / "uploads" / f"p{page_num}_panel{panel.panel_number}.{ext}"
            if img_path.exists():
                img = Image.open(img_path).convert("RGB")
                break

        if img:
            img_fitted = _resize_cover(img, pw, ph)
            page.paste(img_fitted, (px, py))
        else:
            # プレースホルダー（薄いグレー背景 + 構図説明テキスト）
            placeholder = Image.new("RGB", (pw, ph), color=(238, 238, 238))
            page.paste(placeholder, (px, py))
            font_ph = _get_font(20)
            desc = panel.composition or f"コマ {panel.panel_number}"
            lines = _wrap_text(desc, font_ph, pw - 20)
            try:
                lh = font_ph.getbbox("あ")[3] + 4
            except AttributeError:
                lh = 24
            total_h = len(lines) * lh
            start_y = py + ph // 2 - total_h // 2
            for i, line in enumerate(lines):
                draw.text((px + pw // 2, start_y + i * lh),
                          line, fill=(150, 150, 150), font=font_ph, anchor="mt")

        # コマ枠線
        draw.rectangle(
            [px - BORDER_W, py - BORDER_W, px + pw + BORDER_W, py + ph + BORDER_W],
            outline="black", width=BORDER_W,
        )

        # 効果音
        if panel.sound_effect:
            _draw_sfx(draw, panel.sound_effect, px, py, pw, ph)

        # 吹き出し
        for bubble in panel.speech_bubbles:
            _draw_bubble(draw, bubble, px, py, pw, ph)

    # ページ番号（下部中央）
    pg_font = _get_font(22)
    draw.text(
        (PAGE_WIDTH // 2, PAGE_HEIGHT - MARGIN // 2),
        str(page_num),
        fill="black", font=pg_font, anchor="mm",
    )

    return _save_page(session_dir, page, page_num)


def _save_page(session_dir: Path, page: Image.Image, page_num: int) -> Path:
    out_dir = session_dir / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"page_{page_num:03d}.png"
    page.save(out_path, "PNG")
    return out_path
