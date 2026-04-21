"""
core/epk_names.py — EPK filename hash resolver for FSN Remastered

KiriKiri script files (.ks) are named in Japanese (e.g. "プロローグ1日目.ks").
Their corresponding EPK locale files have hashed filenames derived via:
    hash = md5(script_name_utf8)
    → base-32-like encoding using [0-9a-z] alphabet

Algorithm by @tea (credited in epk_name_hash.py from kurikomoe/FSNr_tools).

Usage::
    from core.epk_names import ks_to_epk_hash, build_name_map

    hash = ks_to_epk_hash("プロローグ1日目")
    # → "1jftmqc2rr04kclvl0ql71s2ef"
"""

import hashlib
import string
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Alphabet used for the hash encoding (36 chars: 0-9 + a-z)
_ALPHABET = string.digits + string.ascii_lowercase


def ks_to_epk_hash(script_name: str) -> str:
    """
    Convert a KiriKiri script name to its EPK hash filename.

    Args:
        script_name: The script name WITHOUT path and WITHOUT .ks extension
                     e.g. "プロローグ1日目"

    Returns:
        26-character hash string, e.g. "1jftmqc2rr04kclvl0ql71s2ef"
    """
    txt_enc = script_name.encode('utf-8')
    digest = hashlib.md5(txt_enc).digest()
    bits = int.from_bytes(digest, byteorder='big')

    result = ''
    for i in range(3, 3 + 128, 5):
        digit = (bits << i >> 128) & 0x1F
        result += _ALPHABET[digit]

    return result


def epk_path_from_ks_name(script_name: str, locale: str = 'ck') -> str:
    """
    Return the full in-package path for a script's EPK locale file.

    Args:
        script_name: script stem name (no path, no .ks)
        locale: locale code (default 'ck' for Chinese/common)

    Returns:
        "root/data/locale/<locale>/epk/<hash>.epk"
    """
    h = ks_to_epk_hash(script_name)
    return f"root/data/locale/{locale}/epk/{h}.epk"


def build_name_map(ks_names: List[str], locale: str = 'ck') -> Dict[str, str]:
    """
    Build a mapping from EPK hash filename → KS script name.

    Args:
        ks_names: list of script stem names (no path, no .ks extension)
        locale: locale code

    Returns:
        Dict: { "1jftmqc2rr04kclvl0ql71s2ef": "プロローグ1日目", ... }
    """
    result = {}
    for name in ks_names:
        h = ks_to_epk_hash(name)
        result[h] = name
    return result


def extract_ks_names_from_fpd_entries(fpd_entries: List) -> List[str]:
    """
    Extract KS script stem names from FPD entry filepaths.

    Args:
        fpd_entries: list of FPDEntry objects (with .filepath attribute)

    Returns:
        List of script name stems (e.g. ["プロローグ1日目", "セイバーエピローグ", ...])
    """
    names = []
    for entry in fpd_entries:
        if entry.filepath and entry.filepath.endswith('.ks'):
            stem = Path(entry.filepath).stem
            names.append(stem)
    return names


def resolve_epk_filename(epk_filename: str, ks_names: List[str]) -> Optional[str]:
    """
    Given an EPK filename hash (without .epk extension), find the matching KS name.

    Args:
        epk_filename: hash portion of filename, e.g. "1jftmqc2rr04kclvl0ql71s2ef"
        ks_names: list of possible script names to check

    Returns:
        Matching KS script name, or None if not found
    """
    name_map = build_name_map(ks_names)
    return name_map.get(epk_filename)


def describe_epk(epk_filename: str, ks_names: List[str]) -> str:
    """Human-readable description of an EPK file given known KS names."""
    stem = epk_filename.replace('.epk', '')
    ks_name = resolve_epk_filename(stem, ks_names)
    if ks_name:
        return f"{epk_filename} → {ks_name}.ks"
    return f"{epk_filename} → (unknown)"


# ---------------------------------------------------------------------------
# Pre-built name list (extracted from patch00m.bin's .ks entries)
# Users can extend this list for other game versions
# ---------------------------------------------------------------------------

KNOWN_KS_NAMES = [
    # Common / prologue
    "プロローグ1日目",
    "プロローグ2日目",
    # Saber route
    "セイバーエピローグ",
    # Add more as discovered...
]
