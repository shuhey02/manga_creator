from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4


# ─── Input schemas ────────────────────────────────────────────────────────────

class StoryboardRequest(BaseModel):
    title: str = Field(..., description="作品タイトル")
    story: str = Field(..., description="ストーリーテキスト")
    genre: str = Field(default="少年漫画", description="ジャンル")
    style: str = Field(default="標準的な漫画スタイル", description="作画スタイル")
    num_pages: int = Field(default=4, ge=1, le=20, description="ページ数")


class AssemblePageRequest(BaseModel):
    session_id: str
    page_number: int


class AssembleAllRequest(BaseModel):
    session_id: str


class ExportRequest(BaseModel):
    session_id: str
    format: str = Field(default="zip", description="zip or pdf")


# ─── Storyboard data models ───────────────────────────────────────────────────

class SpeechBubblePosition(BaseModel):
    x: float = Field(..., ge=0, le=100)
    y: float = Field(..., ge=0, le=100)
    width: float = Field(..., ge=1, le=100)
    height: float = Field(..., ge=1, le=100)


class SpeechBubble(BaseModel):
    text: str
    type: str = Field(default="normal", description="normal|thought|shout|whisper")
    position: SpeechBubblePosition


class PanelLayout(BaseModel):
    x: float = Field(..., ge=0, le=100)
    y: float = Field(..., ge=0, le=100)
    width: float = Field(..., ge=1, le=100)
    height: float = Field(..., ge=1, le=100)


class Panel(BaseModel):
    panel_number: int
    layout: PanelLayout
    composition: str = ""
    camera_angle: str = ""
    background: str = ""
    characters: list[str] = []
    expression: str = ""
    dialogue: str = ""
    sound_effect: str = ""
    image_prompt_en: str = ""
    image_prompt_ja: str = ""
    speech_bubbles: list[SpeechBubble] = []


class MangaPage(BaseModel):
    page_number: int
    page_notes: str = ""
    panels: list[Panel] = []


class Character(BaseModel):
    name: str
    description: str
    prompt_keywords: str


class Storyboard(BaseModel):
    title: str
    genre: str
    style: str
    characters: list[Character] = []
    pages: list[MangaPage] = []


# ─── Response schemas ─────────────────────────────────────────────────────────

class StoryboardResponse(BaseModel):
    session_id: str
    storyboard: Storyboard


class UploadImageResponse(BaseModel):
    session_id: str
    page_number: int
    panel_number: int
    image_url: str


class AssemblePageResponse(BaseModel):
    session_id: str
    page_number: int
    image_url: str


class AssembleAllResponse(BaseModel):
    session_id: str
    pages: list[AssemblePageResponse]


class ExportResponse(BaseModel):
    session_id: str
    download_url: str
    filename: str
