
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import ChatSession, User
from schemas import ChatSessionCreate, ChatSessionResponse

router = APIRouter(prefix="/api/chats", tags=["Chats"])


@router.post(
    "/",
    response_model=ChatSessionResponse,
    status_code=201,
)
def create_chat(
    payload: ChatSessionCreate,
    db: Session = Depends(get_db),
):
    user = db.get(User, payload.user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    chat = ChatSession(
        user_id=user.id,
        title=payload.title,
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    return chat
