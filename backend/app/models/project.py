import uuid
from datetime import datetime

from typing import Optional
from sqlalchemy import String, Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.api.models.enums import GenerationStatus


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128))
    business_type: Mapped[str] = mapped_column(String(32))
    schema_snapshot: Mapped[str] = mapped_column(Text)
    status: Mapped[GenerationStatus] = mapped_column(SAEnum(GenerationStatus), default=GenerationStatus.PENDING)
    zip_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
