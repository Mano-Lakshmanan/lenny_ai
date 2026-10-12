
from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    id: int
    email: str

    model_config = ConfigDict(from_attributes=True)


class ChatSessionCreate(BaseModel):
    user_id: int
    title: str = "New Chat"


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    title: str

    model_config = ConfigDict(from_attributes=True)
