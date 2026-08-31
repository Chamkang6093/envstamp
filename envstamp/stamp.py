from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def read_stamp(path: str | Path) -> dict[str, Any]:
    """Read one stamp from a file."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("stamp must be a JSON object")
    return dict(value)


def write_stamp(path: str | Path, stamp: Mapping[str, Any]) -> None:
    """Atomically replace a single-writer stamp file."""
    stamp_path = Path(path)
    stamp_path.parent.mkdir(parents=True, exist_ok=True)

    _write_stamp(stamp_path, dict(stamp))


def _write_stamp(path: Path, stamp: dict[str, Any]) -> None:
    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open("w", encoding="utf-8") as temporary_file:
        json.dump(
            stamp,
            temporary_file,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        temporary_file.write("\n")
        temporary_file.flush()
        os.fsync(temporary_file.fileno())

    # Atomic on POSIX when both paths are on the same filesystem.
    os.replace(temporary_path, path)
