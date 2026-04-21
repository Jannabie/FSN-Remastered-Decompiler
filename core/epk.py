"""
core/epk.py — EPK encrypt/decrypt for FSN Remastered

EPK files are encrypted KiriKiri script locale packages.

ENCRYPTION KEY DERIVATION
─────────────────────────
main.exe derives the keystream from two inputs:
  1. SomeKey.bin  (5120 bytes — dumped from game process at VA 0x1409E6500)
  2. The EPK filename STEM — specifically the 26-char hash, e.g. "1jftmqc2rr04kclvl0ql71s2ef"

CRITICAL BUG (now fixed):
  When FPD extracts EPK files, they get the full path as filename using '#' as separator:
    "root#data#locale#ck#epk#HASH.epk"
  If this full name is passed to main.exe, it reads the stem as:
    "root#data#locale#ck#epk#HASH"   <-- WRONG key, 46 chars
  Instead of:
    "HASH"                            <-- correct key, 26 chars
  Wrong key → wrong keystream → crash → exit code 3221225781

  Fix: always rename to "HASH.epk" in an isolated tempdir before running main.exe.
  This is why pack00m.bin EPKs failed while manually-renamed patch00m EPKs worked.

EPK FILE LAYOUT
───────────────
  [ encrypted payload ···· N bytes ]
  [ 0x10 bytes zero padding        ]
  [ uint32 BE raw_size + 12 zeros  ]  (= 0x10 bytes)
  [ 16 bytes MD5 checksum          ]  (md5(payload + MAGIC_KEY))
  Total trailer = 0x30 bytes

  MAGIC_KEY = "8FE9D249BD2689BB4B70F5AE88A9E645"

Credit: kurikomoe/FSNr_tools, @tea
"""

import os
import re
import sys
import shutil
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

log = logging.getLogger(__name__)

# Matches a 26-char lowercase alphanumeric EPK hash stem
_HASH_RE = re.compile(r'^[0-9a-z]{10,}$')


def extract_epk_stem(path: Path) -> str:
    """
    Extract the correct EPK hash stem from ANY filename style.

    Examples:
      "HASH.epk"                                → "HASH"
      "root#data#locale#ck#epk#HASH.epk"        → "HASH"
      "root#data#locale#ck#epk#HASH.epk_dec"    → "HASH"
      "root_data_locale_ck_epk_HASH.epk_dec"    → "HASH"
      "uistring.epk"                            → "uistring"
      "statictext.epk_dec"                      → "statictext"

    This is critical because main.exe uses this stem as its crypto key input.
    """
    name = path.name

    # Strip known suffixes
    for suffix in ('.epk_dec', '.epk_enc', '.epk'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    # "root#data#locale#ck#epk#HASH" → take last '#' segment
    if '#' in name:
        return name.rsplit('#', 1)[-1]

    # "root_data_locale_ck_epk_HASH" → take last '_' segment that looks like a hash
    if '_' in name and not _HASH_RE.match(name):
        for part in reversed(name.split('_')):
            if _HASH_RE.match(part):
                return part

    return name


class EPKError(Exception):
    pass


class EPKCrypto:
    """
    Handles EPK encrypt/decrypt via the bundled main.exe.

    main.exe is a Windows binary (compiled from kurikomoe/FSNr_tools).
    On Linux/macOS it requires Wine.

    decrypt:  .epk      → .epk_dec  (readable DAT text)
    encrypt:  .epk_dec  → .epk      (encrypted, deployable)
    """

    def __init__(self, main_exe_path: str, some_key_path: str):
        self.main_exe = Path(main_exe_path).resolve()
        self.some_key = Path(some_key_path).resolve()

        if not self.main_exe.exists():
            raise FileNotFoundError(f"main.exe not found: {self.main_exe}")
        if not self.some_key.exists():
            raise FileNotFoundError(f"SomeKey.bin not found: {self.some_key}")

    # ── Public API ─────────────────────────────────────────────────────

    def decrypt(
        self,
        epk_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Decrypt an EPK file → .epk_dec plain text.

        Args:
            epk_path:    path to encrypted .epk (any naming style)
            output_path: where to write output (default: same dir as input)
        Returns:
            Path to the decrypted .epk_dec file.
        """
        epk_path = Path(epk_path)
        if not epk_path.exists():
            raise FileNotFoundError(f"EPK not found: {epk_path}")

        stem = extract_epk_stem(epk_path)
        log.debug(f"decrypt: {epk_path.name!r} → stem={stem!r}")
        result = self._run(epk_path, mode='dec', stem=stem)

        if output_path:
            dest = Path(output_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(result), str(dest))
            return dest
        return result

    def encrypt(
        self,
        dec_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Encrypt a .epk_dec file → deployable .epk.

        Args:
            dec_path:    path to plaintext .epk_dec file
            output_path: where to write output (default: same dir as input)
        Returns:
            Path to the encrypted .epk file.
        """
        dec_path = Path(dec_path)
        if not dec_path.exists():
            raise FileNotFoundError(f"EPK_dec not found: {dec_path}")

        stem = extract_epk_stem(dec_path)
        log.debug(f"encrypt: {dec_path.name!r} → stem={stem!r}")
        result = self._run(dec_path, mode='enc', stem=stem)

        if output_path:
            dest = Path(output_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(result), str(dest))
            return dest
        return result

    def decrypt_bytes(self, data: bytes, filename_stem: str) -> bytes:
        """Decrypt EPK raw bytes. filename_stem must be the correct 26-char hash."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / f"{filename_stem}.epk"
            src.write_bytes(data)
            out = self.decrypt(src, Path(td) / f"{filename_stem}.epk_dec")
            return out.read_bytes()

    def encrypt_bytes(self, data: bytes, filename_stem: str) -> bytes:
        """Encrypt plain-text bytes to EPK format."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / f"{filename_stem}.epk_dec"
            src.write_bytes(data)
            out = self.encrypt(src, Path(td) / f"{filename_stem}.epk")
            return out.read_bytes()

    # ── Core runner ────────────────────────────────────────────────────

    def _run(self, source: Path, mode: str, stem: str) -> Path:
        """
        Run main.exe in an isolated temp directory.

        Isolation guarantees:
          - SomeKey.bin is always in the same dir as main.exe (required)
          - Source file is named exactly "<stem>.epk" or "<stem>.epk_dec"
            so main.exe gets the correct stem as the crypto key
          - No interference from other files
        """
        tmpdir = Path(tempfile.mkdtemp(prefix='fsn_epk_'))
        try:
            # --- Set up the isolated workspace ---
            tmp_exe = tmpdir / 'main.exe'
            tmp_key = tmpdir / 'SomeKey.bin'
            shutil.copy2(str(self.main_exe), str(tmp_exe))
            shutil.copy2(str(self.some_key), str(tmp_key))

            # Rename source to the CORRECT short name
            if mode == 'dec':
                tmp_src  = tmpdir / f"{stem}.epk"
                tmp_out  = tmpdir / f"{stem}.epk_dec"
            else:
                tmp_src  = tmpdir / f"{stem}.epk_dec"
                tmp_out  = tmpdir / f"{stem}.epk_enc"

            shutil.copy2(str(source), str(tmp_src))

            # --- Build command ---
            cmd = [str(tmp_exe), mode, str(tmp_src)]
            if sys.platform != 'win32':
                wine = shutil.which('wine') or shutil.which('wine64')
                if not wine:
                    raise EPKError(
                        "EPK crypto requires Windows or Wine.\n"
                        "  Linux:  sudo apt install wine\n"
                        "  macOS:  brew install --cask wine-stable"
                    )
                cmd = [wine] + cmd

            log.debug(f"Running: {' '.join(str(c) for c in cmd)}")

            proc = subprocess.run(
                cmd,
                cwd=str(tmpdir),
                capture_output=True,
                text=True,
                timeout=120,
            )

            if proc.returncode != 0:
                msg = (
                    f"main.exe failed (exit code {proc.returncode}):\n"
                    f"  stdout: {proc.stdout.strip()}\n"
                    f"  stderr: {proc.stderr.strip()}\n\n"
                    f"Troubleshooting:\n"
                )
                code = proc.returncode
                if code == 3221225781:   # 0xC0000135
                    msg += (
                        "  0xC0000135 = DLL not found.\n"
                        "  Windows 7/8: install Visual C++ 2015-2022 Redistributable\n"
                        "               or Windows Update KB2999226\n"
                        "  Windows 10+: this should not occur — check main.exe integrity"
                    )
                elif code == 3221225477:  # 0xC0000005
                    msg += "  0xC0000005 = Access violation — likely SomeKey.bin is corrupted"
                raise EPKError(msg)

            if not tmp_out.exists():
                raise EPKError(
                    f"main.exe exited OK but output not found: {tmp_out.name}\n"
                    f"  stdout: {proc.stdout.strip()}"
                )

            # Move result to output directory (same as original source)
            dest = source.parent / tmp_out.name
            shutil.move(str(tmp_out), str(dest))
            return dest

        finally:
            shutil.rmtree(str(tmpdir), ignore_errors=True)


# ── EPK text format parser ─────────────────────────────────────────────────

class EPKFile:
    """
    Represents a decrypted EPK locale data file (plain UTF-8 text).

    Format::
        DAT
        id=qid::label=str::text=lstr::
        27244::$$$message_0234_0000_0000$$$::那是有如闪电的枪尖。[lr]::
        27245::$$$message_0234_0000_0001$$$::迎面刺来的枪尖试图贯穿心脏。[lr]::

    Fields:  id :: $$$placeholder$$$ :: text :: [extra]

    Markup tags to keep when translating:
        [lr]           — line-break + wait for click
        [l]            — wait for click only
        [p]            — page break
        [r]            — newline
        [ruby text=""] — ruby annotation (furigana)
    """

    HEADER = "DAT\r\nid=qid::label=str::text=lstr::\r\n"

    def __init__(self):
        self.entries: list = []

    @classmethod
    def from_bytes(cls, data: bytes) -> 'EPKFile':
        obj = cls()
        for line in data.decode('utf-8', errors='replace').splitlines():
            line = line.strip()
            if not line or line == 'DAT' or line.startswith('id='):
                continue
            parts = line.split('::')
            if len(parts) >= 3:
                obj.entries.append([
                    parts[0].strip(),
                    parts[1].strip(),
                    parts[2].strip(),
                    parts[3] if len(parts) > 3 else '',
                ])
        return obj

    def to_bytes(self) -> bytes:
        lines = [self.HEADER]
        for eid, ph, text, extra in self.entries:
            if extra:
                lines.append(f"{eid}::{ph}::{text}::{extra}::\r\n")
            else:
                lines.append(f"{eid}::{ph}::{text}::\r\n")
        return ''.join(lines).encode('utf-8')

    def get_by_placeholder(self, placeholder: str) -> Optional[list]:
        for e in self.entries:
            if e[1] == placeholder:
                return e
        return None

    def get_all_texts(self) -> list:
        return [(e[1], e[2]) for e in self.entries]

    def set_text(self, placeholder: str, new_text: str) -> bool:
        for e in self.entries:
            if e[1] == placeholder:
                e[2] = new_text
                return True
        return False

    def replace_all(self, translations: dict) -> int:
        """Apply {placeholder: translation} dict. Returns number of replacements."""
        count = 0
        for e in self.entries:
            val = translations.get(e[1], '')
            if val:
                e[2] = val
                count += 1
        return count

    def export_for_translation(self) -> list:
        return [
            {'id': e[0], 'placeholder': e[1], 'original': e[2], 'translation': ''}
            for e in self.entries
        ]
