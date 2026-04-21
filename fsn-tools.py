#!/usr/bin/env python3
"""
fsn-tools.py — All-in-one toolkit for FSN Remastered translation modding

Usage:
    python fsn-tools.py <command> [options]

Commands:
    unpack      Extract FPD .bin packages and DAT data containers
    epk         Decrypt / encrypt EPK locale files
    translate   Export / import translation JSON files
    patch       Build and deploy translation patches
    info        Inspect game files and show structure

Quick start:
    1. python fsn-tools.py unpack auto ./obb/pack/ --key keys/decryptKey.bin --out ./extracted/
    2. python fsn-tools.py epk dec --main-exe keys/main.exe --some-key keys/SomeKey.bin
           extracted/patch00m.bin/root#data#epk#1jftmqc2rr04kclvl0ql71s2ef.epk
    3. python fsn-tools.py translate export work/*.epk_dec --out translations/batch1.json
    4. (edit translations/batch1.json — fill in "translation" fields)
    5. python fsn-tools.py translate import translations/batch1.json --out work/translated/
    6. python fsn-tools.py patch build work/translated/ --out my_patch/
    7. python fsn-tools.py patch deploy my_patch/          # Steam
       python fsn-tools.py patch launcher my_patch/ --game-exe path/to/game.exe  # Cracked

Required key files (place in keys/ folder):
    keys/decryptKey.bin   — 65536-byte XOR key for FPD .bin decryption
    keys/main.exe         — Windows binary for EPK encrypt/decrypt
    keys/SomeKey.bin      — 5120-byte EPK crypto key

Run 'python fsn-tools.py --key-info' for details on obtaining key files.
"""

import sys
import logging
import argparse
from pathlib import Path

# Ensure the package root is in the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.cmd_unpack import add_unpack_parser
from tools.cmd_epk import add_epk_parser
from tools.cmd_translate import add_translate_parser
from tools.cmd_patch import add_patch_parser
from tools.cmd_info import add_info_parser


KEY_INFO = """
=====================================================================
 FSN-TOOLS: Key Files Information
=====================================================================

This toolkit needs 3 key files to work. Here's what each one is:

─────────────────────────────────────────────────────────────────────
 1. keys/decryptKey.bin  (65,536 bytes)
─────────────────────────────────────────────────────────────────────
 Used for: Decrypting FPD .bin packages (unpack command)
 What it is: A keystream XOR-ed against the FPD entry table.
 Where to get it:
   • Available in kurikomoe/FSNr_tools repo under keys/
   • OR dump from game memory at offset 0x1409E6500 while the game runs

─────────────────────────────────────────────────────────────────────
 2. keys/main.exe  (Windows binary, ~1.4 MB)
─────────────────────────────────────────────────────────────────────
 Used for: EPK encrypt/decrypt (epk dec, epk enc, patch build)
 What it is: The compiled C++ binary from kurikomoe/FSNr_tools
 Where to get it:
   Option A — Compile from source:
     git clone https://github.com/kurikomoe/FSNr_tools
     g++ --std=c++20 -O2 main.cpp -o main.exe   (Windows/MinGW)
   Option B — Use the pre-compiled release from the repo's releases page
 Note: On Linux, Wine is required (sudo apt install wine)

─────────────────────────────────────────────────────────────────────
 3. keys/SomeKey.bin  (5,120 bytes)
─────────────────────────────────────────────────────────────────────
 Used for: EPK encryption (bundled alongside main.exe)
 What it is: A 5120-byte key used by the EPK crypto algorithm,
             dumped from game process memory at offset 0x1409E6500
 Where to get it:
   • Bundled in the kurikomoe/FSNr_tools release package
   • Must be placed in the SAME directory as main.exe when running

─────────────────────────────────────────────────────────────────────
 Folder structure:
─────────────────────────────────────────────────────────────────────
  fsn-tools/
  ├── fsn-tools.py        ← this script
  ├── keys/
  │   ├── decryptKey.bin  ← needed for unpack
  │   ├── main.exe        ← needed for epk / patch
  │   └── SomeKey.bin     ← needed for epk / patch
  ├── core/
  ├── tools/
  └── data/
=====================================================================
"""


def main():
    parser = argparse.ArgumentParser(
        prog='fsn-tools',
        description='FSN Remastered translation modding toolkit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'python fsn-tools.py <command> --help' for command-specific help."
    )

    parser.add_argument(
        '--key-info',
        action='store_true',
        help='Show information about required key files'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose/debug logging'
    )

    subparsers = parser.add_subparsers(dest='command')

    add_unpack_parser(subparsers)
    add_epk_parser(subparsers)
    add_translate_parser(subparsers)
    add_patch_parser(subparsers)
    add_info_parser(subparsers)

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(levelname)s %(name)s: %(message)s'
    )

    if args.key_info:
        print(KEY_INFO)
        sys.exit(0)

    if not args.command:
        parser.print_help()
        print()
        print("Quick example:")
        print("  python fsn-tools.py info fpd patch00m.bin --key keys/decryptKey.bin")
        sys.exit(0)

    # Dispatch to subcommand
    if hasattr(args, 'func'):
        args.func(args)
    else:
        # Print subcommand help if no sub-subcommand given
        parser.parse_args([args.command, '--help'])


if __name__ == '__main__':
    main()
