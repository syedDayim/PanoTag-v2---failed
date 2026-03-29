# PanoTag — 360° Automatic Tag Extractor

Automatically detects physical equipment tags in 360° panoramic photos,
reads their text via OCR, and exports pan/tilt coordinates to Excel.

---

## Quick Start

### 1. Install Python 3.10+
Download from https://python.org if not already installed.

### 2. Install dependencies
Open a terminal in this folder and run:

```bash
pip install -r requirements.txt
```

> First run downloads ~200 MB of AI model weights automatically.
> YOLOv8 nano model (~6 MB) + EasyOCR English model (~200 MB).

### 3. Run the app (desktop)

From the **parent folder** of `panotag` (e.g. your project root):

```bash
python -m panotag
```

From inside the `panotag` folder:

```bash
python app.py
```

Open a photo via **Load photo**, or pass a path:

```bash
python app.py path/to/your/photo.jpg
```

---

## How it works

1. **Load photo** — click "LOAD PHOTO", select your 360° equirectangular JPG/PNG
2. **AI detects** — YOLOv8 finds rectangular label regions; EasyOCR reads the text
3. **Coordinates computed** — each bounding box corner is converted to pan/tilt angles
4. **Review** — annotated image shows all detected tags with colour-coded corners
5. **Export** — click "EXPORT EXCEL" to save the formatted spreadsheet

---

## Output Excel columns

| Column      | Description                              |
|-------------|------------------------------------------|
| Photo Name  | Filename of the source image             |
| Tag Name    | Text read from the label by OCR          |
| Pan (TL)    | Pan angle of top-left corner (degrees)   |
| Tilt (TL)   | Tilt angle of top-left corner (degrees)  |
| Pan (TR)    | Pan angle of top-right corner            |
| Tilt (TR)   | Tilt angle of top-right corner           |
| Pan (BR)    | Pan angle of bottom-right corner         |
| Tilt (BR)   | Tilt angle of bottom-right corner        |
| Pan (BL)    | Pan angle of bottom-left corner          |
| Tilt (BL)   | Tilt angle of bottom-left corner         |
| Confidence  | AI detection confidence (0–1)            |

---

## Corner colour coding

| Corner | Colour |
|--------|--------|
| TL     | Cyan   |
| TR     | Orange |
| BR     | Red    |
| BL     | Green  |

---

## Pan / Tilt formula

For an equirectangular image of width W and height H:

```
pan  = (x / W) × 360 − 180     → range: −180° to +180°
tilt = 90 − (y / H) × 180      → range: +90° (top) to −90° (bottom)
```

---

## Accuracy notes

- **High confidence (>0.7):** Tag shown in cyan — reliable
- **Medium confidence (0.4–0.7):** Tag shown in orange — review recommended
- **Low confidence (<0.4):** Tag shown in red — likely needs manual correction

For better accuracy on your specific tag styles, fine-tune YOLOv8 on
~50–100 annotated examples from your own photos. See:
https://docs.ultralytics.com/modes/train/

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| No tags detected | Tags may be too small or blurry; try a higher-res photo |
| Wrong tag names | OCR works best on clear, horizontal text |
| Slow first run | EasyOCR downloads models on first use — normal |
