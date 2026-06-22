"""Clean intermediate artifacts from ppt-work while keeping PPTX comparison versions."""

from __future__ import annotations

import shutil
from pathlib import Path

# Current output + archived versioned decks for side-by-side review.
_KEEP_PPTX_NAMES = frozenset(
    {
        "mental_health_classroom.pptx",
        "mental_health_classroom_V1.pptx",
        "mental_health_classroom_V2.pptx",
        "mental_health_classroom_V3_v3.pptx",
        "mental_health_classroom_V3_v4.pptx",
    }
)

_INTERMEDIATE_SUFFIXES = frozenset({".json", ".md", ".py"})
_SCRATCH_PREFIX = "_"
_OFFICE_LOCK_PREFIX = "~$"


def is_kept_pptx(name: str) -> bool:
    """Return True if a PPTX filename should be preserved for comparison."""
    if name in _KEEP_PPTX_NAMES:
        return True
    if name.startswith("mental_health_classroom_V") and name.endswith(".pptx"):
        return True
    return name == "mental_health_classroom.pptx"


def cleanup_ppt_work_dir(out_dir: Path) -> list[str]:
    """Remove intermediate build artifacts; keep versioned PPTX outputs."""
    out_dir = out_dir.expanduser().resolve()
    if not out_dir.is_dir():
        return []

    removed: list[str] = []
    for path in sorted(out_dir.iterdir()):
        name = path.name
        if name.startswith(_OFFICE_LOCK_PREFIX):
            continue

        if path.is_dir():
            if name == "exports":
                shutil.rmtree(path, ignore_errors=True)
                removed.append(f"{name}/")
            continue

        suffix = path.suffix.lower()
        if suffix == ".pptx":
            if is_kept_pptx(name):
                continue
            path.unlink(missing_ok=True)
            removed.append(name)
            continue

        if suffix in _INTERMEDIATE_SUFFIXES or name.startswith(_SCRATCH_PREFIX):
            path.unlink(missing_ok=True)
            removed.append(name)

    return removed
