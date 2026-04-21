"""
core/fpd.py — FPD (.bin) package parser and extractor
Format: FPD\x00 magic, big-endian header, XOR+zlib entry table

Based on reverse-engineering of FSN Remastered's package format.
Credit: DaZombieKiller/FatePackageManager, kurikomoe/FSNr_tools
"""

import io
import os
import zlib
import struct
import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

HDR_SIZE = 56  # Fixed header size before the XOR'd entry block


class FPDEntry:
    """One file entry inside an FPD package."""

    def __init__(self, filepath_str_offset: int, offset: int, size: int, uncompressed_size: int):
        self.filepath_str_offset = filepath_str_offset
        self.offset = offset          # offset from start of data section
        self.size = size              # stored (compressed) size
        self.uncompressed_size = uncompressed_size  # 0 = not compressed
        self.filepath: Optional[str] = None  # filled in after string table decode

    def __repr__(self):
        return (f"FPDEntry({self.filepath!r}, offset=0x{self.offset:x}, "
                f"size=0x{self.size:x}, unc=0x{self.uncompressed_size:x})")


def _read_cstr(buf: io.BytesIO) -> str:
    """Read a null-terminated UTF-8 string from a BytesIO."""
    result = bytearray()
    while True:
        ch = buf.read(1)
        if not ch or ch == b'\x00':
            break
        result += ch
    return result.decode('utf-8', errors='replace')


def _xor_buf(data: bytearray, key: bytes) -> None:
    """XOR data in-place using a repeating key."""
    key_len = len(key)
    for i in range(len(data)):
        data[i] ^= key[i % key_len]


class FPDPackage:
    """
    Parses and extracts an FPD package file.

    Usage::

        pkg = FPDPackage.from_file("patch00m.bin", decrypt_key)
        pkg.extract_all("./output/")
        entries = pkg.get_entries_by_ext(".epk")
    """

    def __init__(self, file_path: str, decrypt_key: bytes):
        self.file_path = Path(file_path)
        self.key = decrypt_key
        self.entries: List[FPDEntry] = []
        self._raw_data: Optional[bytes] = None
        self._data_section_start: int = 0

        self._parse()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self):
        log.debug(f"Parsing FPD: {self.file_path}")
        with open(self.file_path, 'rb') as f:
            self._raw_data = f.read()

        cur = io.BytesIO(self._raw_data)

        # --- Header ---
        magic = cur.read(4)
        if magic != b'FPD\x00':
            raise ValueError(f"Not an FPD file (magic={magic!r}): {self.file_path}")

        self.version = int.from_bytes(cur.read(4), 'big')
        self.entry_count = int.from_bytes(cur.read(8), 'big')
        # entry_block_size includes the HDR_SIZE, so subtract it
        raw_entry_block_size = int.from_bytes(cur.read(8), 'big')
        entry_block_size = raw_entry_block_size - HDR_SIZE
        cur.seek(4 * 8, io.SEEK_CUR)  # skip 32 bytes of padding/other fields

        log.debug(f"  version={self.version}, entries={self.entry_count}, "
                  f"entry_block=0x{entry_block_size:x}")

        self._data_section_start = HDR_SIZE + entry_block_size

        # --- Entry block (XOR encrypted) ---
        raw_entry_block = bytearray(cur.read(entry_block_size))
        _xor_buf(raw_entry_block, self.key)

        # --- Parse entries (32 bytes each) ---
        entry_cur = io.BytesIO(raw_entry_block)
        for _ in range(self.entry_count):
            fso = int.from_bytes(entry_cur.read(8), 'big')
            offset = int.from_bytes(entry_cur.read(8), 'big')
            size = int.from_bytes(entry_cur.read(8), 'big')
            unc = int.from_bytes(entry_cur.read(8), 'big')
            self.entries.append(FPDEntry(fso, offset, size, unc))

        # --- String table (zlib compressed, follows entries) ---
        zlib_offset = entry_cur.tell()
        zlib_data = entry_cur.read(entry_block_size - zlib_offset)
        string_block = zlib.decompress(zlib_data)

        str_cur = io.BytesIO(string_block)
        for entry in self.entries:
            str_cur.seek(entry.filepath_str_offset)
            entry.filepath = _read_cstr(str_cur)

        log.debug(f"  Parsed {len(self.entries)} entries successfully")

    # ------------------------------------------------------------------
    # Data extraction
    # ------------------------------------------------------------------

    def read_entry(self, entry: FPDEntry) -> bytes:
        """Read and decompress/decrypt the data for a single entry."""
        data_offset = self._data_section_start + entry.offset
        raw = bytearray(self._raw_data[data_offset: data_offset + entry.size])
        _xor_buf(raw, self.key)
        if entry.uncompressed_size != 0:
            raw = bytearray(zlib.decompress(bytes(raw)))
        return bytes(raw)

    def extract_all(self, output_dir: str, verify_md5: bool = False) -> int:
        """
        Extract all entries to output_dir preserving path structure.
        Path separators '/' are replaced with '#' in filenames.
        Returns number of files extracted.
        """
        out = Path(output_dir) / self.file_path.name
        out.mkdir(parents=True, exist_ok=True)
        count = 0
        for entry in self.entries:
            data = self.read_entry(entry)
            # Replace path separators with '#' (original tool convention)
            fname = entry.filepath.replace('/', '#')
            dest = out / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            count += 1
            log.debug(f"  Extracted: {fname} ({len(data)} bytes)")
        return count

    def extract_entry(self, entry: FPDEntry, output_dir: str) -> Path:
        """Extract a single entry and return its output path."""
        data = self.read_entry(entry)
        out = Path(output_dir)
        fname = entry.filepath.replace('/', '#')
        dest = out / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest

    # ------------------------------------------------------------------
    # Filtering helpers
    # ------------------------------------------------------------------

    def get_entries_by_ext(self, ext: str) -> List[FPDEntry]:
        """Return entries whose filepath ends with the given extension."""
        if not ext.startswith('.'):
            ext = '.' + ext
        return [e for e in self.entries if e.filepath and e.filepath.endswith(ext)]

    def get_entry_by_path(self, path: str) -> Optional[FPDEntry]:
        """Find entry by its full filepath (forward slashes)."""
        for entry in self.entries:
            if entry.filepath == path:
                return entry
        return None

    def list_entries(self) -> List[str]:
        return [e.filepath for e in self.entries if e.filepath]

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, file_path: str, decrypt_key: bytes) -> 'FPDPackage':
        return cls(file_path, decrypt_key)

    @classmethod
    def load_key(cls, key_path: str) -> bytes:
        with open(key_path, 'rb') as f:
            return f.read()
