
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.essay import generate_essay

router = APIRouter(prefix="/api/essays", tags=["Essays"])


class EssayRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    provider: Literal["ollama", "openrouter"] = "ollama"


class EssayResponse(BaseModel):
    title: str
    content: str
    sources: list[str]
    model: str


@router.post("/generate", response_model=EssayResponse)
def create_essay(payload: EssayRequest):
    try:
        return generate_essay(
            topic=payload.topic.strip(),
            provider=payload.provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        print(f"Essay generation failed: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=502,
            detail="Essay generation failed. Check the backend terminal.",
        )

