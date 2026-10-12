"""
Codex CLI の $imagegen（gpt-image-2）で画像を生成する。

ChatGPT サブスクの枠で動くため API キーは不要。1枚に数分かかり、
枠を食い合わないよう同時実行は1つに絞る。
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .base import ImageAuthError, ImageGenerationError, ImageQuotaError, ImageSafetyError

# Codex エージェントに「生成だけ」させる。保存・再生成をさせると時間と枠を浪費する
_INSTRUCTION = (
    "$imagegen Use the built-in image generation tool exactly once to create the image "
    "described below. Do not regenerate, edit, inspect, save, or copy files; "
    "just generate it and reply 'done'.\n\n"
)

_lock = asyncio.Lock()


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


@dataclass
class _RunEvents:
    thread_id: str | None = None
    errors: list[str] = field(default_factory=list)
    last_message: str = ""


def _parse_events(stdout: str) -> _RunEvents:
    """
    `codex exec --json` のイベント列から、スレッドID・エラー・最後の返答を拾う。
    エラーは {"type":"error"} と {"type":"turn.failed"} に来る（本文は API の JSON 文字列のことがある）。
    画像ツールが断られたときは turn が成功扱いで、理由が返答文にだけ書かれることがある。
    """
    events = _RunEvents()
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "thread.started":
            events.thread_id = event.get("thread_id")
        elif kind in ("error", "turn.failed"):
            message = str(event.get("message") or (event.get("error") or {}).get("message", ""))
            # 同じ失敗が error と turn.failed の両方で届くので、重複は1つにまとめる
            if message and message not in events.errors:
                events.errors.append(message)
        elif kind == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                events.last_message = str(item.get("text", ""))
    return events


_QUOTA_PATTERN = re.compile(
    r"usage limit|limit reached|hit your .{0,20}limit|rate.?limit|too many requests|quota|"
    r"\b429\b|\"status\":\s*429|resets? in|try again (?:at|in)",
    re.IGNORECASE,
)
_AUTH_PATTERN = re.compile(
    r"\b401\b|\"status\":\s*401|unauthori[sz]ed|not logged in|log ?in again|codex login|"
    r"authentication|token (?:has )?expired",
    re.IGNORECASE,
)
_SAFETY_PATTERN = re.compile(
    r"safety system|content policy|moderation|blocked by|violat\w* (?:our|the) polic", re.IGNORECASE
)
_RETRY_PATTERN = re.compile(r"(?:try again|resets?)\s+(?:at|in)\s+([^.\"\n]+)", re.IGNORECASE)


def classify_failure(text: str) -> ImageGenerationError:
    """Codex の失敗理由の文面から、画面に出す日本語のエラーを作る"""
    detail = text.strip()[-400:]
    if _QUOTA_PATTERN.search(text):
        retry = _RETRY_PATTERN.search(text)
        when = f"（再開の目安: {retry.group(1).strip()}）" if retry else ""
        return ImageQuotaError(
            f"ChatGPT の画像生成の利用枠の上限に達しました{when}。時間をおいて再試行するか、"
            f"Codex の Usage 画面で残量を確認してください。詳細: {detail}"
        )
    if _SAFETY_PATTERN.search(text):
        return ImageSafetyError(
            "ChatGPT の安全フィルタで画像生成が止められました。指示や構図（露出・暴力・実在の人物など）"
            f"を変えて再試行してください。詳細: {detail}"
        )
    if _AUTH_PATTERN.search(text):
        return ImageAuthError(
            "Codex に ChatGPT アカウントでログインしていないか、ログインが切れています。"
            f"ターミナルで `codex login` を実行してください。詳細: {detail}"
        )
    return ImageGenerationError(f"Codex での画像生成に失敗しました。詳細: {detail}")


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

        events = _parse_events(proc.stdout)
        if proc.returncode != 0 or events.thread_id is None:
            reason = "\n".join(events.errors) or proc.stderr or proc.stdout
            raise classify_failure(reason)

        generated = _newest_png(_codex_home() / "generated_images" / events.thread_id)
        if generated is None:
            # 画像ツールが断られても turn は成功で終わり、理由は返答文に書かれる
            reason = "\n".join(events.errors + [events.last_message]) or "画像が生成されませんでした"
            raise classify_failure(reason)
        shutil.copyfile(generated, out_path)
        return out_path
