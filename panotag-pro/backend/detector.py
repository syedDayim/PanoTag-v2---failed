"""
GPU detection engine: YOLOv8 (FP16 batch) + PaddleOCR / EasyOCR fallback.
Coordinates always full-resolution; pan/tilt via database helpers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import cv2
import numpy as np

from .database import box_to_corners_pan_tilt
from .tiler import generate_tiles

logger = logging.getLogger(__name__)

try:
    from turbojpeg import TJPF_RGB, TurboJPEG
except ImportError:
    TJPF_RGB = None
    TurboJPEG = None

try:
    import torch
except ImportError:
    torch = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

try:
    import easyocr
except ImportError:
    easyocr = None


StatusCb = Callable[[str], None]
ProgressCb = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]


def _nms(boxes: list[tuple], iou_threshold: float = 0.42) -> list[tuple]:
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b[4], reverse=True)
    kept: list[tuple] = []

    def iou(a, b) -> float:
        ax1, ay1, ax2, ay2, _ = a
        bx1, by1, bx2, by2, _ = b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0:
            return 0.0
        ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
        return inter / max(ua, 1)

    while boxes:
        best = boxes.pop(0)
        kept.append(best)
        boxes = [b for b in boxes if iou(best, b) < iou_threshold]
    return kept


@dataclass
class EngineConfig:
    tile_size: int = 1280
    overlap: float = 0.20
    yolo_conf: float = 0.20
    yolo_imgsz: int = 1280
    yolo_batch: int = 4
    use_fp16: bool = True
    tiling_threshold_w: int = 4096
    max_tags: int = 64
    nms_iou_tile: float = 0.48
    nms_iou_global: float = 0.42
    ocr_max_width: int = 800


@dataclass
class ProcessingEngine:
    config: EngineConfig = field(default_factory=EngineConfig)
    status_cb: StatusCb = field(default=lambda _s: None)
    progress_cb: Optional[ProgressCb] = field(default=None)
    yolo: Any = None
    paddle: Any = None
    reader: Any = None
    _cuda: bool = False
    _device: str | int = "cpu"

    def __post_init__(self):
        if torch is not None:
            try:
                self._cuda = bool(torch.cuda.is_available())
            except Exception:
                self._cuda = False
        self._device = 0 if self._cuda else "cpu"
        self._load_models()

    def _log(self, msg: str) -> None:
        self.status_cb(msg)
        logger.info(msg)

    def _emit_progress(self, payload: dict[str, Any]) -> None:
        if self.progress_cb:
            self.progress_cb(payload)

    def _load_models(self) -> None:
        if YOLO is not None:
            try:
                self.yolo = YOLO("yolov8n.pt")
                if self._cuda:
                    self.yolo.to("cuda")
                self._log(f"YOLOv8 ready ({'cuda' if self._cuda else 'cpu'})")
            except Exception as e:
                self._log(f"YOLO load failed: {e}")
                self.yolo = None

        if PaddleOCR is not None:
            try:
                kw: dict[str, Any] = dict(
                    use_angle_cls=True,
                    lang="en",
                    use_gpu=self._cuda,
                    show_log=False,
                )
                self.paddle = PaddleOCR(**kw)
                self._log("PaddleOCR ready")
            except Exception as e:
                self._log(f"PaddleOCR failed ({e}), trying EasyOCR")
                self.paddle = None

        if self.paddle is None and easyocr is not None:
            try:
                self.reader = easyocr.Reader(
                    ["en"], gpu=self._cuda, verbose=False
                )
                self._log("EasyOCR ready (fallback)")
            except Exception as e:
                self._log(f"EasyOCR failed: {e}")
                self.reader = None

    def load_image_rgb(self, path: str | Path) -> np.ndarray:
        p = Path(path)
        if TurboJPEG is not None and p.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".jpe",
        ):
            try:
                jpeg = TurboJPEG()
                with open(p, "rb") as f:
                    buf = f.read()
                img = jpeg.decode(buf, pixel_format=TJPF_RGB)
                if img is not None:
                    return img
            except Exception:
                pass
        im = cv2.imread(str(p))
        if im is None:
            raise ValueError(f"Cannot read image: {path}")
        return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)

    def load_image_bgr(self, path: str | Path) -> np.ndarray:
        rgb = self.load_image_rgb(path)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def process_photo(
        self,
        image_path: str | Path,
        photo_stem: str | None = None,
        cancel_check: Optional[CancelCheck] = None,
    ) -> list[dict]:
        path = Path(image_path)
        img_rgb = self.load_image_rgb(path)
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        orig_h, orig_w = img_rgb.shape[:2]
        stem = (photo_stem or path.stem).strip() or "photo"

        def cancelled() -> bool:
            return bool(cancel_check and cancel_check())

        self._emit_progress(
            {
                "type": "photo_start",
                "path": str(path),
                "stem": stem,
                "width": orig_w,
                "height": orig_h,
            }
        )

        use_tiling = orig_w > self.config.tiling_threshold_w
        if not use_tiling:
            if cancelled():
                return []
            det_rgb = img_rgb
            scale = 1.0
            dw, dh = orig_w, orig_h
            self._log(f"Single pass detection {dw}×{dh}")
            boxes = self._detect_on_image(
                det_rgb, dw, dh, 0, 0, scale, orig_w, orig_h
            )
        else:
            tiles = generate_tiles(
                orig_w, orig_h, self.config.tile_size, self.config.overlap
            )
            n = len(tiles)
            self._log(f"Tiling: {n} tile(s) for {orig_w}×{orig_h}")
            all_boxes: list[tuple] = []
            for i, (x0, y0, x2, y2) in enumerate(tiles):
                if cancelled():
                    self._emit_progress({"type": "cancelled_mid", "phase": "tiles"})
                    return []
                self._emit_progress(
                    {
                        "type": "tile_progress",
                        "current": i + 1,
                        "total": n,
                        "path": str(path),
                    }
                )
                self._log(f"Tile {i + 1} of {n}…")
                tile_bgr = img_bgr[y0:y2, x0:x2]
                if tile_bgr.size == 0:
                    continue
                tile_rgb = cv2.cvtColor(tile_bgr, cv2.COLOR_BGR2RGB)
                tw, th = x2 - x0, y2 - y0
                local = self._detect_on_image(
                    tile_rgb, tw, th, x0, y0, 1.0, orig_w, orig_h
                )
                all_boxes.extend(local)
            boxes = all_boxes

        if cancelled():
            return []

        merged = _nms(boxes, self.config.nms_iou_global)
        merged.sort(key=lambda b: b[4], reverse=True)
        merged = merged[: self.config.max_tags]
        self._log(f"After NMS: {len(merged)} candidate(s)")
        self._emit_progress(
            {"type": "detection_done", "count": len(merged), "path": str(path)}
        )

        tags: list[dict] = []
        n_merged = len(merged)
        for idx, (x1, y1, x2, y2, det_conf) in enumerate(merged):
            if cancelled():
                self._emit_progress({"type": "cancelled_mid", "phase": "ocr"})
                return []
            self._emit_progress(
                {
                    "type": "ocr_progress",
                    "current": idx + 1,
                    "total": n_merged,
                    "path": str(path),
                }
            )
            text, ocr_conf = self._ocr_crop(img_bgr, x1, y1, x2, y2)
            if not text.strip():
                text = "UNKNOWN"
            corners = box_to_corners_pan_tilt(
                x1, y1, x2, y2, float(orig_w), float(orig_h)
            )
            blend = float(det_conf) * 0.5 + float(ocr_conf) * 0.5
            tags.append(
                {
                    "photo": stem,
                    "tag_id": 0,
                    "tag_name": text,
                    "system_text": text,
                    "ocr_conf": round(ocr_conf, 4),
                    "conf": round(blend, 3),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    **corners,
                }
            )
        for j, t in enumerate(tags):
            t["tag_id"] = j + 1
        self._emit_progress(
            {
                "type": "photo_complete",
                "path": str(path),
                "tag_count": len(tags),
            }
        )
        return tags

    def _detect_on_image(
        self,
        img_rgb: np.ndarray,
        w: int,
        h: int,
        off_x: int,
        off_y: int,
        scale_to_orig: float,
        orig_w: int,
        orig_h: int,
    ) -> list[tuple[float, float, float, float, float]]:
        """Return boxes in ORIGINAL image coordinates."""
        boxes: list[tuple] = []
        if self.yolo is not None:
            img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
            try:
                pred_kw: dict[str, Any] = dict(
                    verbose=False,
                    conf=self.config.yolo_conf,
                    device=self._device,
                    imgsz=min(w, self.config.yolo_imgsz),
                )
                if self._cuda and self.config.use_fp16:
                    pred_kw["half"] = True
                r = self.yolo(img_bgr, **pred_kw)
                for res in r:
                    for box in res.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        cf = float(box.conf[0])
                        bw, bh = x2 - x1, y2 - y1
                        if (
                            bw > 8
                            and bh > 5
                            and 0.05 < bw / max(bh, 1) < 30
                        ):
                            ox1 = (off_x + x1) / scale_to_orig
                            oy1 = (off_y + y1) / scale_to_orig
                            ox2 = (off_x + x2) / scale_to_orig
                            oy2 = (off_y + y2) / scale_to_orig
                            boxes.append(
                                (
                                    max(0, ox1),
                                    max(0, oy1),
                                    min(orig_w - 1, ox2),
                                    min(orig_h - 1, oy2),
                                    cf,
                                )
                            )
            except Exception as e:
                self._log(f"YOLO inference error: {e}")

        if self.paddle is not None:
            try:
                pr = self.paddle.ocr(img_rgb, cls=True)
                for line in self._paddle_to_boxes(pr, 0.15):
                    x1, y1, x2, y2, cf = line
                    pad_x = max(8, int((x2 - x1) * 0.15))
                    pad_y = max(4, int((y2 - y1) * 0.25))
                    x1 = max(0, x1 - pad_x)
                    y1 = max(0, y1 - pad_y)
                    x2 = min(w, x2 + pad_x)
                    y2 = min(h, y2 + pad_y)
                    ox1 = (off_x + x1) / scale_to_orig
                    oy1 = (off_y + y1) / scale_to_orig
                    ox2 = (off_x + x2) / scale_to_orig
                    oy2 = (off_y + y2) / scale_to_orig
                    boxes.append(
                        (
                            max(0, ox1),
                            max(0, oy1),
                            min(orig_w - 1, ox2),
                            min(orig_h - 1, oy2),
                            cf,
                        )
                    )
            except Exception as e:
                self._log(f"Paddle tile OCR error: {e}")
        elif self.reader is not None:
            try:
                ocr_raw = self.reader.readtext(
                    img_rgb,
                    detail=1,
                    paragraph=False,
                    width_ths=0.9,
                    text_threshold=0.32,
                    low_text=0.22,
                )
                for item in ocr_raw:
                    if len(item) < 3:
                        continue
                    quad, _txt, cf = item[0], item[1], float(item[2])
                    xs = [float(p[0]) for p in quad]
                    ys = [float(p[1]) for p in quad]
                    x1, y1, x2, y2 = (
                        int(min(xs)),
                        int(min(ys)),
                        int(max(xs)),
                        int(max(ys)),
                    )
                    pad_x = max(8, int((x2 - x1) * 0.15))
                    pad_y = max(4, int((y2 - y1) * 0.25))
                    x1 = max(0, x1 - pad_x)
                    y1 = max(0, y1 - pad_y)
                    x2 = min(w, x2 + pad_x)
                    y2 = min(h, y2 + pad_y)
                    ox1 = (off_x + x1) / scale_to_orig
                    oy1 = (off_y + y1) / scale_to_orig
                    ox2 = (off_x + x2) / scale_to_orig
                    oy2 = (off_y + y2) / scale_to_orig
                    boxes.append(
                        (
                            max(0, ox1),
                            max(0, oy1),
                            min(orig_w - 1, ox2),
                            min(orig_h - 1, oy2),
                            cf,
                        )
                    )
            except Exception as e:
                self._log(f"EasyOCR scan error: {e}")

        if not boxes:
            boxes = self._mser_fallback(img_rgb, w, h, off_x, off_y, orig_w, orig_h)

        merged = _nms(boxes, self.config.nms_iou_tile)
        return merged

    @staticmethod
    def _paddle_to_boxes(
        ocr_result: Any, min_conf: float
    ) -> list[tuple[int, int, int, int, float]]:
        out: list[tuple[int, int, int, int, float]] = []
        if not ocr_result or ocr_result[0] is None:
            return out
        for item in ocr_result[0]:
            if not item or len(item) < 2:
                continue
            quad, tx = item[0], item[1]
            if not quad or not tx:
                continue
            text, conf = tx[0], float(tx[1])
            if conf < min_conf or not (text or "").strip():
                continue
            xs = [float(p[0]) for p in quad]
            ys = [float(p[1]) for p in quad]
            x1, y1, x2, y2 = (
                int(min(xs)),
                int(min(ys)),
                int(max(xs)),
                int(max(ys)),
            )
            out.append((x1, y1, x2, y2, conf))
        return out

    def _mser_fallback(
        self,
        img_rgb: np.ndarray,
        w: int,
        h: int,
        off_x: int,
        off_y: int,
        orig_w: int,
        orig_h: int,
    ) -> list[tuple]:
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        mser = cv2.MSER_create()
        regions, _ = mser.detectRegions(gray)
        boxes: list[tuple] = []
        for pts in regions:
            x, y, bw, bh = cv2.boundingRect(pts.reshape(-1, 1, 2))
            if bw < 20 or bh < 8 or bw > w * 0.4 or bh > h * 0.4:
                continue
            if 0.3 < bw / max(bh, 1) < 20:
                ox1 = off_x + x
                oy1 = off_y + y
                ox2 = off_x + x + bw
                oy2 = off_y + y + bh
                boxes.append(
                    (
                        max(0, ox1),
                        max(0, oy1),
                        min(orig_w - 1, ox2),
                        min(orig_h - 1, oy2),
                        0.25,
                    )
                )
        return boxes[: self.config.max_tags]

    def _ocr_crop(
        self, img_bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int
    ) -> tuple[str, float]:
        crop = img_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return "UNKNOWN", 0.0
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        ch, cw = crop.shape[:2]
        if cw > self.config.ocr_max_width:
            s = self.config.ocr_max_width / cw
            crop = cv2.resize(
                crop,
                (self.config.ocr_max_width, max(1, int(ch * s))),
                interpolation=cv2.INTER_AREA,
            )
        elif cw < 80:
            f = max(2, 160 // cw)
            crop = cv2.resize(
                crop,
                (cw * f, ch * f),
                interpolation=cv2.INTER_CUBIC,
            )
        k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        crop = cv2.filter2D(crop, -1, k)

        if self.paddle is not None:
            try:
                pr = self.paddle.ocr(crop, cls=True)
                if not pr or pr[0] is None:
                    return "UNKNOWN", 0.0
                best = ("", 0.0)
                for item in pr[0]:
                    if not item or len(item) < 2:
                        continue
                    _q, tx = item[0], item[1]
                    if not tx:
                        continue
                    text, conf = str(tx[0]), float(tx[1])
                    if conf > best[1]:
                        best = (text.strip(), conf)
                return best[0] or "UNKNOWN", best[1]
            except Exception as e:
                logger.debug("Paddle OCR crop: %s", e)

        if self.reader is not None:
            try:
                res = self.reader.readtext(
                    crop,
                    detail=1,
                    paragraph=False,
                    text_threshold=0.35,
                    low_text=0.22,
                    width_ths=0.9,
                )
                if not res:
                    return "UNKNOWN", 0.0
                best = max(res, key=lambda r: r[2])
                return best[1].strip(), float(best[2])
            except Exception as e:
                logger.debug("EasyOCR crop: %s", e)
        return "UNKNOWN", 0.0
