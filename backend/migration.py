"""Safely preserve existing preferences when the desktop application is renamed."""

from pathlib import Path
import shutil


def preferred_settings_path(current: Path, previous: Path) -> Path:
    """Copy previous non-secret settings once, or use the old path on IO failure."""
    if current.is_file() or not previous.is_file():
        return current
    try:
        current.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(previous, current)
        return current
    except OSError:
        # Non-destructive fallback: don't prevent the app from starting.
        return previous
