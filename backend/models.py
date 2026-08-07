"""SQLAlchemy ORM models for ContentFlow QA."""

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from .database import Base


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


class IssueStatus(str, enum.Enum):
    pass_ = "pass"
    fail = "fail"
    warn = "warn"


class ValidationRun(Base):
    """Top-level record for one full validation pipeline execution."""
    __tablename__ = "validation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    partner: Mapped[str] = mapped_column(String(128))
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.queued)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    warn_count: Mapped[int] = mapped_column(Integer, default=0)
    pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    results: Mapped[list["ValidationResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ValidationRun {self.run_id} partner={self.partner} status={self.status}>"


class ValidationResult(Base):
    """Individual validation check result for one asset."""
    __tablename__ = "validation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(16), ForeignKey("validation_runs.run_id"), index=True)
    asset_id: Mapped[str] = mapped_column(String(256), index=True)
    category: Mapped[str] = mapped_column(String(64))   # metadata, xml_feed, etc.
    scenario: Mapped[str] = mapped_column(String(128))  # specific check name
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus))
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    run: Mapped["ValidationRun"] = relationship(back_populates="results")

    def __repr__(self) -> str:
        return f"<ValidationResult {self.asset_id} {self.category}/{self.scenario} {self.status}>"
