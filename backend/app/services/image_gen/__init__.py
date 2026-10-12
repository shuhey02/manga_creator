from ...config import settings
from .base import ImageGenerationError, ImageGenerator
from .codex_cli import CodexImageGenerator


def create_image_generator() -> ImageGenerator:
    if settings.image_provider == "codex":
        return CodexImageGenerator(settings.codex_bin, settings.image_timeout_sec)
    raise ImageGenerationError(f"未対応の IMAGE_PROVIDER です: {settings.image_provider}")


__all__ = ["ImageGenerationError", "ImageGenerator", "create_image_generator"]
