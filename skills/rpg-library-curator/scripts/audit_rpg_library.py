#!/usr/bin/env python3
"""Read-only inventory and exact-duplicate detector for RPG library roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SYSTEM_FILE_NAMES = {".DS_Store"}


def is_system_file(relative_path: Path) -> bool:
    return any(
        part in SYSTEM_FILE_NAMES or part.startswith("._")
        for part in relative_path.parts
    )


def extension_for(path: Path) -> str:
    return path.suffix.lower() if path.suffix else "[no extension]"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_root(root: Path, include_system: bool) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    excluded_system_files = 0

    for directory, child_directories, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        child_directories[:] = [
            name for name in child_directories if not (directory_path / name).is_symlink()
        ]

        for filename in filenames:
            path = directory_path / filename
            if path.is_symlink():
                continue

            relative_path = path.relative_to(root)
            if not include_system and is_system_file(relative_path):
                excluded_system_files += 1
                continue

            try:
                size = path.stat().st_size
            except OSError as error:
                print(f"warning: cannot stat {path}: {error}", file=sys.stderr)
                continue

            records.append(
                {
                    "root": str(root),
                    "relative_path": str(relative_path),
                    "path": str(path),
                    "size_bytes": size,
                    "extension": extension_for(path),
                }
            )

    return records, excluded_system_files


def duplicate_groups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records_by_size: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["size_bytes"] > 0:
            records_by_size[record["size_bytes"]].append(record)

    groups: list[dict[str, Any]] = []
    for size, size_matches in sorted(records_by_size.items()):
        if len(size_matches) < 2:
            continue

        records_by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in size_matches:
            try:
                digest = file_hash(Path(record["path"]))
            except OSError as error:
                print(f"warning: cannot hash {record['path']}: {error}", file=sys.stderr)
                continue
            records_by_hash[digest].append(record)

        for digest, hash_matches in sorted(records_by_hash.items()):
            if len(hash_matches) > 1:
                groups.append(
                    {
                        "sha256": digest,
                        "size_bytes": size,
                        "files": sorted(hash_matches, key=lambda item: item["path"]),
                    }
                )

    return groups


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only inventory for one or more RPG library roots."
    )
    parser.add_argument(
        "--root",
        action="append",
        required=True,
        help="Root directory to inventory. Repeat for library and intake roots.",
    )
    parser.add_argument(
        "--hash-duplicates",
        action="store_true",
        help="Hash same-size files to report exact duplicate groups.",
    )
    parser.add_argument(
        "--include-files",
        action="store_true",
        help="Include every file record in the JSON output.",
    )
    parser.add_argument(
        "--include-system-files",
        action="store_true",
        help="Include .DS_Store and AppleDouble metadata files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    all_records: list[dict[str, Any]] = []
    root_summaries: list[dict[str, Any]] = []

    for value in args.root:
        root = Path(value).expanduser().resolve()
        if not root.is_dir():
            print(f"error: root is not a directory: {root}", file=sys.stderr)
            return 2

        records, excluded_system_files = collect_root(root, args.include_system_files)
        extensions = Counter(record["extension"] for record in records)
        root_summaries.append(
            {
                "path": str(root),
                "file_count": len(records),
                "total_bytes": sum(record["size_bytes"] for record in records),
                "system_files_excluded": excluded_system_files,
                "extensions": dict(sorted(extensions.items())),
            }
        )
        all_records.extend(records)

    output: dict[str, Any] = {
        "roots": root_summaries,
        "total_files": len(all_records),
        "total_bytes": sum(record["size_bytes"] for record in all_records),
    }
    if args.hash_duplicates:
        output["exact_duplicate_groups"] = duplicate_groups(all_records)
    if args.include_files:
        output["files"] = sorted(all_records, key=lambda item: item["path"])

    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
