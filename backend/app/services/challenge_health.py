from __future__ import annotations
# ruff: noqa: E501, E701, E702, I001

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.challenge import Challenge, ChallengeFile, ChallengePrerequisite, Flag


async def build_challenge_health(session: AsyncSession) -> dict:
    challenges = list((await session.scalars(select(Challenge).order_by(Challenge.created_at))).all())
    flags = list((await session.scalars(select(Flag))).all())
    files = list((await session.scalars(select(ChallengeFile))).all())
    flags_by_challenge = {challenge.id: 0 for challenge in challenges}
    for flag in flags:
        flags_by_challenge[flag.challenge_id] = flags_by_challenge.get(flag.challenge_id, 0) + 1
    root = Path(settings.file_storage_dir).resolve()
    missing_files = []
    mismatched_files = []
    for file in files:
        path = root / file.storage_name
        if not path.is_file():
            missing_files.append(str(file.id))
        else:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != file.sha256:
                mismatched_files.append(str(file.id))
    invalid_scoring = [str(c.id) for c in challenges if c.points < 0 or c.initial < c.minimum or c.decay <= 0]
    graph: dict = {}
    for row in (await session.execute(select(ChallengePrerequisite))).all():
        graph.setdefault(row.challenge_id, set()).add(row.requires_challenge_id)
    visiting, visited = set(), set()
    cycles = set()
    def visit(node):
        if node in visiting:
            cycles.add(str(node)); return True
        if node in visited: return False
        visiting.add(node)
        any_cycle = any(visit(child) for child in graph.get(node, set()))
        visiting.remove(node); visited.add(node)
        return any_cycle
    for node in graph: visit(node)
    return {"no_active_flag": [str(c.id) for c in challenges if c.visibility == "visible" and flags_by_challenge.get(c.id, 0) == 0], "missing_files": missing_files, "file_sha256_mismatch": mismatched_files, "invalid_scoring_bounds": invalid_scoring, "prerequisite_cycles": sorted(cycles), "visible_zero_points": [str(c.id) for c in challenges if c.visibility == "visible" and c.points == 0]}
