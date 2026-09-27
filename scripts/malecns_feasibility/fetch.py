#!/usr/bin/env python3
"""Fetch the three MaleCNS v1.0 tables used by this check into .cache only."""
from __future__ import annotations

import argparse
import urllib.request

from common import CACHE, DOWNLOADS, SHA256, sha256

MAX_BYTES = 20_000_000_000


def remote_size(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request) as response:
        return int(response.headers["Content-Length"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="download after the size check")
    args = parser.parse_args()
    sizes = {name: remote_size(url) for name, url in DOWNLOADS.items()}
    total = sum(sizes.values())
    print(f"planned bytes: {total:,}")
    for name, size in sizes.items():
        print(f"{size:>12,}  {name}")
    if total > MAX_BYTES:
        raise SystemExit("planned download exceeds 20 GB; stopped before downloading")
    if not args.download:
        return 0
    CACHE.mkdir(parents=True, exist_ok=True)
    for name, url in DOWNLOADS.items():
        target = CACHE / name
        if not target.is_file():
            temporary = target.with_suffix(target.suffix + ".part")
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(target)
        actual = sha256(target)
        if actual != SHA256[name]:
            raise SystemExit(f"checksum mismatch for {target}: {actual}")
        print(f"verified {target} ({target.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
