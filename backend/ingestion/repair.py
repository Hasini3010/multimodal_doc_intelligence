"""PDF repair via pikepdf; graceful failure for damaged files."""

from __future__ import annotations

import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)


def repair_pdf(source: Path, cache_dir: Path | None = None) -> tuple[Path, bool, str | None]:
    """
    Attempt to repair PDF. Returns (path_to_open, repaired_flag, error_message).
    Skips pikepdf when PyMuPDF already opens the file (avoids Windows temp rename issues).
    """
    open_err: str | None = None
    try:
        doc = pymupdf.open(source)
        doc.close()
        return source, False, None
    except Exception as exc:
        open_err = str(exc)
        logger.debug("PyMuPDF open failed for %s: %s", source.name, exc)

    try:
        import pikepdf
    except ImportError:
        logger.warning("pikepdf not installed; skipping repair")
        return source, False, open_err

    cache_dir = cache_dir or (source.parent / ".repair_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{source.stem}_repaired.pdf"

    try:
        with pikepdf.open(source, allow_overwriting_input=False) as pdf:
            pdf.save(out_path)
        return out_path, True, None
    except Exception as exc:
        logger.warning("pikepdf repair failed for %s: %s", source.name, exc)
        return source, False, str(exc)
