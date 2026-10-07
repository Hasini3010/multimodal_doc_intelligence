"""OCR abstraction with optional Tesseract backend."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OcrBlock:
    text: str
    confidence: float
    bbox_norm: tuple[float, float, float, float]  # x0,y0,x1,y1 in 0-1


def preprocess_for_ocr(image_path: Path) -> np.ndarray:
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    img = cv2.fastNlMeansDenoising(img, h=10)
    img = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return img


def _tesseract_available() -> bool:
    try:
        import pytesseract  # noqa: F401

        return True
    except ImportError:
        return False


def run_ocr(image_path: Path, *, page_width: float, page_height: float) -> list[OcrBlock]:
    """Run OCR; returns empty list if no engine available."""
    engines: list[str] = []
    blocks: list[OcrBlock] = []

    if _tesseract_available():
        engines.append("tesseract")
        blocks = _ocr_tesseract(image_path, page_width, page_height)
    else:
        logger.info("Tesseract/pytesseract unavailable; OCR skipped for %s", image_path.name)

    if blocks:
        return blocks

    # Second-engine fallback placeholder (PaddleOCR) — not installed by default
    return []


def _ocr_tesseract(
    image_path: Path, page_width: float, page_height: float
) -> list[OcrBlock]:
    import pytesseract
    from pytesseract import Output

    pre = preprocess_for_ocr(image_path)
    data = pytesseract.image_to_data(pre, output_type=Output.DICT)
    blocks: list[OcrBlock] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf = float(data["conf"][i])
        if conf < 0:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        x0, y0 = x / page_width, y / page_height
        x1, y1 = (x + w) / page_width, (y + h) / page_height
        blocks.append(
            OcrBlock(
                text=text,
                confidence=min(1.0, conf / 100.0),
                bbox_norm=(x0, y0, x1, y1),
            )
        )
    return blocks
