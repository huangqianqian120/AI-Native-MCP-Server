from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.models.requests import GenerateRequest, GenerationResponse, ProjectSummary
from app.api.models.enums import GenerationStatus
from app.models.project import Project
from app.db.session import get_session
from app.core.generator import GeneratorService

router = APIRouter()


@router.post("", status_code=202)
async def start_generation(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Start generating a mini program project from a BusinessSchema."""
    project = Project(
        name=req.business_schema.project_name,
        business_type=req.business_schema.business_type,
        schema_snapshot=req.business_schema.model_dump_json(),
        status=GenerationStatus.GENERATING,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    generator = GeneratorService()
    background_tasks.add_task(
        generator.generate,
        project_id=project.id,
        schema=req.business_schema,
        db=db,
    )

    return GenerationResponse(project_id=project.id, status=GenerationStatus.GENERATING)


@router.get("/{project_id}/status")
async def get_status(project_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return GenerationResponse(project_id=project.id, status=project.status)


@router.get("/{project_id}/download")
async def download(project_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != GenerationStatus.READY:
        raise HTTPException(status_code=400, detail="Project not ready yet")
    if not project.zip_path or not Path(project.zip_path).exists():
        raise HTTPException(status_code=404, detail="ZIP file not found")

    return FileResponse(
        project.zip_path,
        media_type="application/zip",
        filename=f"{project.name}-ai-native.zip",
    )


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()).limit(50))
    projects = result.scalars().all()
    return [
        ProjectSummary(
            id=p.id,
            name=p.name,
            business_type=p.business_type,
            status=p.status,
            created_at=p.created_at.isoformat(),
            error=p.error,
        )
        for p in projects
    ]
