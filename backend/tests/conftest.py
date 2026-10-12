import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.config import settings  # noqa: E402
from app.models.schemas import Storyboard  # noqa: E402


@pytest.fixture
def storyboard() -> Storyboard:
    data = json.loads((BACKEND.parent / "sample" / "storyboard_output.json").read_text(encoding="utf-8"))
    return Storyboard(**data)


@pytest.fixture
def output_dir(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(settings, "output_dir", str(tmp_path))
    return tmp_path
