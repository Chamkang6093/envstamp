# envstamp

Atomic, reproducible fingerprints of installed Python distributions.

`envstamp` is a small stdlib-only package for recording installed package versions and content
fingerprints in an atomic JSON stamp.

## Installation

```bash
pip install envstamp
```

`envstamp` requires Python 3.12 or newer.

## CLI

Get a stamp for one or more installed distributions and print it:

```bash
envstamp get numpy pandas
```

Search explicit distribution paths:

```bash
envstamp get numpy pandas --paths /path/to/site-packages
```

Attach string metadata by repeating `--metadata`:

```bash
envstamp get numpy pandas \
    --metadata service=worker \
    --metadata environment=production
```

Every stamp contains a metadata object, which may be empty. Its keys and values are strings, keys
are stored in sorted order, and repeated CLI keys are rejected.

Atomically write the stamp to a file:

```bash
envstamp get numpy pandas --output /tmp/envstamp.json
```

Read the saved stamp:

```bash
envstamp read /tmp/envstamp.json
```

Each package record contains its canonical name, installed version, fingerprint algorithm,
package-level SHA-256, and the number of files included in that digest. Package records are sorted
by canonical name.

## Python API

```python
import sys

from envstamp.stamp import get_stamp, read_stamp, write_stamp


stamp = get_stamp(
    ["numpy", "pandas"],
    paths=sys.path,
    metadata={"service": "worker", "environment": "production"},
)
write_stamp("/tmp/envstamp.json", stamp)

saved = read_stamp("/tmp/envstamp.json")
for package in saved.packages:
    print(package.canonical_name, package.version, package.sha256)
```

Pass the distribution search paths explicitly through `get_stamp(..., paths=...)`.
Metadata does not participate in package content hashes.

`envstamp` supports regular, non-editable installations. It reads
`.dist-info/direct_url.json` when present and rejects the distribution when
`dir_info.editable` is `true`, because that metadata points at a mutable source tree rather than a
stable installed payload.

## Fingerprint protocol

The `envstamp-sha256-v1` algorithm starts from each installed distribution manifest, but only
includes entries that resolve inside its installation root, normally `site-packages`. This covers
Python code, native libraries such as `.so` and `.pyd`, and package data. Distribution metadata,
bytecode caches, `.pth` and `.egg-link` path files, launch scripts, and external data are excluded.

RECORD hashes are not used as an inclusion filter. When an included entry has no RECORD hash,
`envstamp` still reads and hashes the installed file directly. If that file is missing,
fingerprinting fails instead of silently producing a partial digest.

File paths are sorted before the package digest hashes the protocol tag followed by
`path\0sha256\0size\n` records. The read buffer size does not affect the resulting digest.

`get_stamp()` fingerprints the complete package set twice and only returns when both results are
identical. If the installed environment changes while the stamp is being generated, it raises
`FingerprintError` instead of returning a mixed snapshot.

## Atomic writes

Each stamp file belongs to one writer and contains one complete stamp. A write creates a
same-directory temporary file, flushes it, and atomically replaces the previous stamp file.
On POSIX, readers therefore observe either the previous complete stamp or the new complete stamp.
Concurrent writers to the same path are not supported; use a separate file for each process.
