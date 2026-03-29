"""SQLite + SQLAlchemy models for PanoTag Pro."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    folder_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    status: Mapped[str] = mapped_column(String(64), default="active")

    photos: Mapped[list["Photo"]] = relationship("Photo", back_populates="project")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    full_path: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    tag_count: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="photos")
    tags: Mapped[list["Tag"]] = relationship(back_populates="photo")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), nullable=False)
    tag_name: Mapped[str] = mapped_column(String(512), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float] = mapped_column(Float, nullable=False)
    y2: Mapped[float] = mapped_column(Float, nullable=False)
    pan_tl: Mapped[float] = mapped_column(Float)
    tilt_tl: Mapped[float] = mapped_column(Float)
    pan_tr: Mapped[float] = mapped_column(Float)
    tilt_tr: Mapped[float] = mapped_column(Float)
    pan_br: Mapped[float] = mapped_column(Float)
    tilt_br: Mapped[float] = mapped_column(Float)
    pan_bl: Mapped[float] = mapped_column(Float)
    tilt_bl: Mapped[float] = mapped_column(Float)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    photo: Mapped["Photo"] = relationship(back_populates="tags")
    corrections: Mapped[list["Correction"]] = relationship(
        "Correction", back_populates="tag"
    )


class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    crop_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    tag: Mapped["Tag"] = relationship("Tag", back_populates="corrections")


class TrainingExport(Base):
    __tablename__ = "training_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exported_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    tag_count: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(String(64), default="")


def get_engine(db_path: Path | str):
    return create_engine(f"sqlite:///{Path(db_path).resolve()}", echo=False, future=True)


def init_db(engine) -> sessionmaker:
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False, future=True)


def pixel_to_pan_tilt(x: float, y: float, img_w: float, img_h: float) -> tuple[float, float]:
    pan = (x / img_w) * 360.0 - 180.0
    tilt = 90.0 - (y / img_h) * 180.0
    return round(pan, 4), round(tilt, 4)


def box_to_corners_pan_tilt(
    x1: float, y1: float, x2: float, y2: float, img_w: float, img_h: float
) -> dict[str, float]:
    tl = pixel_to_pan_tilt(x1, y1, img_w, img_h)
    tr = pixel_to_pan_tilt(x2, y1, img_w, img_h)
    br = pixel_to_pan_tilt(x2, y2, img_w, img_h)
    bl = pixel_to_pan_tilt(x1, y2, img_w, img_h)
    return {
        "pan_tl": tl[0],
        "tilt_tl": tl[1],
        "pan_tr": tr[0],
        "tilt_tr": tr[1],
        "pan_br": br[0],
        "tilt_br": br[1],
        "pan_bl": bl[0],
        "tilt_bl": bl[1],
    }
