from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import BACKEND_ROOT, get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    data_origin: Mapped[str | None] = mapped_column(String, nullable=True)
    csv_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    dataset_id: Mapped[str] = mapped_column(String)
    experiment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    parameters_json: Mapped[str] = mapped_column(Text)
    observed: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="measured")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    dataset_version: Mapped[int] = mapped_column(Integer)
    strategy: Mapped[str] = mapped_column(String)
    config_json: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InferenceLog(Base):
    __tablename__ = "inference_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    purpose: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        if url.startswith("sqlite"):
            data_dir = BACKEND_ROOT / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            if url.startswith("sqlite:///./"):
                rel = url.replace("sqlite:///./", "")
                url = f"sqlite:///{(BACKEND_ROOT / rel).as_posix()}"
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def session():
    get_engine()
    assert _Session is not None
    return _Session()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def dump(data: Any) -> str:
    return json.dumps(data, default=str)


def load(text: str | None, default: Any = None) -> Any:
    if not text:
        return default
    return json.loads(text)


def sample_csv_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "samples" / "nmc811_processing_demo.csv"
