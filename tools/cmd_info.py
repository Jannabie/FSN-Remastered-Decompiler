#!/usr/bin/env python3
"""
tools/cmd_info.py — Inspect game files and show their structure

Commands:
    fpd     Show contents of an FPD .bin package
    epk     Show EPK hash → KS name mapping for all known scripts
    hash    Compute the EPK hash for a given KS script name

Examples:
    python fsn-tools.py info fpd patch00m.bin --key keys/decryptKey.bin
    python fsn-tools.py info epk
    python fsn-tools.py info hash プロローグ1日目
"""

import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.fpd import FPDPackage
from core.epk_names import ks_to_epk_hash
from data.ks_names import ALL_KS_NAMES, HASH_TO_KS_NAME, KS_NAME_TO_HASH


def cmd_info_fpd(args):
    key_path = Path(args.key)
    if not key_path.exists():
        print(f"[ERROR] Key file not found: {key_path}")
        print("  → Need keys/decryptKey.bin to read FPD files")
        sys.exit(1)

    dec_key = key_path.read_bytes()
    p = Path(args.input)
    if not p.exists():
        print(f"[ERROR] File not found: {p}")
        sys.exit(1)

    print(f"[FPD] {p.name}  ({p.stat().st_size/1024/1024:.1f} MB)")
    pkg = FPDPackage(str(p), dec_key)

    ext_count = Counter()
    for e in pkg.entries:
        ext = e.filepath.rsplit('.', 1)[-1] if '.' in e.filepath else '?'
        ext_count[ext] += 1

    print(f"  Version:  {pkg.version}")
    print(f"  Entries:  {pkg.entry_count}")
    print(f"  Types:")
    for ext, count in ext_count.most_common():
        print(f"    .{ext:<8}  {count}")

    if args.verbose:
        print(f"\n  All entries:")
        for e in pkg.entries:
            print(f"    {e.filepath}  [{e.size} bytes]")
    elif args.type:
        filt = args.type if args.type.startswith('.') else '.' + args.type
        filtered = [e for e in pkg.entries if e.filepath.endswith(filt)]
        print(f"\n  {filt} files ({len(filtered)}):")
        for e in filtered:
            stem = e.filepath.rsplit('/', 1)[-1].rsplit('.', 1)[0]
            ks_name = HASH_TO_KS_NAME.get(stem, '')
            mapped = f"  ← {ks_name}.ks" if ks_name else ''
            print(f"    {e.filepath}  [{e.size} bytes]{mapped}")


def cmd_info_epk(args):
    route_filter = args.route.lower() if args.route else None

    print(f"All known EPK files ({len(ALL_KS_NAMES)} total):\n")
    print(f"{'KS Script Name':<45}  {'EPK Hash'}")
    print("-" * 80)

    routes = {
        'saber': 'セイバー',
        'rin': '凛',
        'sakura': '桜',
        'prologue': 'プロローグ',
        'other': None,
    }

    for name in sorted(ALL_KS_NAMES):
        if route_filter:
            route_jp = routes.get(route_filter, route_filter)
            if route_jp and route_jp not in name:
                continue
        h = KS_NAME_TO_HASH[name]
        print(f"  {name:<43}  {h}")

    print()
    print(f"Total: {len(ALL_KS_NAMES)} scripts")


def cmd_info_hash(args):
    for name in args.name:
        h = ks_to_epk_hash(name)
        print(f"  {name}")
        print(f"  → {h}.epk")
        print(f"  → root/data/locale/ck/epk/{h}.epk")
        print()


def add_info_parser(subparsers):
    p = subparsers.add_parser('info', help='Inspect game files and show structure')
    sub = p.add_subparsers(dest='info_cmd', required=True)

    # info fpd
    p_fpd = sub.add_parser('fpd', help='Show contents of an FPD .bin package')
    p_fpd.add_argument('input', help='FPD .bin file')
    p_fpd.add_argument('--key', default='keys/decryptKey.bin',
                        help='Path to decryptKey.bin (default: keys/decryptKey.bin)')
    p_fpd.add_argument('-v', '--verbose', action='store_true', help='Show all file paths')
    p_fpd.add_argument('--type', default=None,
                        help='Filter by file type (e.g. --type epk)')
    p_fpd.set_defaults(func=cmd_info_fpd)

    # info epk
    p_epk = sub.add_parser('epk', help='Show all known EPK hash → KS name mappings')
    p_epk.add_argument('--route', default=None,
                        help='Filter by route: saber, rin, sakura, prologue')
    p_epk.set_defaults(func=cmd_info_epk)

    # info hash
    p_hash = sub.add_parser('hash', help='Compute EPK hash for KS script name(s)')
    p_hash.add_argument('name', nargs='+', help='KS script name(s) to hash')
    p_hash.set_defaults(func=cmd_info_hash)

    return p
