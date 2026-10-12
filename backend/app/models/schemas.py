from pydantic import BaseModel, Field
from typing import Literal, Optional
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
    # auto は吹き出しが縦長なら縦書き、横長なら横書き（向きを持たない既存のネームの見た目を変えないため）
    orientation: Literal["auto", "vertical", "horizontal"] = "auto"


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
    sound_effect_orientation: Literal["vertical", "horizontal"] = "vertical"
    image_prompt_en: str = ""
    image_prompt_ja: str = ""
    speech_bubbles: list[SpeechBubble] = []
    # AI 生成ページ上で実際に描かれたコマ枠（生成画像全体に対する 0〜100%）
    rendered_layout: Optional[PanelLayout] = None


class MangaPage(BaseModel):
    page_number: int
    page_notes: str = ""
    panels: list[Panel] = []
    # AI 生成したページ画像（セッションディレクトリからの相対パス）
    generated_image: Optional[str] = None


class Character(BaseModel):
    name: str
    description: str
    prompt_keywords: str
    # キャラ参照シート（セッションディレクトリからの相対パス）
    reference_image: Optional[str] = None


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


class GeneratePageRequest(BaseModel):
    session_id: str
    page_number: int
    use_character_refs: bool = True


class GenerateCharactersRequest(BaseModel):
    session_id: str


class GenerationJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    kind: str = Field(..., description="page|characters")
    page_number: Optional[int] = None
    status: str = Field(default="queued", description="queued|running|done|error")
    image_urls: list[str] = []
    error: Optional[str] = None
    # 画面の出し分け用: quota（利用枠切れ）/ auth（未ログイン）/ other
    error_kind: Optional[str] = None


class ExportResponse(BaseModel):
    session_id: str
    download_url: str
    filename: str
