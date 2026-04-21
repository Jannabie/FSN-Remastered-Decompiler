#!/usr/bin/env python3
"""
tools/cmd_epk.py — Decrypt / encrypt EPK locale files

EPK files contain the game's dialogue strings in the format:
    DAT
    id=qid::label=str::text=lstr::
    27244::$$$message_0234_0000_0000$$$::那是有如闪电的枪尖。[lr]::

Commands:
    dec     Decrypt one or more .epk files → .epk_dec
    enc     Encrypt one or more .epk_dec files → .epk
    info    Show contents of a .epk or .epk_dec file
    list    List all EPK files in an FPD package with their KS names

Requirements:
    --main-exe    Path to main.exe  (from kurikomoe/FSNr_tools compiled binary)
    --some-key    Path to SomeKey.bin  (5120-byte key dumped from game memory)

Examples:
    python fsn-tools.py epk dec --main-exe tools/main.exe --some-key keys/SomeKey.bin \\
        extracted/patch00m.bin/root#data#epk#1jftmqc2rr04kclvl0ql71s2ef.epk

    python fsn-tools.py epk enc --main-exe tools/main.exe --some-key keys/SomeKey.bin \\
        work/1jftmqc2rr04kclvl0ql71s2ef.epk_dec --out ./output/

    python fsn-tools.py epk info work/1jftmqc2rr04kclvl0ql71s2ef.epk_dec

    python fsn-tools.py epk list extracted/patch00m.bin/
"""

import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.epk import EPKCrypto, EPKFile, EPKError
from core.epk_names import ks_to_epk_hash
from data.ks_names import HASH_TO_KS_NAME


def _get_crypto(args):
    """Create EPKCrypto from args, with clear error if files are missing."""
    main_exe = Path(args.main_exe)
    some_key = Path(args.some_key)

    missing = []
    if not main_exe.exists():
        missing.append(f"main.exe  → {main_exe}")
    if not some_key.exists():
        missing.append(f"SomeKey.bin  → {some_key}")

    if missing:
        print("[ERROR] Required files not found:")
        for m in missing:
            print(f"  ✗  {m}")
        print()
        print("These files are needed for EPK encryption/decryption:")
        print("  main.exe     — compiled from kurikomoe/FSNr_tools (Windows binary)")
        print("  SomeKey.bin  — 5120-byte key file (included with the compiled release)")
        print()
        print("→ Place them in the keys/ folder or specify paths with --main-exe / --some-key")
        sys.exit(1)

    return EPKCrypto(str(main_exe), str(some_key))


def cmd_epk_dec(args):
    crypto = _get_crypto(args)
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for input_path in args.input:
        p = Path(input_path)
        if not p.exists():
            print(f"[SKIP] Not found: {p}")
            continue

        out_path = (out_dir / (p.stem + '.epk_dec')) if out_dir else None
        stem = p.stem  # hash portion of filename
        ks_name = HASH_TO_KS_NAME.get(stem, '?')

        print(f"[DEC] {p.name}  ({ks_name}.ks) ...")
        try:
            result = crypto.decrypt(p, out_path)
            print(f"  ✓  → {result}")
        except EPKError as e:
            print(f"  ✗  {e}")


def cmd_epk_enc(args):
    crypto = _get_crypto(args)
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for input_path in args.input:
        p = Path(input_path)
        if not p.exists():
            print(f"[SKIP] Not found: {p}")
            continue

        # Determine output filename: remove _dec suffix, keep hash name
        stem = p.name.replace('.epk_dec', '').replace('.epk_enc', '')
        out_path = (out_dir / f"{stem}.epk") if out_dir else None
        ks_name = HASH_TO_KS_NAME.get(stem, '?')

        print(f"[ENC] {p.name}  ({ks_name}.ks) ...")
        try:
            result = crypto.encrypt(p, out_path)
            print(f"  ✓  → {result}")
        except EPKError as e:
            print(f"  ✗  {e}")


def cmd_epk_info(args):
    for input_path in args.input:
        p = Path(input_path)
        if not p.exists():
            print(f"[SKIP] Not found: {p}")
            continue

        # If it's encrypted, we can't read it without crypto
        if p.suffix == '.epk' and not p.name.endswith('.epk_dec'):
            print(f"[INFO] {p.name} — encrypted (use 'epk dec' first to inspect)")
            continue

        data = p.read_bytes()
        epk = EPKFile.from_bytes(data)
        stem = p.name.replace('.epk_dec', '')
        ks_name = HASH_TO_KS_NAME.get(stem, '?')

        print(f"[INFO] {p.name}")
        print(f"  Script:  {ks_name}.ks")
        print(f"  Entries: {len(epk.entries)}")
        if epk.entries:
            print(f"  Sample entries:")
            for entry in epk.entries[:5]:
                entry_id, placeholder, text, extra = entry
                short_text = text[:60] + '...' if len(text) > 60 else text
                print(f"    [{entry_id}] {placeholder}")
                print(f"         → {short_text}")
        print()


SPECIAL_EPK_NAMES = {
    "uistring":      "UI Strings (menus, buttons, labels)",
    "statictext":    "Static Text (title screen, chapter names)",
    "uiconst":       "UI Constants",
    "bgm_flag":      "BGM Track Names / Flags",
    "correct_data":  "Choice / Answer Data",
    "picture_data":  "CG Picture References",
    "timeline_text": "Timeline Text (flowchart labels)",
    "timeline_data": "Timeline Data",
    "weapon_data":   "Noble Phantasm / Weapon Descriptions",
    "servant_data":  "Servant Profile Data",
}


def cmd_epk_list(args):
    """List all EPK files in a directory, showing KS name mappings."""
    d = Path(args.dir)
    if not d.exists():
        print(f"[ERROR] Not found: {d}")
        sys.exit(1)

    epk_files = sorted(d.rglob('*.epk'))
    if not epk_files:
        print(f"No .epk files found in {d}")
        return

    # Group by locale
    ck_epks = []
    us_epks = []
    base_epks = []
    other_epks = []

    for epk in epk_files:
        name = epk.name  # may be "root#data#locale#ck#epk#HASH.epk"
        # Extract locale and stem from the full path name
        parts = epk.stem.split('#')  # ["root","data","locale","ck","epk","HASH"]
        stem = parts[-1]

        if 'locale#ck' in epk.stem:
            ck_epks.append((stem, epk))
        elif 'locale#us' in epk.stem:
            us_epks.append((stem, epk))
        elif 'data#epk' in epk.stem:
            base_epks.append((stem, epk))
        else:
            other_epks.append((stem, epk))

    def print_group(label, items):
        if not items:
            return
        print(f"\n  [{label}] ({len(items)} files)")
        print(f"  {'Stem / Hash':<34}  {'Script / Description':<42}  {'Size':>7}")
        print("  " + "-" * 86)
        known = 0
        for stem, epk in sorted(items):
            ks_name = HASH_TO_KS_NAME.get(stem) or SPECIAL_EPK_NAMES.get(stem)
            size_kb = epk.stat().st_size / 1024
            if ks_name:
                known += 1
                print(f"  {stem:<34}  {ks_name:<42}  {size_kb:>5.1f}KB")
            else:
                print(f"  {stem:<34}  {'(unknown)':<42}  {size_kb:>5.1f}KB  ←")
        return known

    total = len(epk_files)
    print(f"\nEPK files in: {d}  ({total} total)\n")
    print_group("locale/ck  — Chinese strings (main dialogue)", ck_epks)
    print_group("locale/us  — English strings", us_epks)
    print_group("base epk   — Shared/global data", base_epks)
    if other_epks:
        print_group("other", other_epks)

    print(f"\nNote: 'locale/ck' EPKs are the main translation target (Chinese → your language)")
    print(f"      'locale/us' EPKs may also need translation for English UI elements")


def add_epk_parser(subparsers):
    p = subparsers.add_parser('epk', help='Decrypt / encrypt EPK locale files')
    sub = p.add_subparsers(dest='epk_cmd', required=True)

    def _add_crypto_args(parser):
        parser.add_argument('--main-exe', default='keys/main.exe',
                             help='Path to main.exe (default: keys/main.exe)')
        parser.add_argument('--some-key', default='keys/SomeKey.bin',
                             help='Path to SomeKey.bin (default: keys/SomeKey.bin)')

    # epk dec
    p_dec = sub.add_parser('dec', help='Decrypt .epk → .epk_dec')
    p_dec.add_argument('input', nargs='+', help='.epk file(s) to decrypt')
    p_dec.add_argument('--out', default=None, help='Output directory')
    _add_crypto_args(p_dec)
    p_dec.set_defaults(func=cmd_epk_dec)

    # epk enc
    p_enc = sub.add_parser('enc', help='Encrypt .epk_dec → .epk')
    p_enc.add_argument('input', nargs='+', help='.epk_dec file(s) to encrypt')
    p_enc.add_argument('--out', default=None, help='Output directory')
    _add_crypto_args(p_enc)
    p_enc.set_defaults(func=cmd_epk_enc)

    # epk info
    p_info = sub.add_parser('info', help='Show contents of a decrypted EPK file')
    p_info.add_argument('input', nargs='+', help='.epk_dec file(s) to inspect')
    p_info.set_defaults(func=cmd_epk_info)

    # epk list
    p_list = sub.add_parser('list', help='List EPK files in a directory with KS name mapping')
    p_list.add_argument('dir', help='Directory to scan for .epk files')
    p_list.set_defaults(func=cmd_epk_list)

    return p
