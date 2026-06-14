from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler


def configure_logging(log_path: Path | None = None, *, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("asub")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    console = RichHandler(rich_tracebacks=True, show_time=False)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)
    return logger
