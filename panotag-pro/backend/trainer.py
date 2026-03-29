"""PaddleOCR fine-tuning pipeline — stub for active learning (Section 5)."""
from __future__ import annotations


def export_training_dataset(project_corrections_dir: str) -> int:
    """Placeholder: export corrections in Paddle train format."""
    return 0


def retrain_paddleocr(_dataset_path: str) -> str | None:
    """Placeholder: run fine-tune; return new model version string."""
    return None
