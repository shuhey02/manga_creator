from ...config import settings
from .base import ImageAuthError, ImageGenerationError, ImageGenerator, ImageQuotaError, ImageSafetyError
from .codex_cli import CodexImageGenerator


def create_image_generator() -> ImageGenerator:
    if settings.image_provider == "codex":
        return CodexImageGenerator(settings.codex_bin, settings.image_timeout_sec)
    raise ImageGenerationError(f"未対応の IMAGE_PROVIDER です: {settings.image_provider}")


__all__ = [
    "ImageAuthError", "ImageGenerationError", "ImageGenerator", "ImageQuotaError",
    "ImageSafetyError",
    "create_image_generator",
]
