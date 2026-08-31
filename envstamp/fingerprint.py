from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.metadata import Distribution, PackagePath
from importlib.metadata import distribution as find_distribution
from pathlib import Path, PurePosixPath

FINGERPRINT_ALGORITHM = "envstamp-sha256-v1"


class FingerprintError(RuntimeError):
    """Raised when an installed distribution cannot be fingerprinted reliably."""


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class DistributionFingerprint:
    name: str
    version: str
    algorithm: str
    sha256: str
    files: tuple[FileFingerprint, ...]


def distribution(name: str) -> DistributionFingerprint:
    """Fingerprint the stable installed payload of a Python distribution."""
    if not name:
        raise ValueError("distribution name must not be empty")

    installed = find_distribution(name)
    distribution_name = installed.metadata["Name"]
    if distribution_name is None:
        raise FingerprintError(f"distribution {name!r} has no canonical name")

    manifest = installed.files
    if manifest is None:
        raise FingerprintError(f"distribution {name!r} has no installed file manifest")

    files: list[FileFingerprint] = []

    for manifest_file in manifest:
        file_fingerprint = _manifest_file(installed, manifest_file)
        if file_fingerprint is not None:
            files.append(file_fingerprint)

    files.sort(key=lambda file: file.path)
    if not files:
        raise FingerprintError(f"distribution {name!r} has no stable installed files")

    return DistributionFingerprint(
        name=distribution_name,
        version=installed.version,
        algorithm=FINGERPRINT_ALGORITHM,
        sha256=_sha256_package(files),
        files=tuple(files),
    )


def _manifest_file(installed: Distribution, manifest_file: PackagePath) -> FileFingerprint | None:
    # NOTE: RECORD hashes are optional; hash the installed file directly.
    # if manifest_file.hash is None:
    #     return None

    manifest_path = PurePosixPath(manifest_file)
    if not _is_stable_manifest_path(manifest_path):
        return None

    installed_path = Path(installed.locate_file(manifest_file)).resolve()
    distribution_root = Path(installed.locate_file("")).resolve()
    if not installed_path.is_relative_to(distribution_root):
        return None
    if not installed_path.is_file():
        raise FingerprintError(f"installed file is missing: {manifest_path}")

    sha256, size = _sha256_file(installed_path, chunk_size=1024 * 1024)
    return FileFingerprint(path=manifest_path.as_posix(), sha256=sha256, size=size)


def _is_stable_manifest_path(manifest_path: PurePosixPath) -> bool:
    lowered_parts = tuple(part.lower() for part in manifest_path.parts)
    if "__pycache__" in lowered_parts:
        return False
    if any(part.endswith((".dist-info", ".egg-info")) for part in lowered_parts):
        return False
    return manifest_path.suffix.lower() not in {".egg-link", ".pth", ".pyc", ".pyo"}


def _sha256_file(path: Path, *, chunk_size: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0

    with path.open("rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)

    return digest.hexdigest(), size


def _sha256_package(files: list[FileFingerprint]) -> str:
    """Hash the protocol tag and sorted ``path\\0sha256\\0size\\n`` records."""
    digest = hashlib.sha256()
    digest.update(FINGERPRINT_ALGORITHM.encode("ascii"))
    digest.update(b"\0")
    for file in files:
        digest.update(file.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file.sha256.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(file.size).encode("ascii"))
        digest.update(b"\n")

    return digest.hexdigest()
