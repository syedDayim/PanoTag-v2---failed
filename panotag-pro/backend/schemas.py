"""Pydantic schemas for REST API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    folder_path: str = Field(..., min_length=1)


class ProjectOut(BaseModel):
    id: int
    name: str
    folder_path: str
    status: str
    created_at: datetime
    photo_count: int = 0

    model_config = {"from_attributes": True}


class PhotoOut(BaseModel):
    id: int
    project_id: int
    filename: str
    full_path: str
    width: int
    height: int
    status: str
    tag_count: int
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class TagOut(BaseModel):
    id: int
    photo_id: int
    tag_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    pan_tl: float
    tilt_tl: float
    pan_tr: float
    tilt_tr: float
    pan_br: float
    tilt_br: float
    pan_bl: float
    tilt_bl: float
    confirmed: bool

    model_config = {"from_attributes": True}


class TagUpdate(BaseModel):
    tag_name: str | None = None
    x1: float | None = None
    y1: float | None = None
    x2: float | None = None
    y2: float | None = None
    confirmed: bool | None = None


class CorrectionCreate(BaseModel):
    original_text: str
    corrected_text: str
    crop_image_path: str | None = None


class ProcessBody(BaseModel):
    photo_ids: list[int] | None = None


class ExportBody(BaseModel):
    output_path: str


class ScanResult(BaseModel):
    added: int
    skipped: int
    photos: list[PhotoOut]
