"""One-time setup: promote an already-registered user to the admin role.

The public register endpoint intentionally never accepts a role (accepting
one there would be a privilege-escalation hole), so the very first admin
account has to be created this way. Run once per user you want to promote,
from the backend/ directory:

    python scripts/promote_admin.py someone@example.com
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import User  # noqa: E402


async def main(email: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"[error] no user registered with email: {email}")
            return
        if user.role == UserRole.ADMIN:
            print(f"[skip] {email} is already an admin")
            return
        user.role = UserRole.ADMIN
        await session.commit()
        print(f"[done] {email} promoted to admin")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/promote_admin.py <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
