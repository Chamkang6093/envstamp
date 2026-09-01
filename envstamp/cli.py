from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from envstamp.stamp import get_stamp, read_stamp, write_stamp


def main() -> None:
    parser = _build_parser()
    arguments = parser.parse_args()

    if arguments.command == "get":
        metadata: dict[str, str] = {}
        for item in arguments.metadata:
            key, separator, value = item.partition("=")
            if not separator:
                parser.error("metadata must use KEY=VALUE")
            if key in metadata:
                parser.error(f"metadata key must not repeat: {key}")
            metadata[key] = value

        stamp = get_stamp(
            arguments.packages,
            paths=arguments.paths,
            metadata=metadata,
        )
        if arguments.output is not None:
            write_stamp(arguments.output, stamp)
            return
    elif arguments.command == "read":
        stamp = read_stamp(arguments.file)
    else:
        raise AssertionError(f"unknown command: {arguments.command!r}")

    print(
        json.dumps(
            asdict(stamp),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="envstamp",
        description="Write atomic fingerprints of installed Python distributions.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    get_parser = commands.add_parser(
        "get",
        help="get a stamp of installed distributions",
    )
    get_parser.add_argument("packages", nargs="+")
    get_parser.add_argument(
        "--paths",
        nargs="+",
        default=sys.path,
        help="distribution search paths; defaults to the current sys.path",
    )
    get_parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="add string metadata; may be repeated",
    )
    get_parser.add_argument(
        "--output",
        type=Path,
        help="atomically write the stamp to this path",
    )
    read_parser = commands.add_parser("read", help="read one stamp")
    read_parser.add_argument("file", type=Path)

    return parser
