from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from importlib.metadata import Distribution, PackageNotFoundError
from pathlib import Path

from envstamp.fingerprint import DistributionFingerprint, _distribution


@dataclass(frozen=True, slots=True)
class Stamp:
    packages: tuple[DistributionFingerprint, ...]

    def __post_init__(self) -> None:
        names = tuple(package.canonical_name.lower() for package in self.packages)
        if names != tuple(sorted(names)):
            raise ValueError("stamp packages must be sorted by canonical name")


def get_stamp(names: list[str], *, site_packages: str) -> Stamp:
    """Fingerprint installed distributions in canonical-name order."""
    if not names:
        raise ValueError("distribution names must not be empty")

    packages: list[DistributionFingerprint] = []
    for name in names:
        if not name:
            raise ValueError("distribution name must not be empty")

        installed = next(
            Distribution.discover(name=name, path=[site_packages]),
            None,
        )
        if installed is None:
            raise PackageNotFoundError(name)

        packages.append(_distribution(installed))

    packages.sort(key=lambda package: package.canonical_name.lower())
    return Stamp(packages=tuple(packages))


def read_stamp(path: str | Path) -> Stamp:
    """Read one stamp from a file."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("stamp must be a JSON object")

    packages = tuple(
        DistributionFingerprint(**package) for package in value["packages"]
    )
    return Stamp(packages=packages)


def write_stamp(path: str | Path, stamp: Stamp) -> None:
    """Atomically replace a single-writer stamp file."""
    stamp_path = Path(path)
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = stamp_path.with_name(f".{stamp_path.name}.tmp")
    with temporary_path.open("w", encoding="utf-8") as temporary_file:
        json.dump(
            asdict(stamp),
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
    os.replace(temporary_path, stamp_path)
