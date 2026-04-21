"""
core/dat_pack.py — DAT pack unpacker using fileinfo_*.txt index files

The game's obb/pack/ folder contains:
  - fileinfo_*.txt      — index files listing name/type/offset/size/md5
  - *.dat               — the actual data containers

Format of fileinfo lines::
    name::type::source.dat::offset::size::md5::flags::scale::?::?::

This module reads these index files and extracts individual assets.
"""

import os
import re
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from multiprocessing.pool import ThreadPool

log = logging.getLogger(__name__)

_LINE_PATTERN = re.compile(
    r'^(.+?)::(.+?)::(.+?)::(\d+)::(\d+)::([a-f0-9]{32})::(.*)$'
)


@dataclass
class FileInfoEntry:
    name: str
    ext: str
    source_dat: str      # e.g. "patch.dat", "saber.dat"
    offset: int
    size: int
    md5: str
    flags: str = ''      # remaining fields as raw string


class DATPackUnpacker:
    """
    Reads fileinfo_*.txt files and extracts files from the corresponding .dat containers.

    Usage::

        unpacker = DATPackUnpacker(pack_dir="./obb/pack/", output_dir="./extracted/")
        unpacker.extract_all()
        # or extract specific dat
        unpacker.extract_from_dat("patch.dat")
    """

    def __init__(self, pack_dir: str, output_dir: str):
        self.pack_dir = Path(pack_dir)
        self.output_dir = Path(output_dir)
        self._index: Dict[str, Dict[str, FileInfoEntry]] = {}  # dat_name -> {filename -> entry}

    # ------------------------------------------------------------------
    # Index loading
    # ------------------------------------------------------------------

    def load_index(self) -> int:
        """Load all fileinfo_*.txt files. Returns total entries found."""
        fileinfos = list(self.pack_dir.glob("fileinfo_*.txt"))
        if not fileinfos:
            raise FileNotFoundError(f"No fileinfo_*.txt found in {self.pack_dir}")

        total = 0
        for fi_path in fileinfos:
            entries = self._parse_fileinfo(fi_path)
            for dat_name, file_entries in entries.items():
                if dat_name not in self._index:
                    self._index[dat_name] = {}
                self._index[dat_name].update(file_entries)
                total += len(file_entries)

        log.info(f"Loaded {total} entries from {len(fileinfos)} fileinfo files")
        return total

    def _parse_fileinfo(self, path: Path) -> Dict[str, Dict[str, FileInfoEntry]]:
        result: Dict[str, Dict[str, FileInfoEntry]] = {}
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = _LINE_PATTERN.match(line)
                if not m:
                    log.warning(f"Unrecognized fileinfo line: {line!r}")
                    continue

                name = m.group(1)
                ext = m.group(2)
                source = m.group(3)
                offset = int(m.group(4))
                size = int(m.group(5))
                md5 = m.group(6)
                flags = m.group(7)

                entry = FileInfoEntry(
                    name=name, ext=ext, source_dat=source,
                    offset=offset, size=size, md5=md5, flags=flags
                )

                if source not in result:
                    result[source] = {}
                result[source][f"{name}.{ext}"] = entry

        return result

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract_all(self, verify_md5: bool = True, num_workers: int = 4) -> int:
        """Extract all indexed files. Returns count of files extracted."""
        if not self._index:
            self.load_index()

        total = 0
        for dat_name, entries in self._index.items():
            total += self._extract_dat(dat_name, entries, verify_md5)

        log.info(f"Extracted {total} files total")
        return total

    def extract_from_dat(self, dat_name: str, verify_md5: bool = True) -> int:
        """Extract files from a specific .dat container."""
        if not self._index:
            self.load_index()
        if dat_name not in self._index:
            raise KeyError(f"No fileinfo entries for: {dat_name}")
        return self._extract_dat(dat_name, self._index[dat_name], verify_md5)

    def _extract_dat(self, dat_name: str, entries: Dict[str, FileInfoEntry], verify_md5: bool) -> int:
        dat_path = self.pack_dir / dat_name
        if not dat_path.exists():
            log.warning(f"DAT file not found, skipping: {dat_path}")
            return 0

        out_dir = self.output_dir / dat_name
        out_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        with open(dat_path, 'rb') as f:
            for filename, entry in entries.items():
                f.seek(entry.offset)
                data = f.read(entry.size)

                if verify_md5:
                    actual_md5 = hashlib.md5(data).hexdigest()
                    if actual_md5.lower() != entry.md5.lower():
                        log.warning(f"MD5 mismatch: {filename} in {dat_name}")

                dest = out_dir / filename
                dest.write_bytes(data)
                count += 1
                log.debug(f"  {filename} → {dest}")

        log.info(f"Extracted {count} files from {dat_name}")
        return count

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def find_by_ext(self, ext: str) -> List[Tuple[str, str, FileInfoEntry]]:
        """Find all entries with a given extension. Returns (dat, filename, entry) tuples."""
        if not ext.startswith('.'):
            ext = '.' + ext
        results = []
        for dat_name, entries in self._index.items():
            for fname, entry in entries.items():
                if fname.endswith(ext):
                    results.append((dat_name, fname, entry))
        return results

    def get_entry(self, dat_name: str, filename: str) -> Optional[FileInfoEntry]:
        return self._index.get(dat_name, {}).get(filename)

    def read_entry_bytes(self, dat_name: str, filename: str) -> bytes:
        entry = self.get_entry(dat_name, filename)
        if not entry:
            raise KeyError(f"{filename} not found in {dat_name}")
        dat_path = self.pack_dir / dat_name
        with open(dat_path, 'rb') as f:
            f.seek(entry.offset)
            return f.read(entry.size)
