
# backend/routes/users.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from database import get_db
from models import User

router = APIRouter(prefix="/api/users", tags=["Users"])

password_hasher = PasswordHash.recommended()


class AuthRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


def normalize_email(email: str) -> str:
    email = email.strip().lower()

    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=422, detail="Enter a valid email address.")

    return email


@router.post("/register", status_code=201)
def register(payload: AuthRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)

    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Please log in.",
        )

    user = User(
        email=email,
        password_hash=password_hasher.hash(payload.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create your account.",
        )

    return {
        "message": "Account created successfully.",
        "user": {
            "id": user.id,
            "email": user.email,
        },
    }


@router.post("/login")
def login(payload: AuthRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)

    user = db.query(User).filter(User.email == email).first()

    # Return the same error for unknown emails and incorrect passwords.
    if (
        user is None
        or not user.password_hash
        or not password_hasher.verify(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    return {
        "message": "Login successful.",
        "user": {
            "id": user.id,
            "email": user.email,
        },
    }
