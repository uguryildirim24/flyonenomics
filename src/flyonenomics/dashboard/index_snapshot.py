"""Read a SQLite checkpoint plus committed WAL pages without creating SHM files.

SQLite's immutable mode omits the WAL, while ordinary read-only mode can create
sidecars. The dashboard uses a byte snapshot, verified against the documented WAL
checksums, then lets SQLite decode the database in memory. Format reference:
https://www.sqlite.org/fileformat2.html#walformat
"""
from __future__ import annotations

import struct
from pathlib import Path

from flyonenomics.io import read_bytes

# WP8 read-only picker mechanics; sizes and magic values are SQLite file format.
WAL_HEADER_BYTES = 32
WAL_FRAME_HEADER_BYTES = 24
SQLITE_HEADER_BYTES = 100
UINT32_MASK = 0xFFFFFFFF
SNAPSHOT_ATTEMPTS = 3
MAX_INDEX_BYTES = 64 * 1024 * 1024


def _stamp(path: Path) -> tuple[int, int, int] | None:
    try:
        stat = path.stat()
        return stat.st_ino, stat.st_size, stat.st_mtime_ns
    except FileNotFoundError:
        return None


def _checksum(data: bytes, endian: str, initial: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """SQLite cumulative checksum; unsigned 32-bit words in the header's byte order."""
    first, second = initial
    for left, right in struct.iter_unpack(endian + "II", data):
        first = (first + left + second) & UINT32_MASK
        second = (second + right + first) & UINT32_MASK
    return first, second


def _overlay(database: bytes, wal: bytes) -> bytes:
    """Apply only complete committed WAL transactions to the byte snapshot."""
    if len(database) < SQLITE_HEADER_BYTES or database[:16] != b"SQLite format 3\0":
        raise ValueError("Invalid SQLite header")
    page_size = int.from_bytes(database[16:18], "big")
    page_size = 65536 if page_size == 1 else page_size
    if page_size < 512 or page_size > 65536 or page_size & (page_size - 1):
        raise ValueError("Invalid SQLite page size")
    output = bytearray(database)
    if len(wal) >= WAL_HEADER_BYTES:
        magic, version, size, _, salt1, salt2, c1, c2 = struct.unpack(">8I", wal[:WAL_HEADER_BYTES])
        if magic not in (0x377F0682, 0x377F0683) or version != 3007000 or size != page_size:
            raise ValueError("Invalid WAL header")
        endian = "<" if magic == 0x377F0682 else ">"
        checksum = _checksum(wal[:24], endian)
        if checksum != (c1, c2):
            raise ValueError("Invalid WAL checksum")
        pending: dict[int, bytes] = {}
        width = WAL_FRAME_HEADER_BYTES + page_size
        for offset in range(WAL_HEADER_BYTES, len(wal) - width + 1, width):
            header = wal[offset:offset + WAL_FRAME_HEADER_BYTES]
            page, committed_size, s1, s2, c1, c2 = struct.unpack(">6I", header)
            content = wal[offset + WAL_FRAME_HEADER_BYTES:offset + width]
            checksum = _checksum(header[:8] + content, endian, checksum)
            if (s1, s2) != (salt1, salt2) or checksum != (c1, c2):
                break  # Stale frames after a WAL reset, or a torn final write.
            if page == 0 or page * page_size > MAX_INDEX_BYTES:
                raise ValueError("Invalid or oversized WAL page")
            pending[page] = content
            if committed_size:
                if committed_size * page_size > MAX_INDEX_BYTES:
                    raise ValueError("Oversized index snapshot")
                desired = committed_size * page_size
                if len(output) < desired:
                    output.extend(b"\0" * (desired - len(output)))
                del output[desired:]
                for number, data in pending.items():
                    if number <= committed_size:
                        output[(number - 1) * page_size:number * page_size] = data
                pending.clear()
    # The isolated in-memory copy has no WAL. The source header is untouched.
    output[18:20] = b"\x01\x01"
    return bytes(output)


def sqlite_snapshot(database: Path, wal: Path) -> bytes:
    """Read a stable checkpoint/WAL pair; units bytes, bounded in-memory result."""
    for _ in range(SNAPSHOT_ATTEMPTS):
        before = (_stamp(database), _stamp(wal))
        if any(stamp and stamp[1] > MAX_INDEX_BYTES for stamp in before):
            raise ValueError("Index exceeds dashboard snapshot limit")
        checkpoint = read_bytes(database)
        try:
            journal = read_bytes(wal)
        except FileNotFoundError:
            journal = b""
        if before == (_stamp(database), _stamp(wal)):
            return _overlay(checkpoint, journal)
    raise ValueError("Index changed during snapshot; use directory reconciliation")
