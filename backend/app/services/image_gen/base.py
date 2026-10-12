"""
画像生成プロバイダの共通インターフェース
"""
from pathlib import Path
from typing import Protocol


class ImageGenerationError(RuntimeError):
    pass


class ImageGenerator(Protocol):
    async def generate(self, prompt: str, refs: list[Path], out_path: Path) -> Path:
        """prompt と参照画像 refs から1枚生成し、out_path に PNG で保存して返す"""
        ...
