from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.intelligence import (
    AgentMemoryResponse,
    AgentMemoryUpsert,
    AgentSkillCreate,
    AgentSkillResponse,
    AgentSkillUpdate,
)
from codeforge.domain.entities.agent_memory import AgentMemory
from codeforge.domain.entities.agent_skill import AgentSkill
from codeforge.domain.value_objects.project_id import ProjectId

router = APIRouter(prefix="/api/projects/{project_id}", tags=["intelligence"])


@router.get("/skills", response_model=list[AgentSkillResponse])
async def list_skills(
    project_id: str,
    repos: RepositoryContainer = Depends(get_repositories),
) -> list[AgentSkillResponse]:
    skills = await repos.agent_skill_repository.list_by_project(ProjectId(project_id))
    return [_skill_to_response(s) for s in skills]


@router.post("/skills", response_model=AgentSkillResponse, status_code=201)
async def create_skill(
    project_id: str,
    body: AgentSkillCreate,
    repos: RepositoryContainer = Depends(get_repositories),
) -> AgentSkillResponse:
    from codeforge.domain.entities.agent import AgentType

    agent_type = None
    if body.agent_type is not None:
        try:
            agent_type = AgentType(body.agent_type)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"Unknown agent_type: {body.agent_type}"
            ) from exc

    skill = AgentSkill.create(
        id=str(uuid.uuid4()),
        name=body.name,
        content=body.content,
        always_active=body.always_active,
        project_id=ProjectId(project_id),
        agent_type=agent_type,
    )
    await repos.agent_skill_repository.save(skill)
    return _skill_to_response(skill)


@router.put("/skills/{skill_id}", response_model=AgentSkillResponse)
async def update_skill(
    project_id: str,
    skill_id: str,
    body: AgentSkillUpdate,
    repos: RepositoryContainer = Depends(get_repositories),
) -> AgentSkillResponse:
    skill = await repos.agent_skill_repository.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    skill.update(name=body.name, content=body.content, always_active=body.always_active)
    await repos.agent_skill_repository.save(skill)
    return _skill_to_response(skill)


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(
    project_id: str,
    skill_id: str,
    repos: RepositoryContainer = Depends(get_repositories),
) -> None:
    skill = await repos.agent_skill_repository.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    await repos.agent_skill_repository.delete(skill_id)


@router.get("/memory", response_model=list[AgentMemoryResponse])
async def list_memory(
    project_id: str,
    repos: RepositoryContainer = Depends(get_repositories),
) -> list[AgentMemoryResponse]:
    entries = await repos.agent_memory_repository.list_for_project(ProjectId(project_id))
    return [_memory_to_response(m) for m in entries]


@router.put("/memory", response_model=AgentMemoryResponse)
async def upsert_memory(
    project_id: str,
    body: AgentMemoryUpsert,
    repos: RepositoryContainer = Depends(get_repositories),
) -> AgentMemoryResponse:
    pid = ProjectId(project_id)
    existing = await repos.agent_memory_repository.get(pid, body.key)
    if existing is not None:
        existing.update(body.content)
        await repos.agent_memory_repository.save(existing)
        return _memory_to_response(existing)

    memory = AgentMemory.create(
        id=str(uuid.uuid4()),
        project_id=pid,
        key=body.key,
        content=body.content,
    )
    await repos.agent_memory_repository.save(memory)
    return _memory_to_response(memory)


@router.delete("/memory/{key}", status_code=204)
async def delete_memory(
    project_id: str,
    key: str,
    repos: RepositoryContainer = Depends(get_repositories),
) -> None:
    pid = ProjectId(project_id)
    existing = await repos.agent_memory_repository.get(pid, key)
    if existing is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    await repos.agent_memory_repository.delete(existing.id)


def _skill_to_response(skill: AgentSkill) -> AgentSkillResponse:
    return AgentSkillResponse(
        id=skill.id,
        name=skill.name,
        content=skill.content,
        always_active=skill.always_active,
        project_id=str(skill.project_id) if skill.project_id else None,
        agent_type=skill.agent_type.value if skill.agent_type else None,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def _memory_to_response(memory: AgentMemory) -> AgentMemoryResponse:
    return AgentMemoryResponse(
        id=memory.id,
        project_id=str(memory.project_id),
        key=memory.key,
        content=memory.content,
        updated_at=memory.updated_at,
    )
