"""
Image Assembler: Pillow を使って漫画ページを合成する
"""
import math
import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from ..models.schemas import MangaPage, Panel, SpeechBubble
from .vertical_text import AWKWARD_SHRINK, draw_vertical, fit_vertical

# ─── ページサイズ設定 (A4 @ 150dpi) ─────────────────────────────────────────
PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
MARGIN = 28       # ページ外枠マージン
GUTTER = 5        # コマ間の隙間
BORDER_W = 3      # コマ枠線の太さ

# ─── 日本語フォントの候補 ─────────────────────────────────────────────────────
# セリフは Noto Sans JP（可変フォント。太さを wght 軸で指定する）。無ければ従来の書体
NOTO_SANS_JP_PATHS = [
    "C:/Windows/Fonts/NotoSansJP-VF.ttf",
    os.path.expandvars("%LOCALAPPDATA%/Microsoft/Windows/Fonts/NotoSansJP-VF.ttf"),
]
JP_FONT_PATHS = [
    "C:/Windows/Fonts/msgothic.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/yugothb.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
]
JP_BOLD_FONT_PATHS = [
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
]
# 可変フォントの既定の太さは最も細い 100 なので、必ず指定する
REGULAR_WEIGHT = 500
BOLD_WEIGHT = 800
# 吹き出しの文字がこれより小さくなるなら、吹き出しをコマ内で広げる
MIN_READABLE_SIZE = 22
BUBBLE_GROWTH = (1.0, 1.15, 1.3, 1.45, 1.6)

_font_cache: dict[tuple[int, bool], ImageFont.ImageFont] = {}


def _load_font(path: str, size: int, bold: bool) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(path, size)
    try:
        font.get_variation_axes()
    except OSError:
        return font  # 可変フォントではない
    font.set_variation_by_axes([BOLD_WEIGHT if bold else REGULAR_WEIGHT])
    return font


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    fallbacks = JP_BOLD_FONT_PATHS + JP_FONT_PATHS if bold else JP_FONT_PATHS
    for path in NOTO_SANS_JP_PATHS + fallbacks:
        if os.path.exists(path):
            try:
                font = _load_font(path, size, bold)
                _font_cache[key] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def _bold_font(size: int) -> ImageFont.ImageFont:
    return _get_font(size, bold=True)


def _is_emphatic(bubble: SpeechBubble) -> bool:
    """叫び・感情が高ぶったセリフか（太字にする）"""
    return bubble.type == "shout" or any(c in bubble.text for c in "！!")


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """テキストを max_width px 以内に折り返す。改行（\n）の位置では必ず改行する"""
    if "\n" in text:
        return [line for part in text.split("\n") for line in _wrap_text(part, font, max_width)]
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


def _is_vertical(bubble: SpeechBubble, bw: int, bh: int) -> bool:
    if bubble.orientation == "auto":
        return bh > bw
    return bubble.orientation == "vertical"


def _bubble_rect(bubble: SpeechBubble, px: int, py: int, pw: int, ph: int) -> tuple[int, int, int, int]:
    """吹き出しの (x, y, 幅, 高さ)。位置はコマ内のパーセント"""
    pos = bubble.position
    return (px + int(pos.x / 100 * pw), py + int(pos.y / 100 * ph),
            int(pos.width / 100 * pw), int(pos.height / 100 * ph))


def _grow_rect(rect: tuple[int, int, int, int], scale: float,
               px: int, py: int, pw: int, ph: int) -> tuple[int, int, int, int]:
    """吹き出しを中心から scale 倍に広げ、コマからはみ出さないようずらす"""
    bx, by, bw, bh = rect
    nw, nh = min(pw, round(bw * scale)), min(ph, round(bh * scale))
    nx = min(max(px, bx + (bw - nw) // 2), px + pw - nw)
    ny = min(max(py, by + (bh - nh) // 2), py + ph - nh)
    return nx, ny, nw, nh


def _text_inset(btype: str) -> float:
    # 楕円の吹き出しは角が使えないので内側を狭める
    return 0.7 if btype in ("shout", "thought") else 0.85


Rect = tuple[int, int, int, int]
PAD = 7


def _rects_overlap(a: Rect, b: Rect) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _fit_bubble_text(bubble: SpeechBubble, rect: Rect, pad: int,
                     get_font, px: int, py: int, pw: int, ph: int,
                     max_size: int = 34, shrink: float = AWKWARD_SHRINK,
                     obstacles: tuple[Rect, ...] = ()):
    """
    縦書きの文字が小さくなりすぎる、語の途中で折れる、枠に収まらない、のどれかなら、収まるまで吹き出しを広げる。
    obstacles（同じコマのほかの吹き出し）と重なる広げ方は使わない。
    広げきっても足りなければ、重ならない範囲で一番広げた大きさで描く。(吹き出しの位置と大きさ, 列分け) を返す。
    """
    inset = _text_inset(bubble.type)
    readable = min(MIN_READABLE_SIZE, max_size)
    result = None
    for scale in BUBBLE_GROWTH:
        grown = _grow_rect(rect, scale, px, py, pw, ph)
        if scale > 1 and any(_rects_overlap(grown, o) for o in obstacles):
            break
        layout = fit_vertical(bubble.text, int(grown[2] * inset) - pad * 2,
                              int(grown[3] * inset) - pad * 2, get_font,
                              max_size=max_size, shrink=shrink)
        result = (grown, layout)
        if layout.font_size >= readable and not layout.awkward and not layout.overflow:
            break
    return result


def _font_getter(bubble: SpeechBubble):
    return _bold_font if _is_emphatic(bubble) else _get_font


def _fit_page_bubbles(panels: list[tuple[Panel, Rect]]) -> dict[int, tuple[Rect, object]]:
    """
    ページ内の縦書き吹き出しの位置・大きさと列分けを決める。文字サイズはページ全体でそろえる：
    まず吹き出しごとに収まる最大サイズを求め、その最小値（読める大きさが下限）を全吹き出しに使う。
    返り値は id(bubble) をキーにした (吹き出しの位置と大きさ, 列分け)。
    """
    entries = []
    for panel, (px, py, pw, ph) in panels:
        rects = [_bubble_rect(b, px, py, pw, ph) for b in panel.speech_bubbles]
        for i, bubble in enumerate(panel.speech_bubbles):
            bx, by, bw, bh = rects[i]
            if bw < 12 or bh < 10 or not _is_vertical(bubble, bw, bh):
                continue
            others = tuple(r for j, r in enumerate(rects) if j != i)
            entries.append((bubble, rects[i], (px, py, pw, ph), others))
    if not entries:
        return {}
    # font_scale で大きくする吹き出しは、倍率で割った大きさで比べる
    natural = [_fit_bubble_text(b, r, PAD, _font_getter(b), *pr, max_size=round(34 * b.font_scale),
                                obstacles=o)[1].font_size / b.font_scale
               for b, r, pr, o in entries]
    page_size = max(MIN_READABLE_SIZE, round(min(natural)))
    return {
        id(b): _fit_bubble_text(b, r, PAD, _font_getter(b), *pr,
                                max_size=round(page_size * b.font_scale), shrink=1.0, obstacles=o)
        for b, r, pr, o in entries
    }


TAIL_MAX = 70        # しっぽの長さの上限（px）
TAIL_HALF_WIDTH = 10  # 吹き出しの縁でのしっぽの半幅（px）


def _tail_target(bubble: SpeechBubble, rect: Rect, px: int, py: int, pw: int, ph: int):
    """しっぽを向ける先（ページ上の px）。指定が無ければ従来どおり吹き出しの左寄り下方"""
    if bubble.tail is not None:
        return (px + bubble.tail.x / 100 * pw, py + bubble.tail.y / 100 * ph)
    bx, by, bw, bh = rect
    return (bx + bw / 3, by + bh + 60)


def _tail_geometry(rect: Rect, target: tuple[float, float], oval: bool):
    """
    吹き出しの中心から target へ向かうしっぽの形。target が吹き出しの中にあれば None。
    outer は縁取り込みの三角形（吹き出しの中心が底辺）、inner はつなぎ目の縁を消すための一回り小さい三角形、
    dots は心の声の泡を置く3点。
    """
    bx, by, bw, bh = rect
    cx, cy = bx + bw / 2, by + bh / 2
    dx, dy = target[0] - cx, target[1] - cy
    dist = math.hypot(dx, dy)
    if dist == 0:
        return None
    ux, uy = dx / dist, dy / dist
    rx, ry = bw / 2, bh / 2
    if oval:
        edge = 1 / math.sqrt((ux / rx) ** 2 + (uy / ry) ** 2)
    else:
        edge = min(rx / abs(ux) if ux else math.inf, ry / abs(uy) if uy else math.inf)
    if dist <= edge:
        return None
    length = min(TAIL_MAX, max(18.0, (dist - edge) * 0.6))
    total = edge + length
    # 縁での幅が TAIL_HALF_WIDTH になるよう、中心側の底辺を広げる
    base = TAIL_HALF_WIDTH * total / length
    nx, ny = -uy, ux
    tip = (cx + ux * total, cy + uy * total)

    def triangle(half: float, back: float):
        return [(cx + nx * half, cy + ny * half), (cx - nx * half, cy - ny * half),
                (tip[0] - ux * back, tip[1] - uy * back)]

    dots = [(cx + ux * (edge + d), cy + uy * (edge + d)) for d in (12, 28, 40)]
    return {"outer": triangle(base, 0), "inner": triangle(base - 3 * total / length, 4), "dots": dots}


def _draw_bubble(draw: ImageDraw.ImageDraw, bubble: SpeechBubble,
                 px: int, py: int, pw: int, ph: int, fitted: tuple | None = None) -> None:
    """吹き出しを描画する。fitted はページ単位で決めた (位置と大きさ, 列分け)"""
    bx, by, bw, bh = _bubble_rect(bubble, px, py, pw, ph)

    if bw < 12 or bh < 10:
        return

    text = bubble.text
    btype = bubble.type
    get_font = _font_getter(bubble)

    pad = PAD
    vertical = _is_vertical(bubble, bw, bh)
    if vertical:
        (bx, by, bw, bh), layout = fitted or _fit_bubble_text(
            bubble, (bx, by, bw, bh), pad, get_font, px, py, pw, ph)

    target = _tail_target(bubble, (bx, by, bw, bh), px, py, pw, ph)
    oval = btype in ("shout", "thought")
    tail = None if btype == "narration" or target is None else _tail_geometry((bx, by, bw, bh), target, oval)
    outline_w = 3 if btype == "shout" else 2
    if tail and btype != "thought":
        # しっぽを先に縁取りで描き、吹き出しを重ねてから、つなぎ目の縁を白で消す
        draw.polygon(tail["outer"], fill="white", outline="black", width=outline_w)

    if btype == "shout":
        # ギザギザ（星形の近似 - 楕円 + 外側の三角）
        draw.ellipse([bx, by, bx + bw, by + bh], fill="white", outline="black", width=3)
        draw.ellipse([bx + 4, by + 4, bx + bw - 4, by + bh - 4],
                     fill="white", outline="black", width=2)

    elif btype == "thought":
        # 思ったこと・気づいたこと：丸い吹き出し + 考えている人物へ向かう小さい泡
        draw.ellipse([bx, by, bx + bw, by + bh], fill="white", outline="black", width=2)
        for (dx, dy), dot_r in zip(tail["dots"] if tail else [], [7, 5, 3]):
            draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r],
                         fill="white", outline="black", width=1)

    elif btype == "narration":
        # ナレーション（場所・時刻など）は四角い枠だけ
        draw.rectangle([bx, by, bx + bw, by + bh], fill="white", outline="black", width=2)

    else:
        # 通常の吹き出し（角丸四角形）
        try:
            draw.rounded_rectangle([bx, by, bx + bw, by + bh],
                                    radius=14, fill="white", outline="black", width=2)
        except AttributeError:
            draw.rectangle([bx, by, bx + bw, by + bh], fill="white", outline="black", width=2)

    if tail and btype != "thought":
        draw.polygon(tail["inner"], fill="white")

    # テキスト描画：吹き出しに収まる最大の文字サイズを選ぶ
    inset = _text_inset(btype)
    text_x = bx + bw // 2
    text_y = by + bh // 2
    if vertical:
        draw_vertical(draw, layout, get_font(layout.font_size), (text_x, text_y), resize=get_font)
        return
    for font_size in range(34, 13, -2):
        font = get_font(font_size)
        lines = _wrap_text(text, font, int(bw * inset) - pad * 2)
        try:
            lh = font.getbbox("あ")[3] + 3
        except AttributeError:
            lh = font_size + 4
        if len(lines) * lh <= bh * inset - pad * 2:
            break
    total_h = len(lines) * lh
    start_y = text_y - total_h // 2

    for i, line in enumerate(lines):
        draw.text((text_x, start_y + i * lh), line,
                  fill="black", font=font, anchor="mt")


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """(x0, y0, x1, y1) 同士が重なるか"""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _draw_sfx(draw: ImageDraw.ImageDraw, panel: Panel,
              px: int, py: int, pw: int, ph: int) -> None:
    """効果音を描画する（白抜き文字＋黒の縁取り）"""
    text = panel.sound_effect
    if panel.sound_effect_orientation == "vertical":
        _draw_vertical_sfx(draw, panel, px, py, pw, ph)
        return
    font = _get_font(36)
    tx = px + pw - 6
    ty = py + 6
    # 太字風（オフセット重ね描き）
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            draw.text((tx + dx, ty + dy), text, fill="black", font=font, anchor="ra")
    draw.text((tx, ty), text, fill="white", font=font, anchor="ra")


def _draw_vertical_sfx(draw: ImageDraw.ImageDraw, panel: Panel,
                       px: int, py: int, pw: int, ph: int) -> None:
    """
    効果音を縦書きでコマの右端に沿って上から置く。吹き出しと重なるなら左端に置く
    （ネーム生成は先に読む吹き出しを右上に置くため、右端がふさがっていることが多い）。
    """
    box = (int(pw * 0.3), int(ph * 0.7))
    # 効果音は1列で一気に読ませる。1列に収まらないほど長いときだけ折り返す
    layout = fit_vertical(panel.sound_effect, *box, _get_font, max_size=80, min_size=20, max_columns=1)
    if len(layout.columns) > 1:
        layout = fit_vertical(panel.sound_effect, *box, _get_font, max_size=80, min_size=20)
    margin = max(8, int(min(pw, ph) * 0.04))
    w, h = layout.width, layout.height
    right_side = (px + pw - margin - w, py + margin, px + pw - margin, py + margin + h)
    left_side = (px + margin, py + margin, px + margin + w, py + margin + h)
    bubbles = [(x, y, x + bw, y + bh) for x, y, bw, bh in
               (_bubble_rect(b, px, py, pw, ph) for b in panel.speech_bubbles)]
    blocked = any(_overlaps(right_side, b) for b in bubbles)
    x0, y0, x1, y1 = left_side if blocked else right_side

    size = layout.font_size
    draw_vertical(draw, layout, _get_font(size), (round((x0 + x1) / 2), round((y0 + y1) / 2)),
                  fill="white", stroke_width=max(2, size // 10), stroke_fill="black", resize=_get_font)


def _assemble_on_generated(generated: Image.Image, page_data: MangaPage) -> Image.Image:
    """AI 生成ページを縦横比を保って A4 に収め、検出済みのコマ枠に吹き出しを重ねる"""
    gw, gh = generated.size
    scale = min(PAGE_WIDTH / gw, PAGE_HEIGHT / gh)
    sw, sh = round(gw * scale), round(gh * scale)
    ox, oy = (PAGE_WIDTH - sw) // 2, (PAGE_HEIGHT - sh) // 2

    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color="white")
    page.paste(generated.convert("RGB").resize((sw, sh), Image.LANCZOS), (ox, oy))
    draw = ImageDraw.Draw(page)

    panels = []
    for panel in page_data.panels:
        lo = panel.rendered_layout or panel.layout
        panels.append((panel, (ox + int(lo.x / 100 * sw), oy + int(lo.y / 100 * sh),
                               int(lo.width / 100 * sw), int(lo.height / 100 * sh))))
    fitted = _fit_page_bubbles(panels)
    for panel, (px, py, pw, ph) in panels:
        if panel.sound_effect:
            _draw_sfx(draw, panel, px, py, pw, ph)
        for bubble in panel.speech_bubbles:
            _draw_bubble(draw, bubble, px, py, pw, ph, fitted.get(id(bubble)))
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
            _draw_sfx(draw, panel, px, py, pw, ph)

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
