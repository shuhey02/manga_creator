import asyncio
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.services import generation_service
from app.services.image_assembler import PAGE_HEIGHT, PAGE_WIDTH, assemble_page
from app.services.image_gen import ImageGenerationError
from app.services.image_gen import codex_cli
from app.services.page_prompt import build_character_sheet_prompt, build_page_prompt
from app.services.session_store import create_session, load_storyboard, session_dir


class FakeGenerator:
    """ガイド画像（refs[0]）をそのまま灰色で塗って返す、生成 AI の代わり"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Path]]] = []

    async def generate(self, prompt: str, refs: list[Path], out_path: Path) -> Path:
        self.calls.append((prompt, refs))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if refs:
            img = Image.open(refs[0]).convert("RGB")
            img = img.point(lambda v: 150 if v > 200 else v)
            # 外周の余白は白に戻す（実物の生成ページと同じく）
            ImageDraw.Draw(img).rectangle([0, 0, img.width - 1, img.height - 1], outline="white", width=30)
        else:
            img = Image.new("RGB", (1024, 1536), "white")
        img.save(out_path)
        return out_path


def test_page_prompt_forbids_text_and_names_reference_characters(storyboard):
    prompt = build_page_prompt(storyboard, storyboard.pages[0], [c.name for c in storyboard.characters])
    assert "no speech bubbles" in prompt
    assert "never sexualized" in prompt
    assert "Input image 2" in prompt
    assert all(f"Panel {p.panel_number} (" in prompt for p in storyboard.pages[0].panels)


def test_page_prompt_without_references_does_not_mention_image_2(storyboard):
    assert "Input image 2" not in build_page_prompt(storyboard, storyboard.pages[0], [])


def test_character_sheet_prompt_lists_every_character(storyboard):
    prompt = build_character_sheet_prompt(storyboard)
    assert all(c.name in prompt for c in storyboard.characters)


def test_generated_page_is_recorded_and_assembled(storyboard, output_dir):
    session_id = create_session(storyboard)
    fake = FakeGenerator()

    asyncio.run(generation_service.generate_character_sheet(session_id, fake))
    out = asyncio.run(generation_service.generate_page(session_id, 1, generator=fake))

    saved = load_storyboard(session_id)
    page = saved.pages[0]
    assert page.generated_image == "generated/page_001.png"
    assert all(p.rendered_layout is not None for p in page.panels)
    assert saved.characters[0].reference_image == "characters/characters.png"
    # 2回目（ページ）の呼び出しにはガイドとキャラ参照シートが渡る
    assert [r.name for r in fake.calls[1][1]] == ["guide_001.png", "characters.png"]
    assert out.with_suffix(".prompt.txt").exists()

    assembled = assemble_page(session_dir(session_id), page)
    assert Image.open(assembled).size == (PAGE_WIDTH, PAGE_HEIGHT)


def _fake_run(home: Path, thread_id: str | None, write_png: bool):
    def run(cmd, **kwargs):
        if write_png:
            target = home / "generated_images" / thread_id
            target.mkdir(parents=True)
            Image.new("RGB", (8, 8), "black").save(target / "ig_1.png")
        events = [{"type": "thread.started", "thread_id": thread_id}] if thread_id else []
        stdout = "\n".join(json.dumps(e) for e in events)
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
    return run


def test_codex_generator_copies_image_from_thread_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setattr(codex_cli.subprocess, "run", _fake_run(tmp_path / "codex", "t-1", True))

    ref = tmp_path / "guide.png"
    Image.new("RGB", (8, 8)).save(ref)
    out = asyncio.run(codex_cli.CodexImageGenerator().generate("draw", [ref], tmp_path / "out" / "p.png"))
    assert out.exists()


def test_codex_command_passes_refs_and_reads_prompt_from_stdin(tmp_path):
    ref = tmp_path / "guide.png"
    cmd = codex_cli._build_command("codex", [ref], tmp_path)
    assert cmd[cmd.index("--image") + 1] == str(ref.resolve())
    assert cmd[-1] == "-"


def test_codex_generator_reports_missing_image(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setattr(codex_cli.subprocess, "run", _fake_run(tmp_path / "codex", "t-2", False))
    with pytest.raises(ImageGenerationError, match="画像が見つかりません"):
        asyncio.run(codex_cli.CodexImageGenerator().generate("draw", [], tmp_path / "p.png"))
