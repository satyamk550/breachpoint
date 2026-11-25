import asyncio
import getpass
import sys

from sqlalchemy import func, select

from app.core.db import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User


async def create_admin() -> None:
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip().casefold()
    password = getpass.getpass("Admin password: ")
    if await _exists(username, email):
        raise SystemExit("Username or email already exists")
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    async with AsyncSessionLocal() as session:
        session.add(User(username=username, email=email, password_hash=password_hash, role="admin"))
        await session.commit()
    print("Admin created.")


async def check_challenges() -> None:
    from app.services.challenge_health import build_challenge_health
    async with AsyncSessionLocal() as session:
        report = await build_challenge_health(session)
    for key, values in report.items():
        print(f"{key}: {len(values)}")
        for value in values:
            print(f"  {value}")


async def _exists(username: str, email: str) -> bool:
    async with AsyncSessionLocal() as session:
        return (
            await session.scalar(
                select(User.id).where(
                    (func.lower(User.username) == username.casefold())
                    | (func.lower(User.email) == email)
                )
            )
            is not None
        )


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"create-admin", "check-challenges"}:
        raise SystemExit("Usage: python -m app.cli create-admin|check-challenges")
    asyncio.run(create_admin() if sys.argv[1] == "create-admin" else check_challenges())
