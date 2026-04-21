#!/usr/bin/env python3
"""
tools/cmd_translate.py — Export and import translations for EPK files

The translation workflow:
    1. export  → Extract Japanese text from .epk_dec → JSON translation file
    2. (human translates the JSON)
    3. import  → Apply translations from JSON back into .epk_dec
    4. Then use 'epk enc' to re-encrypt for deployment

JSON format::
    [
      {
        "ks_name": "プロローグ1日目",
        "epk_hash": "1jftmqc2rr04kclvl0ql71s2ef",
        "entries": [
          {
            "id": "27244",
            "placeholder": "$$$message_0234_0000_0000$$$",
            "original": "那是有如闪电的枪尖。[lr]",
            "translation": ""
          },
          ...
        ]
      }
    ]

Commands:
    export  Export .epk_dec files to a JSON translation file
    import  Apply a filled JSON translation file back to .epk_dec files
    status  Show translation progress for a JSON file

Examples:
    python fsn-tools.py translate export work/*.epk_dec --out translations/prologue.json
    python fsn-tools.py translate import translations/prologue.json --out work/translated/
    python fsn-tools.py translate status translations/prologue.json
"""

import sys
import json
import logging
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.epk import EPKFile
from data.ks_names import HASH_TO_KS_NAME, KS_NAME_TO_HASH


def cmd_translate_export(args):
    """Export .epk_dec files to a JSON translation file."""
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_data = []
    total_strings = 0

    for input_path in args.input:
        p = Path(input_path)
        if not p.exists():
            print(f"[SKIP] Not found: {p}")
            continue

        data = p.read_bytes()
        epk = EPKFile.from_bytes(data)

        raw_stem = p.name.replace('.epk_dec', '').replace('.epk_enc', '')
        # Handle both "HASH.epk_dec" and "root#data#locale#ck#epk#HASH.epk_dec" styles
        stem = raw_stem.split('#')[-1] if '#' in raw_stem else raw_stem
        # Also handle underscore-joined path style
        if '_' in stem and len(stem) != 26:
            for part in reversed(stem.split('_')):
                if len(part) == 26 and part.isalnum():
                    stem = part
                    break
        ks_name = HASH_TO_KS_NAME.get(stem, stem)

        entries = [
            {
                "id": e[0],
                "placeholder": e[1],
                "original": e[2],
                "translation": ""
            }
            for e in epk.entries
        ]

        item = {
            "ks_name": ks_name,
            "epk_hash": stem,
            "source_file": str(p),
            "entry_count": len(entries),
            "entries": entries
        }
        all_data.append(item)
        total_strings += len(entries)
        print(f"  [+] {ks_name}  ({len(entries)} strings)")

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n✓  Exported {total_strings} strings from {len(all_data)} scripts")
    print(f"   → {out_path}")
    print(f"\nNext step: fill in 'translation' fields in the JSON, then run:")
    print(f"   python fsn-tools.py translate import {out_path} --out ./work/translated/")


def cmd_translate_import(args):
    """Apply translations from JSON back to .epk_dec files."""
    json_path = Path(args.input)
    if not json_path.exists():
        print(f"[ERROR] JSON file not found: {json_path}")
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_applied = 0
    total_skipped = 0

    for item in data:
        ks_name = item.get('ks_name', '?')
        epk_hash = item.get('epk_hash', '')
        entries = item.get('entries', [])
        source_file = item.get('source_file', '')

        # Find the source .epk_dec file
        source = None
        if source_file and Path(source_file).exists():
            source = Path(source_file)
        elif epk_hash:
            # Try to find it in common locations
            candidates = [
                Path(f"{epk_hash}.epk_dec"),
                Path(f"work/{epk_hash}.epk_dec"),
                Path(f"extracted/{epk_hash}.epk_dec"),
            ]
            for c in candidates:
                if c.exists():
                    source = c
                    break

        if source is None:
            print(f"[WARN] Source file not found for {ks_name}, skipping")
            print(f"       Expected: {epk_hash}.epk_dec")
            total_skipped += 1
            continue

        # Load original EPK
        epk = EPKFile.from_bytes(source.read_bytes())

        # Build translation dict (only non-empty translations)
        translations = {
            e['placeholder']: e['translation']
            for e in entries
            if e.get('translation', '').strip()
        }

        if not translations:
            print(f"[SKIP] No translations in {ks_name}")
            total_skipped += 1
            continue

        count = epk.replace_all(translations)
        total_applied += count

        # Write output
        out_file = out_dir / f"{epk_hash}.epk_dec"
        out_file.write_bytes(epk.to_bytes())
        print(f"  ✓  {ks_name}: {count}/{len(entries)} strings translated → {out_file.name}")

    print(f"\n✓  Applied {total_applied} translations")
    if total_skipped:
        print(f"   Skipped {total_skipped} scripts (no translations or source not found)")
    print(f"\nNext step: encrypt and deploy:")
    print(f"   python fsn-tools.py patch build {out_dir}/ --main-exe keys/main.exe --some-key keys/SomeKey.bin")


def cmd_translate_status(args):
    """Show translation progress statistics."""
    json_path = Path(args.input)
    if not json_path.exists():
        print(f"[ERROR] Not found: {json_path}")
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Translation Status: {json_path.name}\n")
    print(f"{'Script Name':<40}  {'Done':>6}  {'Total':>6}  {'%':>6}")
    print("-" * 62)

    grand_done = 0
    grand_total = 0

    for item in data:
        ks_name = item.get('ks_name', '?')
        entries = item.get('entries', [])
        done = sum(1 for e in entries if e.get('translation', '').strip())
        total = len(entries)
        pct = (done / total * 100) if total > 0 else 0
        grand_done += done
        grand_total += total

        bar = '█' * int(pct / 10) + '░' * (10 - int(pct / 10))
        print(f"  {ks_name:<38}  {done:>6}  {total:>6}  {pct:>5.1f}%  {bar}")

    print("-" * 62)
    grand_pct = (grand_done / grand_total * 100) if grand_total > 0 else 0
    print(f"  {'TOTAL':<38}  {grand_done:>6}  {grand_total:>6}  {grand_pct:>5.1f}%")


def add_translate_parser(subparsers):
    p = subparsers.add_parser('translate', help='Export / import translation JSON files')
    sub = p.add_subparsers(dest='translate_cmd', required=True)

    # translate export
    p_exp = sub.add_parser('export', help='Export .epk_dec files to JSON')
    p_exp.add_argument('input', nargs='+', help='.epk_dec file(s) to export')
    p_exp.add_argument('--out', required=True, help='Output JSON file path')
    p_exp.set_defaults(func=cmd_translate_export)

    # translate import
    p_imp = sub.add_parser('import', help='Apply JSON translations to .epk_dec files')
    p_imp.add_argument('input', help='JSON translation file')
    p_imp.add_argument('--out', default='./work/translated',
                        help='Output directory for translated .epk_dec files (default: ./work/translated)')
    p_imp.set_defaults(func=cmd_translate_import)

    # translate status
    p_sta = sub.add_parser('status', help='Show translation progress')
    p_sta.add_argument('input', help='JSON translation file')
    p_sta.set_defaults(func=cmd_translate_status)

    return p
