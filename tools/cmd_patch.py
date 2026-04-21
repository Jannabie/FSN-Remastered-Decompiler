#!/usr/bin/env python3
"""
tools/cmd_patch.py — Build and deploy a deployable translation patch

The patch system works WITHOUT modifying game files.
The game reads override data from %LOCALAPPDATA%\\typemoon\\fsn2\\data\\
This means you can ship a patch as a separate folder + launcher script.

Commands:
    build       Encrypt translated .epk_dec files → ready-to-deploy .epk patch
    deploy      Copy built patch to %LOCALAPPDATA% (direct install)
    launcher    Create a .bat / .ps1 launcher for cracked / non-Steam versions
    extract-epk Pull an EPK from an FPD .bin and decrypt it in one step

Examples:
    # Build patch from translated epk_dec files
    python fsn-tools.py patch build ./work/translated/ \\
        --main-exe keys/main.exe --some-key keys/SomeKey.bin \\
        --out ./my_patch/

    # Deploy directly to %LOCALAPPDATA% (Steam / installed version)
    python fsn-tools.py patch deploy ./my_patch/

    # Create launcher for cracked version (redirects LOCALAPPDATA)
    python fsn-tools.py patch launcher ./my_patch/ \\
        --game-exe "C:\\Games\\Fate\\fsn2-win64vc14-release.exe"

    # One-step: extract EPK from FPD, decrypt it
    python fsn-tools.py patch extract-epk patch00m.bin プロローグ1日目 \\
        --key keys/decryptKey.bin --main-exe keys/main.exe --some-key keys/SomeKey.bin \\
        --out ./work/
"""

import os
import sys
import shutil
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.epk import EPKCrypto, EPKError
from core.fpd import FPDPackage
from core.epk_names import ks_to_epk_hash
from core.patch_builder import PatchBuilder, get_game_userdata_path
from data.ks_names import HASH_TO_KS_NAME, KS_NAME_TO_HASH

LOCALE_SUBPATH = "root/data/locale/ck/epk"


def _get_crypto(args):
    main_exe = Path(args.main_exe)
    some_key = Path(args.some_key)
    missing = []
    if not main_exe.exists():
        missing.append(f"main.exe   → {main_exe}")
    if not some_key.exists():
        missing.append(f"SomeKey.bin → {some_key}")
    if missing:
        print("[ERROR] Required crypto files missing:")
        for m in missing:
            print(f"  ✗  {m}")
        print()
        print("You need two files for EPK encryption:")
        print("  main.exe     — Windows binary from kurikomoe/FSNr_tools")
        print("                 (compile main.cpp with: g++ --std=c++20 -O2 main.cpp -o main.exe)")
        print("  SomeKey.bin  — 5120-byte key, bundled with the FSNr_tools release")
        print()
        print("→ Place both in the keys/ folder.")
        sys.exit(1)
    return EPKCrypto(str(main_exe), str(some_key))


def cmd_patch_build(args):
    crypto = _get_crypto(args)
    input_dir = Path(args.input)
    out_dir = Path(args.out)

    dec_files = list(input_dir.rglob('*.epk_dec'))
    if not dec_files:
        print(f"[ERROR] No .epk_dec files found in {input_dir}")
        print("  → Run 'translate import' first to produce translated .epk_dec files")
        sys.exit(1)

    # EPK output goes into: out_dir/root/data/locale/ck/epk/
    epk_out = out_dir / LOCALE_SUBPATH.replace('/', os.sep)
    epk_out.mkdir(parents=True, exist_ok=True)

    print(f"[BUILD] Building patch from {len(dec_files)} translated EPK files...")
    ok = 0
    fail = 0

    for dec_file in dec_files:
        # Determine EPK hash stem from filename
        stem = dec_file.name.replace('.epk_dec', '')
        if '#' in stem:
            stem = stem.rsplit('#', 1)[-1]

        ks_name = HASH_TO_KS_NAME.get(stem, stem)
        out_epk = epk_out / f"{stem}.epk"

        print(f"  [ENC] {ks_name}  ({stem}) ...")
        try:
            crypto.encrypt(dec_file, out_epk)
            print(f"    ✓  → {out_epk.name}")
            ok += 1
        except EPKError as e:
            print(f"    ✗  {e}")
            fail += 1

    print(f"\n{'✓' if not fail else '!'} Built {ok} EPK files → {out_dir}")
    if fail:
        print(f"  {fail} failures — check errors above")
    print()
    print("Next steps:")
    print(f"  Steam/installed:  python fsn-tools.py patch deploy {out_dir}/")
    print(f"  Cracked version:  python fsn-tools.py patch launcher {out_dir}/ --game-exe <path>")


def cmd_patch_deploy(args):
    patch_dir = Path(args.patch_dir)
    custom = args.localappdata if hasattr(args, 'localappdata') else None

    try:
        game_data = get_game_userdata_path(custom)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        print("  Use --localappdata to specify the path manually")
        sys.exit(1)

    epk_files = list(patch_dir.rglob('*.epk'))
    if not epk_files:
        print(f"[ERROR] No .epk files found in {patch_dir}")
        print("  → Run 'patch build' first")
        sys.exit(1)

    print(f"[DEPLOY] Deploying {len(epk_files)} EPK files to game data folder...")
    print(f"  Target: {game_data}")

    if args.dry_run:
        print("  (DRY RUN — not actually copying)")

    ok = 0
    for epk in epk_files:
        rel = epk.relative_to(patch_dir)
        dest = game_data / rel
        stem = epk.stem
        ks_name = HASH_TO_KS_NAME.get(stem, stem)

        if args.dry_run:
            print(f"  [DRY] {ks_name} → {dest}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(epk), str(dest))
            print(f"  ✓  {ks_name} → {dest}")
        ok += 1

    if not args.dry_run:
        print(f"\n✓  Deployed {ok} files. Launch the game normally.")
        print("  The game will read your translated EPK files from %LOCALAPPDATA%.")


def cmd_patch_launcher(args):
    patch_dir = Path(args.patch_dir).resolve()
    game_exe = args.game_exe

    # Patch structure: patch_dir/root/data/locale/ck/epk/
    # We want LOCALAPPDATA = patch_dir so that:
    #   %LOCALAPPDATA%\typemoon\fsn2\data\root\data\locale\ck\epk = patch_dir\root\data\locale\ck\epk
    # That means we need patch_dir to BE the "data" folder, which means LOCALAPPDATA = 3 levels up
    # But wait: the game reads %LOCALAPPDATA%\typemoon\fsn2\data\...
    # Our patch_dir IS the output folder containing root/data/locale/ck/epk/
    # So: LOCALAPPDATA needs to be such that LOCALAPPDATA\typemoon\fsn2\data = patch_dir
    # → LOCALAPPDATA = patch_dir / ".." / ".." / ".."

    # Create wrapper dir structure
    # Best practice: create a "_launch" subfolder with the full typemoon/fsn2/data symlink
    launch_dir = patch_dir / "_launch"
    fake_data_dir = launch_dir / "typemoon" / "fsn2" / "data"
    fake_data_dir.mkdir(parents=True, exist_ok=True)

    # Copy patch files into fake_data_dir
    for src in patch_dir.rglob('*.epk'):
        rel = src.relative_to(patch_dir)
        dest = fake_data_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))

    localappdata_path = launch_dir.resolve()

    bat = f"""@echo off
REM ============================================================
REM  FSN Remastered Translation Patch Launcher
REM  Generated by fsn-tools
REM ============================================================
REM  This launcher redirects %%LOCALAPPDATA%% so the game
REM  reads translated EPK files instead of the originals.
REM  The original game files are NOT modified.
REM ============================================================

SET "LOCALAPPDATA={localappdata_path}"

echo [FSN Patch Launcher]
echo LOCALAPPDATA redirected to: %LOCALAPPDATA%
echo Launching game...

start "" "{game_exe}"
"""

    ps1 = f"""# ============================================================
# FSN Remastered Translation Patch Launcher
# Generated by fsn-tools
# ============================================================
$env:LOCALAPPDATA = "{localappdata_path}"
Write-Host "[FSN Patch Launcher]" -ForegroundColor Cyan
Write-Host "LOCALAPPDATA redirected to: $env:LOCALAPPDATA"
Write-Host "Launching game..." -ForegroundColor Green
Start-Process "{game_exe}"
"""

    bat_path = patch_dir / "launch_with_patch.bat"
    ps1_path = patch_dir / "launch_with_patch.ps1"
    bat_path.write_text(bat, encoding='utf-8')
    ps1_path.write_text(ps1, encoding='utf-8')

    print(f"[LAUNCHER] Created launchers:")
    print(f"  {bat_path}")
    print(f"  {ps1_path}")
    print()
    print(f"  LOCALAPPDATA will be redirected to: {localappdata_path}")
    print(f"  Game EXE: {game_exe}")
    print()
    print("Usage:")
    print("  Double-click launch_with_patch.bat  — or —  run launch_with_patch.ps1")
    print()
    print("Note: The game's original files are NOT modified.")
    print("      Remove/rename the launcher to play without the patch.")


def cmd_patch_extract_epk(args):
    """One-step: pull an EPK from an FPD .bin and decrypt it."""
    bin_path = Path(args.bin_file)
    ks_name = args.ks_name
    key_path = Path(args.key)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not bin_path.exists():
        print(f"[ERROR] FPD file not found: {bin_path}")
        sys.exit(1)
    if not key_path.exists():
        print(f"[ERROR] Key file not found: {key_path}")
        print("  → You need keys/decryptKey.bin")
        sys.exit(1)

    epk_hash = ks_to_epk_hash(ks_name)
    crypto = _get_crypto(args)

    print(f"[EXTRACT] {ks_name}.ks → hash: {epk_hash}")
    print(f"  Loading FPD: {bin_path.name} ...")

    dec_key = key_path.read_bytes()
    pkg = FPDPackage(str(bin_path), dec_key)

    # Find the EPK entry
    epk_entry = None
    for entry in pkg.entries:
        if entry.filepath and epk_hash in entry.filepath:
            epk_entry = entry
            break

    if not epk_entry:
        print(f"  [ERROR] EPK not found in {bin_path.name}: {epk_hash}")
        print(f"  Available EPKs (first 10):")
        for e in pkg.get_entries_by_ext('.epk')[:10]:
            print(f"    {e.filepath}")
        sys.exit(1)

    # Extract EPK bytes
    epk_data = pkg.read_entry(epk_entry)
    epk_file = out_dir / f"{epk_hash}.epk"
    epk_file.write_bytes(epk_data)
    print(f"  ✓  Extracted: {epk_file} ({len(epk_data)} bytes)")

    # Decrypt
    print(f"  Decrypting ...")
    dec_file = out_dir / f"{epk_hash}.epk_dec"
    try:
        crypto.decrypt(epk_file, dec_file)
        epk_file.unlink()  # remove intermediate encrypted file
        print(f"  ✓  Decrypted: {dec_file}")
        print(f"\nReady to translate: {dec_file}")
        print(f"Run: python fsn-tools.py translate export {dec_file} --out translations/{ks_name}.json")
    except EPKError as e:
        print(f"  ✗  Decrypt failed: {e}")


def add_patch_parser(subparsers):
    p = subparsers.add_parser('patch', help='Build and deploy translation patches')
    sub = p.add_subparsers(dest='patch_cmd', required=True)

    def _add_crypto(parser):
        parser.add_argument('--main-exe', default='keys/main.exe',
                             help='Path to main.exe (default: keys/main.exe)')
        parser.add_argument('--some-key', default='keys/SomeKey.bin',
                             help='Path to SomeKey.bin (default: keys/SomeKey.bin)')

    # patch build
    p_build = sub.add_parser('build', help='Encrypt translated .epk_dec → deployable patch')
    p_build.add_argument('input', help='Directory with translated .epk_dec files')
    p_build.add_argument('--out', default='./my_patch', help='Output patch directory')
    _add_crypto(p_build)
    p_build.set_defaults(func=cmd_patch_build)

    # patch deploy
    p_deploy = sub.add_parser('deploy', help='Install patch to %%LOCALAPPDATA%% (Steam/installed)')
    p_deploy.add_argument('patch_dir', help='Built patch directory')
    p_deploy.add_argument('--localappdata', default=None,
                           help='Override %%LOCALAPPDATA%% path')
    p_deploy.add_argument('--dry-run', action='store_true',
                           help='Show what would be copied without copying')
    p_deploy.set_defaults(func=cmd_patch_deploy)

    # patch launcher
    p_launch = sub.add_parser('launcher', help='Create launch script for cracked/non-Steam versions')
    p_launch.add_argument('patch_dir', help='Built patch directory')
    p_launch.add_argument('--game-exe', required=True,
                           help='Path to fsn2-win64vc14-release.exe')
    p_launch.set_defaults(func=cmd_patch_launcher)

    # patch extract-epk
    p_exepk = sub.add_parser('extract-epk',
                               help='Extract + decrypt an EPK from a FPD .bin in one step')
    p_exepk.add_argument('bin_file', help='FPD .bin file (e.g. patch00m.bin)')
    p_exepk.add_argument('ks_name', help='KS script name (e.g. プロローグ1日目)')
    p_exepk.add_argument('--key', default='keys/decryptKey.bin',
                          help='Path to decryptKey.bin (default: keys/decryptKey.bin)')
    p_exepk.add_argument('--out', default='./work', help='Output directory')
    _add_crypto(p_exepk)
    p_exepk.set_defaults(func=cmd_patch_extract_epk)

    return p
