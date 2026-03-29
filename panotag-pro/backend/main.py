"""
FastAPI + WebSocket server for PanoTag Pro.
Run: uvicorn backend.main:app --host 127.0.0.1 --port 8756
"""
from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .database import (
    Correction,
    Photo,
    Project,
    Tag,
    box_to_corners_pan_tilt,
    get_engine,
    init_db,
)
from .detector import EngineConfig, ProcessingEngine
from .exporter import export_tags_to_xlsx
from .schemas import (
    CorrectionCreate,
    ExportBody,
    PhotoOut,
    ProcessBody,
    ProjectCreate,
    ProjectOut,
    ScanResult,
    TagOut,
    TagUpdate,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "panotag_pro.db"
engine = get_engine(DB_PATH)
SessionLocal = init_db(engine)

_executor_workers = 1
_executor = None


def get_executor():
    global _executor
    if _executor is None:
        from concurrent.futures import ThreadPoolExecutor

        _executor = ThreadPoolExecutor(max_workers=_executor_workers)
    return _executor


_processing_engine: ProcessingEngine | None = None


def get_processing_engine() -> ProcessingEngine:
    global _processing_engine
    if _processing_engine is None:
        _processing_engine = ProcessingEngine(
            config=EngineConfig(),
            status_cb=lambda _m: None,
        )
    return _processing_engine


def try_gpu_stats() -> dict[str, Any] | None:
    try:
        import pynvml

        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(h)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        return {
            "gpu_util": util.gpu,
            "mem_used_mb": mem.used // (1024**2),
            "mem_total_mb": mem.total // (1024**2),
        }
    except Exception:
        return None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def read_image_dimensions(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
            return int(w), int(h)
    except Exception:
        import cv2

        im = cv2.imread(str(path))
        if im is None:
            return 0, 0
        h, w = im.shape[:2]
        return int(w), int(h)


def emit_event(data: dict[str, Any]) -> None:
    loop = _main_loop
    if loop is None or not loop.is_running():
        return
    try:
        asyncio.run_coroutine_threadsafe(_connection_manager.broadcast(data), loop)
    except Exception:
        logger.debug("emit_event failed", exc_info=True)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


_connection_manager = ConnectionManager()
_main_loop: asyncio.AbstractEventLoop | None = None
_cancel_event = threading.Event()
_process_lock = asyncio.Lock()
_process_running = False
_gpu_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_loop, _gpu_task
    _main_loop = asyncio.get_running_loop()

    async def gpu_loop() -> None:
        while True:
            await asyncio.sleep(2.0)
            s = try_gpu_stats()
            if s:
                await _connection_manager.broadcast({"type": "gpu", **s})

    _gpu_task = asyncio.create_task(gpu_loop())
    yield
    if _gpu_task:
        _gpu_task.cancel()
        try:
            await _gpu_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="PanoTag Pro API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_process_photo_sync(
    path: str,
    stem: str,
    status_cb,
    progress_cb,
    cancel_check,
) -> list[dict]:
    eng = get_processing_engine()
    old_s, old_p = eng.status_cb, eng.progress_cb
    eng.status_cb = status_cb
    eng.progress_cb = progress_cb
    try:
        return eng.process_photo(path, stem, cancel_check=cancel_check)
    finally:
        eng.status_cb = old_s
        eng.progress_cb = old_p


def tag_dict_to_row(tag: Tag, photo_name: str) -> dict[str, Any]:
    return {
        "photo": photo_name,
        "tag_name": tag.tag_name,
        "pan_tl": tag.pan_tl,
        "tilt_tl": tag.tilt_tl,
        "pan_tr": tag.pan_tr,
        "tilt_tr": tag.tilt_tr,
        "pan_br": tag.pan_br,
        "tilt_br": tag.tilt_br,
        "pan_bl": tag.pan_bl,
        "tilt_bl": tag.tilt_bl,
        "conf": tag.confidence,
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "panotag-pro"}


@app.get("/api/gpu")
def gpu_stats():
    s = try_gpu_stats()
    return s or {"error": "NVML unavailable"}


@app.get("/api/process/status")
def process_status():
    return {"running": _process_running}


@app.get("/api/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    out: list[ProjectOut] = []
    for p in db.scalars(select(Project).order_by(Project.created_at.desc())):
        n = (
            db.scalar(
                select(func.count()).select_from(Photo).where(Photo.project_id == p.id)
            )
            or 0
        )
        out.append(
            ProjectOut(
                id=p.id,
                name=p.name,
                folder_path=p.folder_path,
                status=p.status,
                created_at=p.created_at,
                photo_count=int(n),
            )
        )
    return out


@app.post("/api/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    fp = Path(body.folder_path)
    if not fp.is_dir():
        raise HTTPException(status_code=400, detail="folder_path must be an existing directory")
    p = Project(name=body.name.strip(), folder_path=str(fp.resolve()))
    db.add(p)
    db.commit()
    db.refresh(p)
    return ProjectOut(
        id=p.id,
        name=p.name,
        folder_path=p.folder_path,
        status=p.status,
        created_at=p.created_at,
        photo_count=0,
    )


@app.get("/api/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    n = (
        db.scalar(
            select(func.count()).select_from(Photo).where(Photo.project_id == p.id)
        )
        or 0
    )
    return ProjectOut(
        id=p.id,
        name=p.name,
        folder_path=p.folder_path,
        status=p.status,
        created_at=p.created_at,
        photo_count=int(n),
    )


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    for ph in list(db.scalars(select(Photo).where(Photo.project_id == project_id))):
        tids = list(db.scalars(select(Tag.id).where(Tag.photo_id == ph.id)).all())
        if tids:
            db.execute(delete(Correction).where(Correction.tag_id.in_(tids)))
        db.execute(delete(Tag).where(Tag.photo_id == ph.id))
        db.delete(ph)
    db.delete(p)
    db.commit()
    return {"ok": True}


@app.post("/api/projects/{project_id}/scan", response_model=ScanResult)
def scan_project_folder(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    root = Path(p.folder_path)
    if not root.is_dir():
        raise HTTPException(status_code=400, detail="Project folder missing on disk")

    added = 0
    skipped = 0
    photos_out: list[PhotoOut] = []

    for fp in sorted(root.rglob("*")):
        if not fp.is_file():
            continue
        if fp.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        resolved = str(fp.resolve())
        exists = db.scalar(
            select(Photo.id).where(
                Photo.project_id == project_id,
                Photo.full_path == resolved,
            )
        )
        if exists:
            skipped += 1
            continue
        w, h = read_image_dimensions(fp)
        ph = Photo(
            project_id=project_id,
            filename=fp.name,
            full_path=resolved,
            width=w,
            height=h,
            status="queued",
        )
        db.add(ph)
        db.flush()
        added += 1
        photos_out.append(PhotoOut.model_validate(ph))

    db.commit()
    emit_event(
        {
            "type": "scan_complete",
            "project_id": project_id,
            "added": added,
            "skipped": skipped,
        }
    )
    return ScanResult(added=added, skipped=skipped, photos=photos_out)


@app.get("/api/projects/{project_id}/photos", response_model=list[PhotoOut])
def list_photos(project_id: int, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    rows = db.scalars(
        select(Photo)
        .where(Photo.project_id == project_id)
        .order_by(Photo.filename)
    ).all()
    return [PhotoOut.model_validate(x) for x in rows]


@app.get("/api/photos/{photo_id}", response_model=PhotoOut)
def get_photo(photo_id: int, db: Session = Depends(get_db)):
    ph = db.get(Photo, photo_id)
    if not ph:
        raise HTTPException(status_code=404, detail="Photo not found")
    return PhotoOut.model_validate(ph)


@app.get("/api/photos/{photo_id}/tags", response_model=list[TagOut])
def list_tags(photo_id: int, db: Session = Depends(get_db)):
    if not db.get(Photo, photo_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    rows = db.scalars(select(Tag).where(Tag.photo_id == photo_id).order_by(Tag.id)).all()
    return [TagOut.model_validate(x) for x in rows]


@app.patch("/api/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, body: TagUpdate, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    photo = db.get(Photo, tag.photo_id)
    if not photo:
        raise HTTPException(status_code=400, detail="Photo missing")

    if body.tag_name is not None:
        tag.tag_name = body.tag_name.strip()
    for attr in ("x1", "y1", "x2", "y2"):
        v = getattr(body, attr)
        if v is not None:
            setattr(tag, attr, float(v))
    if body.confirmed is not None:
        tag.confirmed = body.confirmed

    if any(
        getattr(body, a) is not None for a in ("x1", "y1", "x2", "y2")
    ) and photo.width > 0 and photo.height > 0:
        corners = box_to_corners_pan_tilt(
            tag.x1,
            tag.y1,
            tag.x2,
            tag.y2,
            float(photo.width),
            float(photo.height),
        )
        for k, v in corners.items():
            setattr(tag, k, v)

    db.commit()
    db.refresh(tag)
    return TagOut.model_validate(tag)


@app.post("/api/tags/{tag_id}/corrections")
def add_correction(tag_id: int, body: CorrectionCreate, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    c = Correction(
        tag_id=tag_id,
        original_text=body.original_text,
        corrected_text=body.corrected_text,
        crop_image_path=body.crop_image_path,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "tag_id": c.tag_id}


@app.post("/api/projects/{project_id}/export")
def export_project(project_id: int, body: ExportBody, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    out_path = Path(body.output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    photos = db.scalars(
        select(Photo).where(Photo.project_id == project_id).order_by(Photo.id)
    ).all()
    rows: list[dict[str, Any]] = []
    for ph in photos:
        for tag in ph.tags:
            rows.append(tag_dict_to_row(tag, ph.filename))

    export_tags_to_xlsx(rows, out_path)
    emit_event({"type": "export_complete", "project_id": project_id, "path": str(out_path)})
    return {"path": str(out_path.resolve()), "row_count": len(rows)}


@app.post("/api/process/cancel")
async def cancel_process():
    global _process_running
    _cancel_event.set()
    emit_event({"type": "cancel_requested"})
    return {"ok": True}


async def _run_process_job(project_id: int, photo_ids: list[int] | None) -> None:
    global _process_running
    import datetime as dt

    _cancel_event.clear()
    _process_running = True
    emit_event({"type": "process_started", "project_id": project_id})

    try:
        with SessionLocal() as db:
            p = db.get(Project, project_id)
            if not p:
                emit_event({"type": "error", "message": "Project not found"})
                return

            q = select(Photo).where(Photo.project_id == project_id)
            if photo_ids:
                q = q.where(Photo.id.in_(photo_ids))
            else:
                q = q.where(Photo.status.in_(("queued", "error")))
            photos = list(db.scalars(q.order_by(Photo.id)).all())

        if not photos:
            emit_event({"type": "process_queue_empty"})
            return

        loop = asyncio.get_running_loop()
        ex = get_executor()

        for idx, photo in enumerate(photos):
            if _cancel_event.is_set():
                emit_event({"type": "cancelled"})
                break

            emit_event(
                {
                    "type": "photo_queued",
                    "index": idx + 1,
                    "total": len(photos),
                    "photo_id": photo.id,
                    "path": photo.full_path,
                }
            )

            with SessionLocal() as db2:
                ph = db2.get(Photo, photo.id)
                if not ph:
                    continue
                ph.status = "processing"
                db2.commit()

            stem = Path(photo.full_path).stem

            def status_cb(msg: str) -> None:
                emit_event({"type": "log", "message": msg, "photo_id": photo.id})

            def progress_cb(d: dict[str, Any]) -> None:
                emit_event({**d, "photo_id": photo.id})

            def cancel_check() -> bool:
                return _cancel_event.is_set()

            try:
                tags_raw = await loop.run_in_executor(
                    ex,
                    lambda: run_process_photo_sync(
                        photo.full_path,
                        stem,
                        status_cb,
                        progress_cb,
                        cancel_check,
                    ),
                )
            except Exception as e:
                logger.exception("process_photo failed")
                emit_event({"type": "error", "message": str(e), "photo_id": photo.id})
                with SessionLocal() as db3:
                    ph = db3.get(Photo, photo.id)
                    if ph:
                        ph.status = "error"
                        db3.commit()
                continue

            if _cancel_event.is_set() and not tags_raw:
                emit_event({"type": "cancelled"})
                break

            with SessionLocal() as db4:
                ph = db4.get(Photo, photo.id)
                if not ph:
                    continue
                db4.execute(delete(Tag).where(Tag.photo_id == ph.id))
                for t in tags_raw:
                    corners = {
                        k: t[k]
                        for k in (
                            "pan_tl",
                            "tilt_tl",
                            "pan_tr",
                            "tilt_tr",
                            "pan_br",
                            "tilt_br",
                            "pan_bl",
                            "tilt_bl",
                        )
                    }
                    tag = Tag(
                        photo_id=ph.id,
                        tag_name=str(t.get("tag_name", "UNKNOWN"))[:512],
                        confidence=float(t.get("conf", 0)),
                        x1=float(t["x1"]),
                        y1=float(t["y1"]),
                        x2=float(t["x2"]),
                        y2=float(t["y2"]),
                        **corners,
                    )
                    db4.add(tag)
                ph.status = "done"
                ph.processed_at = dt.datetime.utcnow()
                ph.tag_count = len(tags_raw)
                db4.commit()

            emit_event(
                {
                    "type": "photo_processed",
                    "photo_id": photo.id,
                    "tag_count": len(tags_raw),
                    "path": photo.full_path,
                }
            )

        emit_event({"type": "process_finished", "project_id": project_id})
    finally:
        _process_running = False


@app.post("/api/projects/{project_id}/process")
async def start_process(project_id: int, body: ProcessBody | None = None):
    global _process_running
    if _process_running:
        raise HTTPException(status_code=409, detail="A processing job is already running")

    with SessionLocal() as s:
        if s.get(Project, project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")

    ids = body.photo_ids if body else None
    asyncio.create_task(_run_process_job(project_id, ids))
    return {"started": True, "project_id": project_id}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await _connection_manager.connect(websocket)
    await websocket.send_json(
        {
            "type": "ready",
            "message": "Connected — use REST POST /api/projects/{id}/process to run detection.",
        }
    )
    g = try_gpu_stats()
    if g:
        await websocket.send_json({"type": "gpu", **g})

    try:
        while True:
            raw = await websocket.receive_text()
            import json

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            cmd = data.get("command")
            if cmd == "ping":
                await websocket.send_json({"type": "pong"})
            elif cmd == "cancel":
                _cancel_event.set()
                await websocket.send_json({"type": "cancel_ack"})
    except WebSocketDisconnect:
        pass
    finally:
        _connection_manager.disconnect(websocket)


def create_app():
    return app
