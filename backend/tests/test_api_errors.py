import asyncio
import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.image_gen import ImageAuthError, ImageQuotaError, codex_cli
from app.services.image_gen.codex_cli import classify_failure
from app.services.session_store import create_session

client = TestClient(app)


def _codex_run(stdout_events: list[dict], returncode: int = 0):
    def run(cmd, **kwargs):
        stdout = "\n".join(json.dumps(e) for e in stdout_events)
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    return run


def test_usage_limit_is_reported_as_quota_with_retry_time():
    error = classify_failure("You've hit your usage limit. Try again at 3:15 PM.")
    assert isinstance(error, ImageQuotaError)
    assert "3:15 PM" in str(error)


def test_http_429_is_reported_as_quota():
    assert isinstance(classify_failure('{"type":"error","status":429,"error":{}}'), ImageQuotaError)


def test_expired_login_is_reported_as_auth():
    assert isinstance(classify_failure('{"status":401,"error":{"message":"Unauthorized"}}'), ImageAuthError)


def test_turn_failed_event_reaches_the_user(tmp_path, monkeypatch):
    events = [
        {"type": "thread.started", "thread_id": "t-q"},
        {"type": "turn.failed", "error": {"message": "You've hit your usage limit. Try again in 2 hours."}},
    ]
    monkeypatch.setattr(codex_cli.subprocess, "run", _codex_run(events, returncode=1))
    with pytest.raises(ImageQuotaError, match="2 hours"):
        asyncio.run(codex_cli.CodexImageGenerator().generate("draw", [], tmp_path / "p.png"))


def test_refusal_written_only_in_reply_is_still_classified(tmp_path, monkeypatch):
    # 画像ツールが断られても turn は成功で終わり、理由は返答文にだけ書かれる
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    events = [
        {"type": "thread.started", "thread_id": "t-r"},
        {"type": "item.completed", "item": {"type": "agent_message",
                                            "text": "Image generation limit reached. It resets in 3 hours."}},
        {"type": "turn.completed"},
    ]
    monkeypatch.setattr(codex_cli.subprocess, "run", _codex_run(events))
    with pytest.raises(ImageQuotaError, match="3 hours"):
        asyncio.run(codex_cli.CodexImageGenerator().generate("draw", [], tmp_path / "p.png"))


@pytest.mark.parametrize("bad_id", [
    "../etc",
    "not-a-uuid",
    "{12345678-1234-5678-1234-567812345678}",
    "12345678123456781234567812345678",
    "urn:uuid:12345678-1234-5678-1234-567812345678",
])
def test_assembly_and_export_reject_non_canonical_session_ids(bad_id, output_dir):
    assert client.post("/api/assembly/assemble-all", json={"session_id": bad_id}).status_code == 404
    assert client.post("/api/assembly/assemble-page", json={"session_id": bad_id, "page_number": 1}).status_code == 404
    assert client.get(f"/api/assembly/status/{bad_id}").status_code == 404
    assert client.post("/api/export/generate", json={"session_id": bad_id, "format": "pdf"}).status_code == 404
    response = client.post("/api/assembly/upload-image", data={
        "session_id": bad_id, "page_number": 1, "panel_number": 1,
    }, files={"image": ("a.png", b"x", "image/png")})
    assert response.status_code == 404


def test_unknown_but_well_formed_session_is_404(output_dir):
    missing = "12345678-1234-5678-1234-567812345678"
    assert client.get(f"/api/export/download/{missing}/manga.pdf").status_code == 404


def test_existing_session_still_assembles(storyboard, output_dir):
    session_id = create_session(storyboard)
    response = client.post("/api/assembly/assemble-page", json={"session_id": session_id, "page_number": 1})
    assert response.status_code == 200
    assert client.get(f"/api/assembly/status/{session_id}").json() == {"uploaded": []}


def _anthropic_error(cls, status: int):
    import httpx
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return cls("error", response=response, body=None)


@pytest.mark.parametrize("cls_name,status,expected", [
    ("AuthenticationError", 401, "ANTHROPIC_API_KEY が無効です"),
    ("RateLimitError", 429, "利用制限"),
])
def test_claude_api_errors_reach_the_screen_in_japanese(cls_name, status, expected, monkeypatch):
    import anthropic

    from app.config import settings
    from app.services import llm_service

    class FakeMessages:
        async def create(self, **kwargs):
            raise _anthropic_error(getattr(anthropic, cls_name), status)

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr(settings, "anthropic_api_key", "dummy")
    monkeypatch.setattr(llm_service.anthropic, "AsyncAnthropic", FakeClient)
    response = client.post("/api/storyboard/generate", json={"title": "t", "story": "s", "num_pages": 1})
    assert response.status_code == status
    assert expected in response.json()["detail"]
