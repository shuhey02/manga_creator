from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    host: str = "127.0.0.1"
    port: int = 8000
    output_dir: str = "output"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)


settings = Settings()
