"""
Export Service: PDF / Kindle用ZIP(CBZ) を生成する
"""
import zipfile
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

from ..models.schemas import Storyboard


def create_pdf(session_dir: Path, storyboard: Storyboard) -> Path:
    """
    合成済みページ画像からPDFを生成する。

    Args:
        session_dir: セッションディレクトリ
        storyboard: ネームデータ（タイトル等のメタ情報用）

    Returns:
        生成したPDFのパス
    """
    pages_dir = session_dir / "pages"
    page_files = sorted(pages_dir.glob("page_*.png"))

    if not page_files:
        raise FileNotFoundError("合成済みページが見つかりません。先にページを合成してください。")

    out_path = session_dir / "export.pdf"
    c = rl_canvas.Canvas(str(out_path), pagesize=A4)
    a4_w, a4_h = A4  # points (595 × 841)

    for img_path in page_files:
        c.drawImage(
            str(img_path),
            0, 0,
            width=a4_w, height=a4_h,
            preserveAspectRatio=True,
            anchor="c",
        )
        c.showPage()

    c.save()
    return out_path


def create_kindle_zip(session_dir: Path, storyboard: Storyboard) -> Path:
    """
    合成済みページ画像からKindle/CBZ用ZIPを生成する。
    CBZ形式（Comic Book Archive）: ZIP内に 001.png, 002.png ... と格納。

    Args:
        session_dir: セッションディレクトリ
        storyboard: ネームデータ

    Returns:
        生成したZIPのパス
    """
    pages_dir = session_dir / "pages"
    page_files = sorted(pages_dir.glob("page_*.png"))

    if not page_files:
        raise FileNotFoundError("合成済みページが見つかりません。先にページを合成してください。")

    out_path = session_dir / "manga_kindle.cbz"

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # ComicRack互換のメタデータ
        title = storyboard.title
        num_pages = len(page_files)
        comic_xml = f"""<?xml version="1.0"?>
<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Title>{title}</Title>
  <PageCount>{num_pages}</PageCount>
  <Manga>YesAndRightToLeft</Manga>
</ComicInfo>"""
        zf.writestr("ComicInfo.xml", comic_xml)

        for i, img_path in enumerate(page_files, start=1):
            zf.write(img_path, f"{i:03d}.png")

    return out_path
