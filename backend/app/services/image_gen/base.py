"""
画像生成プロバイダの共通インターフェース
"""
from pathlib import Path
from typing import Protocol


class ImageGenerationError(RuntimeError):
    # 画面の出し分けに使う: quota（利用枠切れ）/ auth（未ログイン）/ safety（安全フィルタ）/ other
    kind = "other"


class ImageQuotaError(ImageGenerationError):
    kind = "quota"


class ImageAuthError(ImageGenerationError):
    kind = "auth"


class ImageSafetyError(ImageGenerationError):
    kind = "safety"


class ImageGenerator(Protocol):
    async def generate(self, prompt: str, refs: list[Path], out_path: Path) -> Path:
        """prompt と参照画像 refs から1枚生成し、out_path に PNG で保存して返す"""
        ...
