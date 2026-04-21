"""
core/epk.py — EPK encrypt/decrypt for FSN Remastered

EPK files are encrypted KiriKiri script locale packages.
The encryption uses a keystream derived from:
  - SomeKey.bin  (5120 bytes, dumped from game process at 0x1409E6500)
  - The EPK filename stem (e.g. "1jftmqc2rr04kclvl0ql71s2ef")

Since the key-init algorithm (sub_1404C80B0 + DecEncEPK from the C++ source)
is not open-sourced, we delegate to the pre-compiled main.exe via subprocess.

EPK file layout (from kurikomoe/FSNr_tools):
    [encrypted payload ............. N bytes, 4-byte aligned]
    [0x10 bytes zero padding                                 ]
    [raw_size: 4 bytes BE + 0xC bytes zero pad  (= 0x10)    ]
    [MD5 hash: 16 bytes  (md5(payload + MAGIC_KEY))         ]
    Total trailer = 0x30 bytes

The MD5 magic constant is: "8FE9D249BD2689BB4B70F5AE88A9E645"

Credit: kurikomoe/FSNr_tools, Jannabie/FSN_Decompiler
"""

import os
import sys
import struct
import hashlib
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Optional, Union

log = logging.getLogger(__name__)

MAGIC_KEY = b"8FE9D249BD2689BB4B70F5AE88A9E645"
TRAILER_SIZE = 0x30


class EPKError(Exception):
    pass


class EPKCrypto:
    """
    Handles EPK encrypt/decrypt using the bundled main.exe.

    The main.exe must be present alongside SomeKey.bin in the same directory.
    On Windows, it's called directly. On other platforms, Wine is tried.

    For decryption:  epk  → epk_dec  (plaintext locale DAT)
    For encryption:  epk_dec → epk   (encrypted, ready to deploy)
    """

    def __init__(self, main_exe_path: str, some_key_path: str):
        self.main_exe = Path(main_exe_path).resolve()
        self.some_key = Path(some_key_path).resolve()

        if not self.main_exe.exists():
            raise FileNotFoundError(f"main.exe not found: {self.main_exe}")
        if not self.some_key.exists():
            raise FileNotFoundError(f"SomeKey.bin not found: {self.some_key}")

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    def decrypt(self, epk_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Decrypt an EPK file to produce a plain-text .epk_dec.

        Args:
            epk_path: path to encrypted .epk file
            output_path: where to write the decrypted file (default: same dir, .epk_dec extension)

        Returns:
            Path to the decrypted file
        """
        epk_path = Path(epk_path)
        if not epk_path.exists():
            raise FileNotFoundError(f"EPK not found: {epk_path}")

        result = self._run(epk_path, mode='dec')
        # main.exe writes <same_path>.epk_dec
        dec_path = epk_path.with_suffix('.epk_dec')

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dec_path), str(output_path))
            return output_path

        return dec_path

    def encrypt(self, dec_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Encrypt a .epk_dec file to produce a deployable .epk.

        Args:
            dec_path: path to decrypted .epk_dec file
            output_path: where to write the encrypted file (default: same dir, renamed to .epk)

        Returns:
            Path to the encrypted file
        """
        dec_path = Path(dec_path)
        if not dec_path.exists():
            raise FileNotFoundError(f"EPK_dec not found: {dec_path}")

        result = self._run(dec_path, mode='enc')
        # main.exe writes <same_path>.epk_enc
        enc_path = dec_path.with_suffix('.epk_enc')

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(enc_path), str(output_path))
            return output_path

        return enc_path

    def decrypt_bytes(self, data: bytes, filename_stem: str) -> bytes:
        """
        Decrypt EPK data given as bytes.
        Uses a temp directory to avoid naming conflicts.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # main.exe derives keystream from filename stem
            epk_file = Path(tmpdir) / f"{filename_stem}.epk"
            epk_file.write_bytes(data)
            dec_file = self.decrypt(epk_file)
            return dec_file.read_bytes()

    def encrypt_bytes(self, data: bytes, filename_stem: str) -> bytes:
        """Encrypt plain-text bytes to EPK format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dec_file = Path(tmpdir) / f"{filename_stem}.epk_dec"
            dec_file.write_bytes(data)
            enc_file = self.encrypt(dec_file)
            return enc_file.read_bytes()

    # ------------------------------------------------------------------
    # Subprocess runner
    # ------------------------------------------------------------------

    def _run(self, target: Path, mode: str) -> subprocess.CompletedProcess:
        """Run main.exe in a temp directory where SomeKey.bin is present."""
        # main.exe reads SomeKey.bin from the same directory as the exe
        # We symlink/copy main.exe and SomeKey.bin to a work dir,
        # then call it with the target file path

        work_dir = target.parent

        # Ensure SomeKey.bin is in the same directory as main.exe
        # (main.exe looks for SomeKey.bin relative to argv[0])
        # We copy main.exe + SomeKey.bin to the target's directory temporarily
        # if they're not already there

        key_in_workdir = work_dir / 'SomeKey.bin'
        exe_in_workdir = work_dir / 'main.exe'

        _cleanup_exe = False
        _cleanup_key = False

        try:
            if not exe_in_workdir.exists() or exe_in_workdir.resolve() != self.main_exe:
                shutil.copy2(str(self.main_exe), str(exe_in_workdir))
                _cleanup_exe = True

            if not key_in_workdir.exists() or key_in_workdir.resolve() != self.some_key:
                shutil.copy2(str(self.some_key), str(key_in_workdir))
                _cleanup_key = True

            cmd = [str(exe_in_workdir), mode, str(target)]

            # On Linux, try Wine
            if sys.platform != 'win32':
                wine = shutil.which('wine') or shutil.which('wine64')
                if wine:
                    cmd = [wine] + cmd
                else:
                    raise EPKError(
                        "main.exe requires Windows or Wine. "
                        "Install Wine (sudo apt install wine) or run on Windows."
                    )

            log.debug(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                raise EPKError(
                    f"main.exe failed (code {result.returncode}):\n"
                    f"  stdout: {result.stdout}\n"
                    f"  stderr: {result.stderr}"
                )

            log.debug(f"main.exe output: {result.stdout.strip()}")
            return result

        finally:
            if _cleanup_exe and exe_in_workdir.exists():
                exe_in_workdir.unlink(missing_ok=True)
            if _cleanup_key and key_in_workdir.exists():
                key_in_workdir.unlink(missing_ok=True)


class EPKFile:
    """
    Represents a decrypted EPK locale data file.

    Format::
        DAT\r\n
        id=qid::label=str::text=lstr::\r\n
        <id>::<placeholder>::<text>::\r\n
        ...

    Each text line:  numeric_id :: $$$message_XXXX_XXXX_NNNN$$$ :: actual_text :: [markup]
    """

    HEADER = "DAT\r\nid=qid::label=str::text=lstr::\r\n"

    def __init__(self):
        self.entries: list = []   # list of (id, placeholder, text, extra)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'EPKFile':
        """Parse decrypted EPK bytes."""
        obj = cls()
        text = data.decode('utf-8', errors='replace')
        lines = text.splitlines()

        for line in lines:
            if not line or line == 'DAT' or line.startswith('id='):
                continue
            parts = line.split('::')
            if len(parts) >= 3:
                entry_id = parts[0].strip()
                placeholder = parts[1].strip()
                content = parts[2].strip()
                extra = parts[3] if len(parts) > 3 else ''
                obj.entries.append([entry_id, placeholder, content, extra])

        return obj

    def to_bytes(self) -> bytes:
        """Serialize back to EPK text format."""
        lines = [self.HEADER]
        for entry_id, placeholder, text, extra in self.entries:
            if extra:
                line = f"{entry_id}::{placeholder}::{text}::{extra}::\r\n"
            else:
                line = f"{entry_id}::{placeholder}::{text}::\r\n"
            lines.append(line)
        return ''.join(lines).encode('utf-8')

    def get_by_placeholder(self, placeholder: str) -> Optional[list]:
        for entry in self.entries:
            if entry[1] == placeholder:
                return entry
        return None

    def get_all_texts(self) -> list:
        """Return list of (placeholder, text) tuples — the translatable content."""
        return [(e[1], e[2]) for e in self.entries]

    def set_text(self, placeholder: str, new_text: str) -> bool:
        for entry in self.entries:
            if entry[1] == placeholder:
                entry[2] = new_text
                return True
        return False

    def replace_all(self, translations: dict) -> int:
        """
        Apply a dict of {placeholder: new_text} translations.
        Returns number of replacements made.
        """
        count = 0
        for entry in self.entries:
            if entry[1] in translations:
                entry[2] = translations[entry[1]]
                count += 1
        return count

    def export_for_translation(self) -> list:
        """
        Return a list of dicts suitable for JSON export.
        Each dict: {id, placeholder, original, translation}
        """
        return [
            {
                'id': e[0],
                'placeholder': e[1],
                'original': e[2],
                'translation': ''
            }
            for e in self.entries
        ]
