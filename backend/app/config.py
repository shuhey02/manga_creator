from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    host: str = "127.0.0.1"
    port: int = 8000
    output_dir: str = "output"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 画像生成: "codex" は Codex CLI の $imagegen（ChatGPT サブスク枠）を使う
    image_provider: str = "codex"
    codex_bin: str = "codex"
    image_timeout_sec: int = 600

    @property
    def output_path(self) -> Path:
        path = Path(self.output_dir)
        # MCP サーバーなど backend/ 以外から起動しても同じ出力先を使う
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
