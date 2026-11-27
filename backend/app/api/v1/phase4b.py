from __future__ import annotations
# ruff: noqa: E501, I001

import hashlib
import re
import secrets
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File as UploadFileMarker, HTTPException, UploadFile
from fastapi.responses import FileResponse as DownloadResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_capability, require_user
from app.core.config import settings
from app.core.db import get_session
from app.models.audit_log import AuditLog
from app.models.challenge import ChallengeFile, Hint, HintUnlock
from app.models.scoring import ScoreEvent
from app.models.user import User
from app.schemas.challenges import HintAdminResponse, HintListResponse, HintWrite
from app.api.v1.challenges import challenge_or_404, eligible

router = APIRouter(tags=["hints", "files"])


def storage_root() -> Path:
    root = Path(settings.file_storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def clean_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip(".")
    return (cleaned or "download")[:255]


async def audit(session: AsyncSession, admin: User, action: str, target: str, meta: dict | None = None) -> None:
    session.add(AuditLog(actor_id=admin.id, action=action, target=target, meta=meta or {}))


async def hint_or_404(session: AsyncSession, hint_id: uuid.UUID) -> Hint:
    hint = await session.get(Hint, hint_id)
    if not hint:
        raise HTTPException(status_code=404, detail="Hint not found")
    return hint


async def validate_hint_requirement(session: AsyncSession, challenge_id: uuid.UUID, requires_hint_id: uuid.UUID | None, current_id: uuid.UUID | None = None) -> None:
    if requires_hint_id is None:
        return
    required = await hint_or_404(session, requires_hint_id)
    if required.challenge_id != challenge_id or required.id == current_id:
        raise HTTPException(status_code=422, detail="Hint prerequisite must belong to this challenge")
    rows = list((await session.scalars(select(Hint))).all())
    graph = {row.id: row.requires_hint_id for row in rows}
    graph[current_id or uuid.UUID(int=0)] = requires_hint_id
    visiting: set[uuid.UUID] = set()
    visited: set[uuid.UUID] = set()
    def visit(node: uuid.UUID) -> bool:
        if node in visiting:
            return True
        if node in visited or graph.get(node) is None:
            return False
        visiting.add(node)
        result = visit(graph[node])
        visiting.remove(node)
        visited.add(node)
        return result
    if visit(current_id or uuid.UUID(int=0)):
        raise HTTPException(status_code=422, detail="Hint prerequisites cannot contain a cycle")


@router.get("/admin/challenges/{challenge_id}/hints", response_model=list[HintListResponse])
async def admin_list_hints(challenge_id: uuid.UUID, _admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    await challenge_or_404(session, challenge_id)
    return [HintListResponse.model_validate(hint) for hint in (await session.scalars(select(Hint).where(Hint.challenge_id == challenge_id).order_by(Hint.sort_order, Hint.id))).all()]


@router.post("/admin/challenges/{challenge_id}/hints", response_model=HintAdminResponse, status_code=201)
async def admin_create_hint(challenge_id: uuid.UUID, payload: HintWrite, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    await challenge_or_404(session, challenge_id)
    await validate_hint_requirement(session, challenge_id, payload.requires_hint_id)
    hint = Hint(challenge_id=challenge_id, **payload.model_dump())
    session.add(hint)
    await session.flush()
    await audit(session, admin, "hint_created", f"hint:{hint.id}", {"challenge_id": str(challenge_id)})
    await session.commit()
    return hint


@router.patch("/admin/hints/{hint_id}", response_model=HintAdminResponse)
async def admin_update_hint(hint_id: uuid.UUID, payload: HintWrite, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    hint = await hint_or_404(session, hint_id)
    await validate_hint_requirement(session, hint.challenge_id, payload.requires_hint_id, hint.id)
    for key, value in payload.model_dump().items():
        setattr(hint, key, value)
    await audit(session, admin, "hint_updated", f"hint:{hint.id}", {"challenge_id": str(hint.challenge_id)})
    await session.commit()
    return hint


@router.patch("/admin/challenges/{challenge_id}/hints/{hint_id}", response_model=HintAdminResponse)
async def admin_update_challenge_hint(challenge_id: uuid.UUID, hint_id: uuid.UUID, payload: HintWrite, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    hint = await hint_or_404(session, hint_id)
    if hint.challenge_id != challenge_id:
        raise HTTPException(status_code=404, detail="Hint not found")
    return await admin_update_hint(hint_id, payload, admin, session)


@router.delete("/admin/hints/{hint_id}", status_code=204, response_model=None)
async def admin_delete_hint(hint_id: uuid.UUID, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    hint = await hint_or_404(session, hint_id)
    if await session.scalar(select(Hint.id).where(Hint.requires_hint_id == hint.id)):
        raise HTTPException(status_code=409, detail="Hint is required by another hint")
    await session.delete(hint)
    await audit(session, admin, "hint_deleted", f"hint:{hint.id}")
    await session.commit()


@router.delete("/admin/challenges/{challenge_id}/hints/{hint_id}", status_code=204, response_model=None)
async def admin_delete_challenge_hint(challenge_id: uuid.UUID, hint_id: uuid.UUID, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    hint = await hint_or_404(session, hint_id)
    if hint.challenge_id != challenge_id:
        raise HTTPException(status_code=404, detail="Hint not found")
    await admin_delete_hint(hint_id, admin, session)


@router.post("/hints/{hint_id}/unlock")
async def unlock_hint(hint_id: uuid.UUID, user: User = Depends(require_capability("can_unlock_hints")), session: AsyncSession = Depends(get_session)):
    if user.team_id is None:
        raise HTTPException(status_code=403, detail="You must be in a team to unlock hints")
    hint = await hint_or_404(session, hint_id)
    challenge = await challenge_or_404(session, hint.challenge_id)
    if not await eligible(session, challenge, user.team_id):
        raise HTTPException(status_code=404, detail="Hint not found")
    if hint.requires_hint_id is not None and not await session.scalar(select(HintUnlock.id).where(HintUnlock.team_id == user.team_id, HintUnlock.hint_id == hint.requires_hint_id)):
        raise HTTPException(status_code=409, detail="Required hint has not been unlocked")
    stmt = insert(HintUnlock).values(team_id=user.team_id, user_id=user.id, hint_id=hint.id).on_conflict_do_nothing(index_elements=["team_id", "hint_id"])
    inserted = (await session.execute(stmt.returning(HintUnlock.id))).scalar_one_or_none()
    if inserted is not None:
        session.add(ScoreEvent(team_id=user.team_id, kind="hint", delta=-hint.cost))
    await session.commit()
    return {"id": hint.id, "content": hint.content, "cost": hint.cost, "sort_order": hint.sort_order, "unlocked": True}


@router.post("/admin/challenges/{challenge_id}/files", status_code=201)
async def admin_upload_file(challenge_id: uuid.UUID, upload: UploadFile = UploadFileMarker(...), admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    await challenge_or_404(session, challenge_id)
    size = 0
    digest = hashlib.sha256()
    storage_name = secrets.token_hex(32)
    destination = storage_root() / storage_name
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.file_upload_max_bytes:
                    raise HTTPException(status_code=413, detail="File exceeds the upload size limit")
                digest.update(chunk)
                output.write(chunk)
        record = ChallengeFile(challenge_id=challenge_id, storage_name=storage_name, original_name=clean_filename(upload.filename or "download"), sha256=digest.hexdigest(), size_bytes=size, content_type=upload.content_type or "application/octet-stream")
        session.add(record)
        await session.flush()
        await audit(session, admin, "challenge_file_uploaded", f"challenge:{challenge_id}", {"file_id": str(record.id)})
        await session.commit()
        return {"id": record.id, "original_name": record.original_name, "size_bytes": record.size_bytes, "content_type": record.content_type, "sha256": record.sha256}
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


@router.delete("/admin/files/{file_id}", status_code=204, response_model=None)
async def admin_delete_file(file_id: uuid.UUID, admin: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    record = await session.get(ChallengeFile, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    path = storage_root() / record.storage_name
    path.unlink(missing_ok=True)
    await session.delete(record)
    await audit(session, admin, "challenge_file_deleted", f"file:{file_id}")
    await session.commit()


@router.get("/files/{file_id}")
async def download_file(file_id: uuid.UUID, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    record = await session.get(ChallengeFile, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    challenge = await challenge_or_404(session, record.challenge_id)
    if user.role != "admin":
        if user.team_id is None:
            raise HTTPException(status_code=404, detail="File not found")
        from app.services.lifecycle import get_capabilities, get_state, parse_datetime, read_lifecycle_config
        values = await read_lifecycle_config(session)
        state = get_state(event_start=parse_datetime(values["event_start"]), event_end=parse_datetime(values["event_end"]), state_override=values["state_override"])
        if not get_capabilities(state)["can_view_challenges"]:
            raise HTTPException(status_code=404, detail="File not found")
        values = await eligible(session, challenge, user.team_id)
        if not values:
            raise HTTPException(status_code=404, detail="File not found")
    path = (storage_root() / record.storage_name).resolve()
    if path.parent != storage_root() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    response = DownloadResponse(path=str(path), media_type=record.content_type, filename=clean_filename(record.original_name), headers={"X-Content-Type-Options": "nosniff"})
    return response
