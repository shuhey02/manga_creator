"""
Generation API: ChatGPT（Codex CLI 経由）でキャラ参照シート・ページ画像を生成する

1枚に数分かかるので、受け付けたらジョブ ID を返し、状態はポーリングで取る。
ジョブはメモリに置くだけなので、サーバー再起動で消える（画像と storyboard.json は残る）。
"""
import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models.schemas import GenerateCharactersRequest, GeneratePageRequest, GenerationJob
from ..services.generation_service import generate_character_sheet, generate_page
from ..services.session_store import (
    SessionNotFoundError,
    load_storyboard,
    output_url,
    session_dir,
)

router = APIRouter(prefix="/api/generation", tags=["generation"])

_jobs: dict[str, GenerationJob] = {}
# 実行中タスクへの参照を持たないと GC で途中停止することがある
_tasks: set[asyncio.Task] = set()


def _start(job: GenerationJob, work: Callable[[], Awaitable[Path]]) -> GenerationJob:
    async def run() -> None:
        job.status = "running"
        try:
            out = await work()
            relative = out.relative_to(session_dir(job.session_id))
            job.image_urls = [output_url(job.session_id, relative)]
            job.status = "done"
        except Exception as e:
            job.error = str(e)
            job.status = "error"

    _jobs[job.job_id] = job
    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job


def _require_session(session_id: str) -> None:
    try:
        load_storyboard(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="セッションが見つかりません。")


@router.post("/characters", response_model=GenerationJob)
async def start_character_sheet(request: GenerateCharactersRequest):
    _require_session(request.session_id)
    job = GenerationJob(session_id=request.session_id, kind="characters")
    return _start(job, lambda: generate_character_sheet(request.session_id))


@router.post("/page", response_model=GenerationJob)
async def start_page(request: GeneratePageRequest):
    _require_session(request.session_id)
    job = GenerationJob(
        session_id=request.session_id, kind="page", page_number=request.page_number
    )
    return _start(
        job,
        lambda: generate_page(
            request.session_id, request.page_number, request.use_character_refs
        ),
    )


@router.get("/job/{job_id}", response_model=GenerationJob)
async def get_job(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。")
    return job
