# fsn-tools

All-in-one toolkit for translating **Fate/Stay Night Remastered** (FSN Steam / non-Steam).

No external dependencies — pure Python 3.8+ stdlib.  
Works on Windows natively, and on Linux with Wine for EPK operations.

---

## What This Does

The game stores all dialogue text in **EPK files** (encrypted KiriKiri locale packages)  
inside **FPD .bin packages** (encrypted+compressed archives).

This toolkit lets you:

1. **Unpack** `.bin` / `.dat` files to get the raw EPK files
2. **Decrypt** EPK → plain text `DAT` format you can read and edit
3. **Export** strings to a JSON file for translation
4. **Import** translated strings back into the EPK
5. **Encrypt** back to `.epk`
6. **Deploy** to the game — without touching any original files

---

## Required Key Files

Place these in the `keys/` folder before use.

| File | Size | Used for | Where to get |
|------|------|----------|--------------|
| `keys/decryptKey.bin` | 65,536 bytes | Unpack FPD `.bin` files | kurikomoe/FSNr_tools repo (`keys/` folder) |
| `keys/main.exe` | ~1.4 MB | EPK encrypt/decrypt | kurikomoe/FSNr_tools (compile `main.cpp`) |
| `keys/SomeKey.bin` | 5,120 bytes | EPK crypto | Bundled with main.exe release |

**To compile main.exe yourself (Windows/MinGW):**
```bash
git clone https://github.com/kurikomoe/FSNr_tools
cd FSNr_tools
g++ --std=c++20 -O2 main.cpp -o main.exe
# Copy main.exe and keys/SomeKey.bin to fsn-tools/keys/
```

**On Linux** — install Wine for EPK operations:
```bash
sudo apt install wine
```

Run `python fsn-tools.py --key-info` for full details.

---

## Installation

```bash
git clone <this-repo>
cd fsn-tools
# Python 3.8+ required, no pip install needed
python fsn-tools.py --help
```

---

## Directory Structure

```
fsn-tools/
├── fsn-tools.py            ← main entry point (run this)
├── keys/
│   ├── decryptKey.bin      ← FPD XOR key  (65536 bytes)
│   ├── main.exe            ← EPK crypto binary
│   └── SomeKey.bin         ← EPK crypto key  (5120 bytes)
├── core/
│   ├── fpd.py              ← FPD .bin parser/extractor
│   ├── epk.py              ← EPK decrypt/encrypt wrapper
│   ├── epk_names.py        ← KS name ↔ EPK hash resolver
│   ├── dat_pack.py         ← DAT pack extractor (fileinfo_*.txt)
│   └── patch_builder.py    ← Patch build/deploy logic
├── data/
│   └── ks_names.py         ← All 301 KS script names (embedded)
└── tools/
    ├── cmd_unpack.py
    ├── cmd_epk.py
    ├── cmd_translate.py
    ├── cmd_patch.py
    └── cmd_info.py
```

---

## Complete Workflow

### Step 1 — Unpack the game

```bash
# Extract everything from the game's obb/pack/ folder
python fsn-tools.py unpack auto "C:\Games\Fate\obb\pack\" \
    --key keys/decryptKey.bin \
    --out ./extracted/
```

This produces:
- `extracted/patch00m.bin/` — contains `.ks` scripts + `.epk` locale files
- `extracted/patch00d.bin/` — contains UI assets

### Step 2 — Inspect what's there

```bash
# List all EPK files with their script names
python fsn-tools.py epk list extracted/patch00m.bin/

# Show full FPD contents
python fsn-tools.py info fpd extracted/patch00m.bin --key keys/decryptKey.bin --type epk
```

### Step 3 — Decrypt an EPK (or all of them)

```bash
# Decrypt a single EPK (prologue day 1)
python fsn-tools.py epk dec \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    extracted/patch00m.bin/root#data#epk#1jftmqc2rr04kclvl0ql71s2ef.epk \
    --out ./work/

# Or one-step: extract + decrypt by script name
python fsn-tools.py patch extract-epk \
    extracted/patch00m.bin/../patch00m.bin \
    "プロローグ1日目" \
    --key keys/decryptKey.bin \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./work/
```

### Step 4 — Export for translation

```bash
python fsn-tools.py translate export work/*.epk_dec --out translations/batch1.json
```

The JSON looks like:
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
        "translation": ""
      }
    ]
  }
]
```

### Step 5 — Translate

Edit `translations/batch1.json` and fill in the `"translation"` fields.
Keep markup tags like `[lr]`, `[l]`, `[p]`, `[r]` intact.

### Step 6 — Import translations back

```bash
python fsn-tools.py translate import translations/batch1.json --out work/translated/
```

Check progress:
```bash
python fsn-tools.py translate status translations/batch1.json
```

### Step 7 — Build the patch

```bash
python fsn-tools.py patch build work/translated/ \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./my_patch/
```

### Step 8 — Deploy

**Steam / installed version** (no game file modification):
```bash
python fsn-tools.py patch deploy my_patch/
```
> Copies to `%LOCALAPPDATA%\typemoon\fsn2\data\`. Game reads translated EPKs automatically.

**Cracked / non-Steam version:**
```bash
python fsn-tools.py patch launcher my_patch/ \
    --game-exe "C:\Games\Fate\fsn2-win64vc14-release.exe"
```
> Creates `my_patch/launch_with_patch.bat` — double-click to launch with patch.  
> `LOCALAPPDATA` is redirected so the game finds your translations without modifying anything.

---

## EPK File Format Reference

After decryption, EPK files are plain UTF-8 text:

```
DAT\r\n
id=qid::label=str::text=lstr::\r\n
27244::$$$message_0234_0000_0000$$$::那是有如闪电的枪尖。[lr]::\r\n
27245::$$$message_0234_0000_0001$$$::迎面刺来的枪尖试图贯穿心脏。[lr]::\r\n
```

Fields: `ID :: placeholder_tag :: text_content :: [markup]`

Placeholder tags follow the pattern: `$$$message_SCENE_BLOCK_LINE$$$`

### Markup tags to preserve

| Tag | Meaning |
|-----|---------|
| `[lr]` | Line break + wait for click |
| `[l]` | Wait for click |
| `[p]` | Page break |
| `[r]` | Newline only |
| `[ruby text="..."]` | Ruby/furigana |

---

## FPD .bin Format Reference

```
Magic:   FPD\x00  (4 bytes)
Version: uint32 big-endian  (= 2)
Entries: uint64 big-endian  (file count)
BlkSize: uint64 big-endian  (entry block size including 56-byte header)
Padding: 32 bytes
--- Entry block (XOR'd with decryptKey.bin, 32 bytes per entry) ---
  filepath_str_offset: uint64 BE
  data_offset:         uint64 BE
  data_size:           uint64 BE  (compressed)
  uncompressed_size:   uint64 BE  (0 = not compressed)
--- String table (zlib compressed, follows entries) ---
  null-terminated UTF-8 strings
--- Data section ---
  XOR'd (and optionally zlib-compressed) file data
```

---

## EPK Hash Algorithm

KS script names are hashed to produce EPK filenames:

```python
import hashlib, string
_ALPHABET = string.digits + string.ascii_lowercase

def ks_to_epk_hash(name: str) -> str:
    digest = hashlib.md5(name.encode('utf-8')).digest()
    bits = int.from_bytes(digest, 'big')
    result = ''
    for i in range(3, 3 + 128, 5):
        result += _ALPHABET[(bits << i >> 128) & 0x1F]
    return result

# "プロローグ1日目" → "1jftmqc2rr04kclvl0ql71s2ef"
```

Algorithm credit: @tea (from kurikomoe/FSNr_tools).

---

## Credits

- **kurikomoe/FSNr_tools** — EPK crypto binary (`main.exe`), key files, EPK hash algorithm
- **DaZombieKiller/FatePackageManager** — FPD format documentation
- **@tea** — EPK filename hashing algorithm

---

## Notes

- The `keys/` folder is gitignored — never commit `decryptKey.bin`, `SomeKey.bin`, or `main.exe`
- EPK names in the game use the `root/data/locale/ck/epk/` path for the Chinese locale strings  
  (used as the main string store regardless of display language)
- The game's `obb/pack/` folder naming is a leftover from the Android/mobile port — it's PC/Steam
