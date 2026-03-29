"""
SQLite storage for OCR correction hints (desktop app).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
DB_PATH = _ROOT / "tags.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as c:
        # Legacy table: still read for correction hints from older web sessions.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS tag_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                photo_filename TEXT NOT NULL,
                image_path TEXT NOT NULL DEFAULT '',
                sort_index INTEGER NOT NULL,
                x1 REAL NOT NULL,
                y1 REAL NOT NULL,
                x2 REAL NOT NULL,
                y2 REAL NOT NULL,
                pan_tl REAL,
                tilt_tl REAL,
                pan_tr REAL,
                tilt_tr REAL,
                pan_br REAL,
                tilt_br REAL,
                pan_bl REAL,
                tilt_bl REAL,
                conf REAL NOT NULL,
                ocr_conf REAL,
                system_text TEXT NOT NULL,
                corrected_text TEXT,
                deleted INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_session ON tag_records(session_id)"
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS ocr_corrections (
                ocr_key TEXT PRIMARY KEY,
                corrected TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )


def remember_ocr_correction(raw_ocr: str, corrected: str) -> None:
    """
    Persist mapping raw OCR reading -> label you want. Keys are normalized lowercase.
    """
    raw = (raw_ocr or "").strip()
    cor = (corrected or "").strip()
    if not raw or raw.upper() == "UNKNOWN":
        return
    if not cor or raw.lower() == cor.lower():
        return
    now = time.time()
    key = raw.lower()
    with get_conn() as c:
        c.execute(
            """
            INSERT INTO ocr_corrections (ocr_key, corrected, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(ocr_key) DO UPDATE SET
                corrected = excluded.corrected,
                updated_at = excluded.updated_at
            """,
            (key, cor, now),
        )


def get_learned_correction_map() -> dict[str, str]:
    """
    Normalized raw OCR string -> user-approved text.
    ocr_corrections first; then legacy tag_records with user corrections.
    """
    out: dict[str, str] = {}
    with get_conn() as c:
        cur = c.execute(
            """
            SELECT ocr_key, corrected FROM ocr_corrections
            ORDER BY updated_at DESC
            """
        )
        for row in cur.fetchall():
            k = (row["ocr_key"] or "").strip().lower()
            if k and k != "unknown" and k not in out:
                out[k] = (row["corrected"] or "").strip()
        try:
            cur = c.execute(
                """
                SELECT system_text, corrected_text, updated_at
                FROM tag_records
                WHERE deleted = 0
                  AND corrected_text IS NOT NULL
                  AND TRIM(corrected_text) != ''
                  AND LOWER(TRIM(corrected_text)) != LOWER(TRIM(system_text))
                ORDER BY updated_at DESC
                """
            )
            for row in cur.fetchall():
                k = (row["system_text"] or "").strip().lower()
                if not k or k == "unknown":
                    continue
                if k not in out:
                    out[k] = (row["corrected_text"] or "").strip()
        except sqlite3.OperationalError:
            pass
    return out
