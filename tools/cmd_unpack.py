#!/usr/bin/env python3
"""
tools/cmd_unpack.py — Extract FPD .bin packages and DAT pack files

Commands:
    fpd    Extract a single FPD .bin file  (needs decryptKey.bin)
    dat    Extract from fileinfo_*.txt / .dat containers  (no key needed)
    auto   Auto-detect and extract everything in a pack/ folder

Examples:
    python fsn-tools.py unpack fpd patch00m.bin --key keys/decryptKey.bin --out ./extracted/
    python fsn-tools.py unpack dat ./obb/pack/ --out ./extracted/
    python fsn-tools.py unpack auto ./obb/pack/ --key keys/decryptKey.bin --out ./extracted/
"""

import sys
import logging
import argparse
from pathlib import Path

# Allow running standalone or as part of package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.fpd import FPDPackage
from core.dat_pack import DATPackUnpacker


def cmd_unpack_fpd(args):
    key = Path(args.key)
    if not key.exists():
        print(f"[ERROR] Key file not found: {key}")
        print("  → You need: keys/decryptKey.bin")
        print("  → This file is a 65536-byte XOR key dumped from the game process.")
        sys.exit(1)

    dec_key = key.read_bytes()
    inputs = args.input if isinstance(args.input, list) else [args.input]

    for input_path in inputs:
        p = Path(input_path)
        if not p.exists():
            print(f"[SKIP] Not found: {p}")
            continue

        print(f"[FPD] Extracting: {p.name} ...")
        try:
            pkg = FPDPackage(str(p), dec_key)
            count = pkg.extract_all(args.out)
            print(f"  ✓  {count} files → {args.out}/{p.name}/")

            # Print summary
            exts = {}
            for e in pkg.entries:
                ext = e.filepath.rsplit('.', 1)[-1] if '.' in e.filepath else '?'
                exts[ext] = exts.get(ext, 0) + 1
            for ext, n in sorted(exts.items(), key=lambda x: -x[1]):
                print(f"       .{ext}: {n}")
        except Exception as ex:
            print(f"  ✗  Failed: {ex}")


def cmd_unpack_dat(args):
    pack_dir = Path(args.input)
    if not pack_dir.is_dir():
        print(f"[ERROR] Not a directory: {pack_dir}")
        sys.exit(1)

    print(f"[DAT] Scanning {pack_dir} ...")
    unpacker = DATPackUnpacker(str(pack_dir), args.out)
    total = unpacker.load_index()
    print(f"  Found {total} indexed files")
    extracted = unpacker.extract_all(verify_md5=not args.no_verify)
    print(f"  ✓  {extracted} files → {args.out}/")


def cmd_unpack_auto(args):
    pack_dir = Path(args.input)
    key_path = Path(args.key) if args.key else None

    print(f"[AUTO] Scanning {pack_dir} ...")

    # Step 1: Extract DAT (fileinfo_*.txt based)
    fileinfos = list(pack_dir.glob("fileinfo_*.txt"))
    if fileinfos:
        print(f"  Found {len(fileinfos)} fileinfo files → extracting DAT packs")
        unpacker = DATPackUnpacker(str(pack_dir), args.out)
        total = unpacker.load_index()
        extracted = unpacker.extract_all(verify_md5=not args.no_verify)
        print(f"  ✓  DAT: {extracted} files extracted")
    else:
        print("  No fileinfo_*.txt files found, skipping DAT extraction")

    # Step 2: Extract FPD .bin files
    bin_files = list(pack_dir.glob("*.bin"))
    if bin_files and key_path:
        if not key_path.exists():
            print(f"  [WARN] Key not found: {key_path} — skipping FPD extraction")
        else:
            dec_key = key_path.read_bytes()
            for bin_file in bin_files:
                try:
                    pkg = FPDPackage(str(bin_file), dec_key)
                    count = pkg.extract_all(args.out)
                    print(f"  ✓  FPD {bin_file.name}: {count} files")
                except Exception as ex:
                    print(f"  ✗  FPD {bin_file.name}: {ex}")
    elif bin_files and not key_path:
        print(f"  Found {len(bin_files)} .bin files but --key not provided → skipping FPD extraction")
        print("  → Provide --key keys/decryptKey.bin to extract them")


def add_unpack_parser(subparsers):
    p = subparsers.add_parser('unpack', help='Extract FPD .bin and DAT pack files')
    sub = p.add_subparsers(dest='unpack_cmd', required=True)

    # unpack fpd
    p_fpd = sub.add_parser('fpd', help='Extract FPD .bin file')
    p_fpd.add_argument('input', nargs='+', help='FPD .bin file(s)')
    p_fpd.add_argument('--key', required=True,
                        help='Path to decryptKey.bin (65536-byte XOR key)')
    p_fpd.add_argument('--out', default='./extracted',
                        help='Output directory (default: ./extracted)')
    p_fpd.set_defaults(func=cmd_unpack_fpd)

    # unpack dat
    p_dat = sub.add_parser('dat', help='Extract DAT pack files via fileinfo_*.txt')
    p_dat.add_argument('input', help='Path to the pack/ folder containing fileinfo_*.txt and *.dat')
    p_dat.add_argument('--out', default='./extracted',
                        help='Output directory (default: ./extracted)')
    p_dat.add_argument('--no-verify', action='store_true', help='Skip MD5 verification')
    p_dat.set_defaults(func=cmd_unpack_dat)

    # unpack auto
    p_auto = sub.add_parser('auto', help='Auto-extract everything in a pack/ folder')
    p_auto.add_argument('input', help='Path to the pack/ folder')
    p_auto.add_argument('--key', default=None,
                         help='Path to decryptKey.bin (needed for .bin files)')
    p_auto.add_argument('--out', default='./extracted',
                         help='Output directory (default: ./extracted)')
    p_auto.add_argument('--no-verify', action='store_true', help='Skip MD5 verification')
    p_auto.set_defaults(func=cmd_unpack_auto)

    return p
