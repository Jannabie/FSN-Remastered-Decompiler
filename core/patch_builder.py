"""
core/patch_builder.py — Build and deploy translation patches for FSN Remastered

The game reads EPK files from %LOCALAPPDATA%/typemoon/fsn2/data/
with the SAME directory structure as in the package.

Deployment strategy (no game file modification):
    1. Encrypt translated EPK files
    2. Place them in %LOCALAPPDATA%/typemoon/fsn2/data/root/data/locale/ck/epk/
    3. Game auto-loads them instead of the packed versions

For non-Steam / cracked versions, %LOCALAPPDATA% can be redirected by
setting the LOCALAPPDATA environment variable before launching the game.
This allows shipping a self-contained patch folder.

Credit: kurikomoe/FSNr_tools (FSNr_Bonus.7z technique)
"""

import os
import sys
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from .epk import EPKCrypto, EPKFile
from .epk_names import ks_to_epk_hash

log = logging.getLogger(__name__)

# Default locale code used by the game for string data
DEFAULT_LOCALE = 'ck'

# EPK subdirectory structure inside the game's data folder
EPK_SUBDIR_TEMPLATE = "root/data/locale/{locale}/epk"

# The game's local data path (Windows)
GAME_DATA_REL = r"typemoon\fsn2\data"


def get_localappdata_path() -> Optional[Path]:
    """Return %%LOCALAPPDATA%% path on Windows, or None on other platforms."""
    if sys.platform == 'win32':
        local = os.environ.get('LOCALAPPDATA')
        if local:
            return Path(local)
    return None


def get_game_userdata_path(custom_localappdata: Optional[str] = None) -> Path:
    """
    Return the path where the game reads user-overridden EPK files.

    Args:
        custom_localappdata: override %%LOCALAPPDATA%% (for cracked/non-Steam versions)
    """
    if custom_localappdata:
        base = Path(custom_localappdata)
    else:
        base = get_localappdata_path()
        if base is None:
            raise RuntimeError("Cannot determine LOCALAPPDATA path. Use custom_localappdata parameter.")
    return base / GAME_DATA_REL


class PatchBuilder:
    """
    Builds a translation patch from edited EPK files.

    Workflow::
        builder = PatchBuilder(crypto, output_dir="./my_patch/")
        builder.add_translated_epk("プロローグ1日目", translated_epk_bytes)
        builder.build()
        builder.deploy()  # copy to %%LOCALAPPDATA%%
        # or: builder.export_launcher()  # create a .bat/.ps1 that sets LOCALAPPDATA
    """

    def __init__(
        self,
        crypto: EPKCrypto,
        output_dir: str,
        locale: str = DEFAULT_LOCALE,
    ):
        self.crypto = crypto
        self.output_dir = Path(output_dir)
        self.locale = locale
        self._translated: Dict[str, bytes] = {}   # ks_name → translated EPK plaintext bytes
        self._patch_name = "fsn_patch"

    # ------------------------------------------------------------------
    # Adding translations
    # ------------------------------------------------------------------

    def add_translated_epk(self, ks_name: str, epk_dec_bytes: bytes) -> None:
        """
        Register a translated EPK for a given script name.

        Args:
            ks_name: KS script stem, e.g. "プロローグ1日目"
            epk_dec_bytes: translated EPK plaintext (UTF-8 DAT format)
        """
        self._translated[ks_name] = epk_dec_bytes
        log.debug(f"Added translation for: {ks_name}")

    def load_translations_from_json(self, json_path: str) -> int:
        """
        Load translations from a JSON file produced by export_for_translation().

        JSON format::
            {
              "ks_name": "プロローグ1日目",
              "entries": [
                {"id": "27244", "placeholder": "$$$...$$$", "original": "...", "translation": "..."},
                ...
              ]
            }

        Returns number of EPK files loaded.
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Support both single-file and multi-file JSON
        if isinstance(data, dict) and 'ks_name' in data:
            data = [data]

        count = 0
        for item in data:
            ks_name = item['ks_name']
            original_bytes = item.get('_original_bytes')
            entries = item['entries']

            # Build translation dict
            translations = {
                e['placeholder']: e['translation']
                for e in entries
                if e.get('translation')
            }

            if not translations:
                log.warning(f"No translations found for {ks_name}, skipping")
                continue

            # Apply to EPK
            epk = EPKFile.from_bytes(item.get('_original_bytes_b64', b'').encode() or b'')
            epk.replace_all(translations)
            self._translated[ks_name] = epk.to_bytes()
            count += 1

        return count

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def build(self) -> Path:
        """
        Encrypt all translated EPK files and place them in the patch folder.

        Returns: Path to the built patch directory
        """
        epk_subdir = EPK_SUBDIR_TEMPLATE.format(locale=self.locale)
        patch_epk_dir = self.output_dir / epk_subdir.replace('/', os.sep)
        patch_epk_dir.mkdir(parents=True, exist_ok=True)

        for ks_name, dec_bytes in self._translated.items():
            epk_hash = ks_to_epk_hash(ks_name)
            epk_filename = f"{epk_hash}.epk"
            out_path = patch_epk_dir / epk_filename

            log.info(f"Building: {ks_name} → {epk_filename}")
            enc_bytes = self.crypto.encrypt_bytes(dec_bytes, epk_hash)
            out_path.write_bytes(enc_bytes)

        log.info(f"Patch built at: {self.output_dir}")
        return self.output_dir

    # ------------------------------------------------------------------
    # Deployment
    # ------------------------------------------------------------------

    def deploy(self, custom_localappdata: Optional[str] = None, dry_run: bool = False) -> List[Path]:
        """
        Copy the built patch to the game's user data directory.

        Args:
            custom_localappdata: override %%LOCALAPPDATA%% path
            dry_run: if True, only print what would be copied

        Returns:
            List of destination paths
        """
        game_data = get_game_userdata_path(custom_localappdata)
        deployed = []

        for src_file in self.output_dir.rglob('*'):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(self.output_dir)
            dest = game_data / rel
            if dry_run:
                log.info(f"[DRY RUN] Would copy: {src_file} → {dest}")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_file), str(dest))
                log.info(f"Deployed: {dest}")
            deployed.append(dest)

        return deployed

    def export_launcher(self, game_exe: str, output_path: Optional[str] = None) -> Path:
        """
        Create a Windows batch/PowerShell launcher that:
        1. Sets LOCALAPPDATA to the patch folder
        2. Launches the game

        This is the recommended way to ship a patch for cracked/non-Steam versions.

        Args:
            game_exe: path to the game executable (absolute or relative)
            output_path: where to write the launcher (default: patch_dir/launch_with_patch.bat)

        Returns:
            Path to the created launcher
        """
        if output_path is None:
            output_path = self.output_dir / "launch_with_patch.bat"
        else:
            output_path = Path(output_path)

        # Compute absolute path to patch root (the "data" directory)
        # The game reads: %%LOCALAPPDATA%%\typemoon\fsn2\data\
        # So we set LOCALAPPDATA to: <patch_dir>\..\  (one level up from typemoon/)
        # Actually we need: LOCALAPPDATA = <something> and then <something>\typemoon\fsn2\data = our patch
        # Simplest: create a folder structure matching
        #   <output_dir>/LOCALAPPDATA/typemoon/fsn2/data/ = <output_dir>/
        # and set LOCALAPPDATA = <output_dir>/../LOCALAPPDATA (or use a subdir)

        # Structure: output_dir IS the "data" folder.
        # LOCALAPPDATA should be set so that LOCALAPPDATA\typemoon\fsn2\data = output_dir
        # → LOCALAPPDATA = output_dir\..\..\..\  (3 levels up)
        localappdata_anchor = self.output_dir.resolve().parent.parent.parent

        bat_content = f"""@echo off
REM FSN Remastered Translation Patch Launcher
REM Auto-generated by fsn-tools

SET "PATCH_DIR=%~dp0"
SET "LOCALAPPDATA={localappdata_anchor}"

echo Launching FSN Remastered with translation patch...
echo LOCALAPPDATA set to: %%LOCALAPPDATA%%

start "" "{game_exe}"
"""

        ps1_content = f"""# FSN Remastered Translation Patch Launcher
# Auto-generated by fsn-tools

$env:LOCALAPPDATA = "{localappdata_anchor}"
Write-Host "Launching FSN Remastered with translation patch..."
Write-Host "LOCALAPPDATA set to: $env:LOCALAPPDATA"
Start-Process "{game_exe}"
"""

        output_path.write_text(bat_content, encoding='utf-8')
        ps1_path = output_path.with_suffix('.ps1')
        ps1_path.write_text(ps1_content, encoding='utf-8')

        log.info(f"Launcher written: {output_path}")
        log.info(f"Launcher written: {ps1_path}")
        return output_path
