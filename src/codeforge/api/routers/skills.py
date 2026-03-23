from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from codeforge.infrastructure.skills.loader import SkillsLoader

router = APIRouter(prefix="/api/skills", tags=["skills"])

SKILLS_DIR = Path(__file__).parents[2] / "skills"


class SkillResponseSchema(BaseModel):
    name: str
    description: str
    available: bool
    missing: str


@router.get("", response_model=list[SkillResponseSchema])
async def list_skills() -> list[SkillResponseSchema]:
    loader = SkillsLoader(SKILLS_DIR)
    items = loader.list_available()
    return [
        SkillResponseSchema(
            name=str(item["name"]),
            description=str(item["description"]),
            available=bool(item["available"]),
            missing=str(item["missing"]),
        )
        for item in items
    ]
