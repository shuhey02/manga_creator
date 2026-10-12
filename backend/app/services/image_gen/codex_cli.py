"""
Codex CLI の $imagegen（gpt-image-2）で画像を生成する。

ChatGPT サブスクの枠で動くため API キーは不要。1枚に数分かかり、
枠を食い合わないよう同時実行は1つに絞る。
"""
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

from .base import ImageGenerationError

# Codex エージェントに「生成だけ」させる。保存・再生成をさせると時間と枠を浪費する
_INSTRUCTION = (
    "$imagegen Use the built-in image generation tool exactly once to create the image "
    "described below. Do not regenerate, edit, inspect, save, or copy files; "
    "just generate it and reply 'done'.\n\n"
)

_lock = asyncio.Lock()


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def _thread_id_from_events(stdout: str) -> str | None:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            return event.get("thread_id")
    return None


def _newest_png(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    pngs = sorted(directory.glob("*.png"), key=lambda p: p.stat().st_mtime)
    return pngs[-1] if pngs else None


def _build_command(codex_bin: str, refs: list[Path], workdir: Path) -> list[str]:
    exe = shutil.which(codex_bin) or codex_bin
    cmd = [exe, "exec", "--json", "-s", "read-only", "--skip-git-repo-check", "-C", str(workdir)]
    for ref in refs:
        cmd += ["--image", str(ref.resolve())]
    # プロンプトは stdin で渡す。Windows の .cmd 経由だと引数のクオートが壊れやすいため
    cmd.append("-")
    return cmd


class CodexImageGenerator:
    def __init__(self, codex_bin: str = "codex", timeout_sec: int = 600) -> None:
        self.codex_bin = codex_bin
        self.timeout_sec = timeout_sec

    async def generate(self, prompt: str, refs: list[Path], out_path: Path) -> Path:
        async with _lock:
            return await asyncio.to_thread(self._generate_sync, prompt, refs, out_path)

    def _generate_sync(self, prompt: str, refs: list[Path], out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = _build_command(self.codex_bin, refs, out_path.parent)
        # uvicorn の Windows イベントループは asyncio のサブプロセスを扱えないので、
        # 同期 subprocess をスレッドで回す
        try:
            proc = subprocess.run(
                cmd,
                input=_INSTRUCTION + prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_sec,
            )
        except FileNotFoundError as e:
            raise ImageGenerationError(f"Codex CLI が見つかりません: {self.codex_bin}") from e
        except subprocess.TimeoutExpired as e:
            raise ImageGenerationError(f"画像生成が {self.timeout_sec} 秒で終わりませんでした") from e

        thread_id = _thread_id_from_events(proc.stdout)
        if proc.returncode != 0 or thread_id is None:
            tail = (proc.stderr or proc.stdout)[-800:]
            raise ImageGenerationError(f"Codex の実行に失敗しました (exit={proc.returncode}): {tail}")

        generated = _newest_png(_codex_home() / "generated_images" / thread_id)
        if generated is None:
            raise ImageGenerationError(
                "Codex は終了しましたが画像が見つかりません。ChatGPT の利用枠や "
                "`codex login` の状態を確認してください。"
            )
        shutil.copyfile(generated, out_path)
        return out_path
