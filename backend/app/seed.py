"""Seed dev users (admin + demo). Run: python -m app.seed"""
from __future__ import annotations

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import AccountStatus, User, UserRole


def seed() -> None:
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "admin@vwa.local").first():
            db.add(
                User(
                    email="admin@vwa.local",
                    full_name="Admin",
                    password_hash=hash_password("Admin!12345"),
                    email_verified=True,
                    role=UserRole.admin,
                    account_status=AccountStatus.active,
                )
            )
        if not db.query(User).filter(User.email == "demo@vwa.local").first():
            db.add(
                User(
                    email="demo@vwa.local",
                    full_name="Demo User",
                    password_hash=hash_password("Demo!12345"),
                    email_verified=True,
                    role=UserRole.user,
                    account_status=AccountStatus.active,
                )
            )
        db.commit()
        print("Seeded: admin@vwa.local / Admin!12345  and  demo@vwa.local / Demo!12345")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
