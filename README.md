# fsn-tools

All-in-one toolkit for translating **Fate/Stay Night Remastered** — works with Steam, cracked, and any version.

Pure Python 3.8+, no external dependencies.
Runs on Windows natively; Linux/macOS needs Wine for EPK operations.

---

## Overview

FSN Remastered stores dialogue in **EPK files** (encrypted locale packages) inside **FPD `.bin` archives**.

```
pack00m.bin  (main game pack, 494 MB, 728 scripts)
patch00m.bin (patch pack, 59 MB, 301 scripts)
      │
      ▼  unpack  ← needs decryptKey.bin
  extracted/  [*.ks scripts + *.epk locale files]
      │
      ▼  epk dec  ← needs main.exe + SomeKey.bin
  HASH.epk_dec   [plain UTF-8 text, editable]
      │
      ▼  translate export → edit JSON → translate import
  HASH_translated.epk_dec
      │
      ▼  patch build  ← needs main.exe + SomeKey.bin
  my_patch/root/data/locale/ck/epk/HASH.epk
      │
      ▼  patch deploy  (Steam)
      or patch launcher  (cracked)
Game reads translated text ✓
```

---

## Required Key Files

Place these three files in the `keys/` folder:

| File | Size | Used for | Where to get |
|------|------|----------|-------------|
| `keys/decryptKey.bin` | 65 536 B | Unpack FPD `.bin` archives | `kurikomoe/FSNr_tools` repo → `keys/` folder |
| `keys/main.exe` | ~1.4 MB | EPK decrypt / encrypt | Compile from `kurikomoe/FSNr_tools` (below) |
| `keys/SomeKey.bin` | 5 120 B | EPK crypto seed | Bundled with the `main.exe` release |

**Compile main.exe (Windows / MinGW):**
```bash
git clone https://github.com/kurikomoe/FSNr_tools
cd FSNr_tools
g++ --std=c++20 -O2 main.cpp -o main.exe
# copy main.exe AND keys/SomeKey.bin into fsn-tools/keys/
```

**Linux — install Wine:**
```bash
sudo apt install wine    # Debian/Ubuntu
sudo pacman -S wine      # Arch
```

Run `python fsn-tools.py --key-info` for detailed instructions on each file.

---

## Quick Start

```bash
# Show what is inside a pack file
python fsn-tools.py info fpd pack00m.bin --key keys/decryptKey.bin

# Extract everything from the game's obb/pack/ folder
python fsn-tools.py unpack auto obb/pack/ \
    --key keys/decryptKey.bin \
    --out ./extracted/

# List all EPK files with human-readable script names
python fsn-tools.py epk list extracted/pack00m.bin/

# Decrypt an EPK for a specific scene
python fsn-tools.py patch extract-epk pack00m.bin "プロローグ1日目" \
    --key keys/decryptKey.bin \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./work/

# Export to JSON for translation
python fsn-tools.py translate export work/*.epk_dec \
    --out translations/batch1.json

# --- edit translations/batch1.json, fill "translation" fields ---

# Import translations back
python fsn-tools.py translate import translations/batch1.json \
    --out work/translated/

# Check progress
python fsn-tools.py translate status translations/batch1.json

# Build patch
python fsn-tools.py patch build work/translated/ \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out my_patch/

# Deploy — Steam / installed version (no game files modified)
python fsn-tools.py patch deploy my_patch/

# Deploy — cracked / portable version
python fsn-tools.py patch launcher my_patch/ \
    --game-exe "C:\Games\Fate\fsn2-win64vc14-release.exe"
```

---

## Command Reference

```
fsn-tools.py  [--verbose]  [--key-info]

  unpack
    fpd   <file.bin> [file.bin ...]  --key <decryptKey.bin>  --out <dir>
    dat   <pack_dir>                                          --out <dir>
    auto  <pack_dir>                 --key <decryptKey.bin>  --out <dir>

  epk
    dec   <file.epk> [...]  --main-exe <exe>  --some-key <key>  [--out <dir>]
    enc   <file.epk_dec> [...]  --main-exe <exe>  --some-key <key>  [--out <dir>]
    info  <file.epk_dec> [...]
    list  <directory>

  translate
    export  <file.epk_dec> [...]  --out <out.json>
    import  <translations.json>   --out <dir>
    status  <translations.json>

  patch
    build        <translated_dir>  --main-exe <exe>  --some-key <key>  --out <patch_dir>
    deploy       <patch_dir>       [--localappdata <path>]  [--dry-run]
    launcher     <patch_dir>       --game-exe <path/to/exe>
    extract-epk  <file.bin>  <"script name">  --key <decryptKey.bin>
                                              --main-exe <exe>  --some-key <key>
                                              --out <dir>

  info
    fpd   <file.bin>  --key <decryptKey.bin>  [--type epk|ks|png]  [-v]
    epk   [--route saber|rin|sakura|prologue]
    hash  <"script name"> [...]
```

Default paths for `--main-exe` and `--some-key` are `keys/main.exe` and `keys/SomeKey.bin`.

---

## Troubleshooting

### `main.exe failed (code 3221225781)`

**0xC0000135** is the Windows "DLL not found" status code.
It has two causes in this context:

**Cause A — Wrong filename stem (now fixed in this toolkit)**

When FPD extracts an EPK, the file is named with the full path using `#` as separator:
```
root#data#locale#ck#epk#HASH.epk
```
`main.exe` reads the stem from `argv[1]` to derive the crypto key.
If it receives the full name, the stem becomes `root#data#locale#ck#epk#HASH` (46 chars)
instead of just `HASH` (26 chars). Wrong stem → wrong keystream → crash.

This toolkit now renames the file to `HASH.epk` in an isolated temp directory
before calling `main.exe`, so this error no longer occurs.

If you call `main.exe` manually, always rename the file first:
```
# WRONG
main.exe dec root#data#locale#ck#epk#HASH.epk

# CORRECT
copy root#data#locale#ck#epk#HASH.epk HASH.epk
main.exe dec HASH.epk
```

**Cause B — Missing Visual C++ runtime (Windows 7 / 8.1 only)**

Windows 10+ already includes the required runtime. For older Windows:
- Install [Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- Or Windows Update KB2999226

**Cause C — Wine not installed (Linux)**

```bash
sudo apt install wine
```

---

## Game File Structure

```
obb/pack/
├── fileinfo_*.txt         ← index files for .dat containers
├── *.dat                  ← raw asset containers (images, video, etc.)
├── pack00m.bin            ← MAIN FPD pack: 6805 entries (728 KS + 2188 EPK + assets)
├── patch00m.bin           ← Patch FPD: 628 entries (subset)
├── patch00d.bin           ← Patch FPD: UI graphics only
└── movie.dat              ← OP movie files
```

### EPK locale groups inside pack00m.bin

| Path | Count | Purpose |
|------|-------|---------|
| `root/data/locale/ck/epk/` | 727 | **Chinese strings — main translation target** |
| `root/data/locale/us/epk/` | 727 | English strings (UI + some scenes) |
| `root/data/epk/` | 734 | Base/fallback copies + special EPKs |

Special named EPKs (not script-specific):

| Name | Contents |
|------|----------|
| `uistring` | Menu labels, buttons, system text |
| `statictext` | Title screen, chapter names |
| `uiconst` | UI constants |
| `timeline_text` | Flowchart / timeline labels |
| `weapon_data` | Noble Phantasm descriptions |
| `servant_data` | Servant profile text |
| `correct_data` | Choice / answer data |
| `bgm_flag` | BGM track names |

---

## EPK Text Format

After decryption, EPK files are plain UTF-8 text:

```
DAT
id=qid::label=str::text=lstr::
27244::$$$message_0234_0000_0000$$$::那是有如闪电的枪尖。[lr]::
27245::$$$message_0234_0000_0001$$$::迎面刺来的枪尖试图贯穿心脏。[lr]::
```

Fields: `id :: $$$placeholder$$$ :: text :: [extra markup]`

**Markup tags — preserve these when translating:**

| Tag | Meaning |
|-----|---------|
| `[lr]` | Line break + wait for click |
| `[l]` | Wait for click |
| `[p]` | Page break |
| `[r]` | Newline |
| `[ruby text="X"]` | Furigana / ruby annotation |

**Translation JSON format:**
```json
[
  {
    "ks_name": "プロローグ1日目",
    "epk_hash": "1jftmqc2rr04kclvl0ql71s2ef",
    "entries": [
      {
        "id": "27244",
        "placeholder": "$$$message_0234_0000_0000$$$",
        "original": "那是有如闪电的枪尖。[lr]",
        "translation": "It was a spear tip like a bolt of lightning.[lr]"
      }
    ]
  }
]
```

Leave `"translation"` empty to keep the original text unchanged.

---

## FPD Binary Format Reference

```
Offset  Size  Type      Field
──────  ────  ────────  ────────────────────────────────
0x00    4     char[4]   Magic: "FPD\x00"
0x04    4     u32 BE    Version (= 2)
0x08    8     u64 BE    Entry count
0x10    8     u64 BE    Entry block total size (includes 56-byte header)
0x18    32    —         Reserved

Entry block (XOR-decrypted with decryptKey.bin):
  Each entry = 32 bytes:
  +0x00  u64 BE  filepath string offset (into string table)
  +0x08  u64 BE  data offset (from start of data section)
  +0x10  u64 BE  stored size (compressed)
  +0x18  u64 BE  uncompressed size (0 = data is NOT compressed)

String table (zlib-compressed, follows the entries):
  Null-terminated UTF-8 strings

Data section (follows the entry block):
  Per-entry: XOR with decryptKey.bin, then optionally zlib-decompress
```

---

## EPK Hash Algorithm

KiriKiri script names hash to their EPK filename:

```python
import hashlib, string

_ALPHABET = string.digits + string.ascii_lowercase

def ks_to_epk_hash(name: str) -> str:
    digest = hashlib.md5(name.encode('utf-8')).digest()
    bits   = int.from_bytes(digest, 'big')
    result = ''
    for i in range(3, 3 + 128, 5):
        result += _ALPHABET[(bits << i >> 128) & 0x1F]
    return result

# "プロローグ1日目" → "1jftmqc2rr04kclvl0ql71s2ef"
# "セイバーエピローグ" → "46hemeh77jjsiv82vkljdobkr7"
```

Algorithm credit: @tea (kurikomoe/FSNr_tools).

---

## Deploy Without Modifying Game Files

The game reads override data from:
```
%LOCALAPPDATA%\typemoon\fsn2\data\
```

Put your patched EPK files there with the same directory structure:
```
%LOCALAPPDATA%\typemoon\fsn2\data\root\data\locale\ck\epk\HASH.epk
```

`patch deploy` does this automatically.

For cracked / portable installs, `patch launcher` creates a batch file that
sets `%LOCALAPPDATA%` to a subfolder of your patch before launching the game.
The original game files are **never touched**.

---

## Credits

- **kurikomoe/FSNr_tools** — EPK crypto (`main.exe`, `SomeKey.bin`), unpack scripts, bonus redirect technique
- **DaZombieKiller/FatePackageManager** — FPD format documentation
- **Jannabie/FSN_Decompiler** — KS script format reference
- **@tea** — EPK filename hash algorithm
