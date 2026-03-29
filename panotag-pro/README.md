# PanoTag Pro

Professional 360° equipment tag extraction — **Electron + React** frontend, **FastAPI** backend, **SQLite** database, **YOLOv8 + PaddleOCR/EasyOCR** on GPU.

## Status

This repository contains a **working scaffold**:

| Area | Status |
|------|--------|
| `backend/detector.py` | Tiling (when width > 4096), YOLO FP16 on CUDA, PaddleOCR + EasyOCR fallback, NMS, pan/tilt |
| `backend/main.py` | FastAPI, WebSocket `/ws`, `/api/health`, `/api/gpu` |
| `backend/database.py` | SQLAlchemy models (projects, photos, tags, corrections) |
| `backend/exporter.py` | Excel export with corner colours |
| `backend/trainer.py` | Stub for Paddle fine-tune |
| `frontend/` | Vite + React + Tailwind — placeholder screens |
| `electron/` | Opens dev server (spawn backend manually or extend) |

**Not yet implemented end-to-end:** Electron spawning uvicorn, full batch UI, Fabric.js review, job queue persistence, Paddle training pipeline.

## Backend (dev)

```bash
cd panotag-pro
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
uvicorn backend.main:app --host 127.0.0.1 --port 8756 --reload
```

WebSocket test: connect to `ws://127.0.0.1:8756/ws`, send:

```json
{"command":"process_photo","path":"C:/path/to/pano.jpg"}
```

## Frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

## Pan / tilt (unchanged)

```
pan  = (x / img_w) * 360 - 180
tilt = 90 - (y / img_h) * 180
```

## Project layout

See spec Section 8 — `electron/`, `frontend/`, `backend/`, `models/`.
