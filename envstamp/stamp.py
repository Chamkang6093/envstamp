from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from importlib.metadata import Distribution, PackageNotFoundError
from pathlib import Path

from envstamp.fingerprint import (
    DistributionFingerprint,
    FingerprintError,
    _distribution,
)


@dataclass(frozen=True, slots=True)
class Stamp:
    packages: tuple[DistributionFingerprint, ...]
    metadata: dict[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in self.metadata.items()
        ):
            raise TypeError("stamp metadata must contain string keys and values")

        metadata_keys = tuple(self.metadata)
        if metadata_keys != tuple(sorted(metadata_keys)):
            raise ValueError("stamp metadata must be sorted by key")

        names = tuple(package.canonical_name.lower() for package in self.packages)
        if names != tuple(sorted(names)):
            raise ValueError("stamp packages must be sorted by canonical name")


def get_stamp(names: list[str], *, paths: list[str], metadata: dict[str, str]) -> Stamp:
    """Return a stable stamp from two matching fingerprints."""
    first = _get_stamp(names, paths, metadata)
    second = _get_stamp(names, paths, metadata)
    if first != second:
        raise FingerprintError("installed distributions changed while fingerprinting")

    return second


def _get_stamp(names: list[str], paths: list[str], metadata: dict[str, str]) -> Stamp:
    """Fingerprint distributions on import paths in canonical-name order."""
    if not names:
        raise ValueError("distribution names must not be empty")

    packages: list[DistributionFingerprint] = []
    for name in names:
        if not name:
            raise ValueError("distribution name must not be empty")

        installed = next(
            iter(Distribution.discover(name=name, path=paths)),
            None,
        )
        if installed is None:
            raise PackageNotFoundError(name)

        packages.append(_distribution(installed))

    packages.sort(key=lambda package: package.canonical_name.lower())
    metadata = dict(sorted(metadata.items(), key=lambda item: item[0]))
    return Stamp(packages=tuple(packages), metadata=metadata)


def read_stamp(file: str | Path) -> Stamp:
    """Read one stamp from a file."""
    value = json.loads(Path(file).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("stamp must be a JSON object")

    packages = tuple(
        DistributionFingerprint(**package) for package in value["packages"]
    )
    return Stamp(packages=packages, metadata=value["metadata"])


def write_stamp(path: str | Path, stamp: Stamp) -> None:
    """Atomically replace a single-writer stamp file."""
    stamp_path = Path(path)
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.parent.chmod(0o755)
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
        os.fchmod(temporary_file.fileno(), 0o444)

    # Atomic on POSIX when both paths are on the same filesystem.
    os.replace(temporary_path, stamp_path)
