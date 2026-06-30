# Fuzz Inc. — Fate/Stay Night Remastered Translation Guide

An all-in-one toolkit for translating **Fate/Stay Night Remastered** (Steam or crack).

Pure Python 3.8+, no external dependencies. Native on Windows — Linux/macOS needs Wine for EPK operations.

---

## Proof of Concept

| Screenshot |
|:---:|
| ![Proof of successful script modification](https://i.imgur.com/q9K7bpr.png) |
| *In-game text successfully changed via patch build + deploy* |

---

## Overview

FSN Remastered stores dialogue in **EPK** (encrypted locale packages) files bundled inside **FPD `.bin`** archives.

```
obb/pack00m.bin  (main pack, 494 MB, 728 scripts)
obb/patch00m.bin (patch pack, 59 MB, 301 scripts)
      │
      ▼  unpack  ← needs decryptKey.bin
  extracted/  [*.ks scripts + *.epk locale files]
      │
      ▼  epk dec  ← needs main.exe + SomeKey.bin
  HASH.epk_dec   [plain UTF-8 text, can be edited directly]
      │
      ▼  translate export → edit JSON → translate import
  HASH_translated.epk_dec
      │
      ▼  patch build  ← needs main.exe + SomeKey.bin
  my_patch/root/data/locale/ck/epk/HASH.epk
      │
      ▼  patch deploy  (Steam)
      or patch launcher  (crack / portable)
Game reads the translated text ✓
```

---

## Requirements

- Python 3.8+
- Windows (native) **or** Linux/macOS with Wine

**Install Wine (Linux):**
```bash
sudo apt install wine       # Debian/Ubuntu
sudo pacman -S wine         # Arch
```

---

## Required Key Files

Place these three files in the `keys/` folder:

| File | Size | Purpose | How to Get |
|------|--------|----------|------------|
| `keys/decryptKey.bin` | 65,536 B | Unpack FPD `.bin` archives | `kurikomoe/FSNr_tools` repo → `keys/` folder |
| `keys/main.exe` | ~1.4 MB | Decrypt/encrypt EPK | Compile from `kurikomoe/FSNr_tools` |
| `keys/SomeKey.bin` | 5,120 B | EPK cryptographic seed | Bundled with the `main.exe` release |

**Compile main.exe (Windows/MinGW):**
```bash
git clone https://github.com/kurikomoe/FSNr_tools
cd FSNr_tools
g++ --std=c++20 -O2 main.cpp -o main.exe
# copy main.exe AND keys/SomeKey.bin to fsn-tools/keys/
```

Run `python fsn-tools.py --key-info` for detailed instructions on each file.

---

## Full Workflow

### Step 1 — Extract the Game Pack

```bash
# Extract all .bin files from the /obb folder at once
python fsn-tools.py unpack auto obb/ \
    --key keys/decryptKey.bin \
    --out ./extracted/
```

The result is an `extracted/` folder containing a subfolder for each `.bin` file, each with `.ks` scripts and `.epk` files.

```bash
# To extract UI image assets from /pack/ (WebP)
python fsn-tools.py unpack dat pack/ --out ./extracted_ui/

# View .bin contents without extracting
python fsn-tools.py info fpd obb/pack00m.bin --key keys/decryptKey.bin

# List all EPKs + their script names
python fsn-tools.py epk list extracted/pack00m.bin/
```

---

### Step 2 — Decrypt a Single Scene's EPK

Use the KiriKiri script name (Japanese characters) to extract and immediately decrypt the EPK of the scene you want to translate:

```bash
python fsn-tools.py patch extract-epk pack00m.bin "プロローグ1日目" \
    --key keys/decryptKey.bin \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./work/
```

> **Tip:** Use `python fsn-tools.py info epk --route prologue` (or `saber`, `rin`, `sakura`) to view the list of script names per route.

If you want to decrypt an `.epk` file directly (without extracting from the pack):
```bash
python fsn-tools.py epk dec \
    extracted/pack00m.bin/root#data#locale#ck#epk#1jftmqc2rr04kclvl0ql71s2ef.epk \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./work/
```

The result is a `HASH.epk_dec` file — plain UTF-8 text, openable in any text editor.

---

### Step 3 — Export to JSON

```bash
python fsn-tools.py translate export work/*.epk_dec \
    --out translations/batch1.json

# Multiple files at once
python fsn-tools.py translate export \
    work/1jftmqc2rr04kclvl0ql71s2ef.epk_dec \
    work/46hemeh77jjsiv82vkljdobkr7.epk_dec \
    --out translations/batch_prologue.json

# Check progress
python fsn-tools.py translate status translations/batch1.json
```

---

### Step 4 — Edit the Translation

Open the JSON, fill in the `"translation"` field — don't change anything else:

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
        "translation": "It was a spear tip as fast as lightning.[lr]"
      }
    ]
  }
]
```

>  Preserve markup tags such as `[lr]`, `[l]`, `[p]`, `[r]`, `[ruby text="X"]`. Leave `"translation"` empty if you want to keep the original text.

---

### Step 5 — Import the Translation

```bash
python fsn-tools.py translate import translations/batch1.json \
    --out work/translated/
```

The result is a `HASH_translated.epk_dec` file in `work/translated/`.

---

### Step 6 — Build the Patch

```bash
python fsn-tools.py patch build ./work/translated/ \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./my_patch/
```

The result is a `my_patch/` folder with the following structure:
```
my_patch/
└── root/data/locale/
    └── ck/epk/
        └── 1jftmqc2rr04kclvl0ql71s2ef.epk
```

---

### Step 7 — Deploy to the Game

**Steam:**
```bash
python fsn-tools.py patch deploy ./my_patch/
```
The file is copied to `%LOCALAPPDATA%\typemoon\fsn2\data\root\data\locale\ck\epk\` — the original game files are not touched.

**Crack/Portable:**
```bash
python fsn-tools.py patch launcher ./my_patch/ \
    --game-exe "C:\Games\Fate\fsn2-win64vc14-release.exe"
```
Creates a batch file that sets `%LOCALAPPDATA%` to the patch subfolder before launching the game.

**Dry run (simulation):**
```bash
python fsn-tools.py patch deploy ./my_patch/ --dry-run
```

---

## Choosing the Target Language: `ck` vs `us`

The FSN Remastered game has two locales:

| Folder | Language | EPK Count |
|--------|--------|------------|
| `ck` | Chinese | 727 EPK — **main translation target** |
| `us` | English | 727 EPK |

If you want to target the English text, rename the `ck` folder → `us` in the `patch build` output before deploying:

```powershell
# PowerShell
Rename-Item "my_patch\root\data\locale\ck" "us"

# Command Prompt
ren "my_patch\root\data\locale\ck" "us"
```

You can also deploy both at once by having both `ck` and `us` folders simultaneously in `my_patch/root/data/locale/`.

---

## Full Command Reference

```
fsn-tools.py  [--verbose]  [--key-info]

  unpack
    fpd   <file.bin> [...]  --key <decryptKey.bin>  --out <dir>
    dat   <pack_dir>                                 --out <dir>
    auto  <pack_dir>        --key <decryptKey.bin>  --out <dir>

  epk
    dec   <file.epk> [...]    --main-exe <exe>  --some-key <key>  [--out <dir>]
    enc   <file.epk_dec> [...] --main-exe <exe>  --some-key <key>  [--out <dir>]
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

> The default `--main-exe` and `--some-key` are `keys/main.exe` and `keys/SomeKey.bin` — if they're already in that location, these two arguments can be omitted.

---

## EPK Text Format

After decryption, the EPK file is plain UTF-8 text:

```
DAT
id=qid::label=str::text=lstr::
27244::$$$message_0234_0000_0000$$$::那是有如闪电的枪尖。[lr]::
27245::$$$message_0234_0000_0001$$$::迎面刺来的枪尖试图贯穿心脏。[lr]::
```

Field: `id :: $$$placeholder$$$ :: text :: [additional markup]`

**Markup tags — must be preserved:**

| Tag | Meaning |
|-----|------|
| `[lr]` | Line break + wait for click |
| `[l]` | Wait for click |
| `[p]` | Page change |
| `[r]` | New line |
| `[ruby text="X"]` | Furigana/ruby annotation |

---

## Game File Structure

```
[installation root]/
├── obb/    ← dialogue scripts, audio, UI (inside encrypted .bin)
└── pack/   ← image UI assets (inside .dat)
```

### `/obb/` — Scripts, Audio, UI

```
obb/
├── pack00m.bin      ← MAIN FPD pack: 6805 entries
│                        728 .ks scripts, 2188 .epk files, graphics & audio
├── patch00m.bin     ← FPD patch/update: 628 entries
├── patch00d.bin     ← FPD dedicated to UI graphics
└── movie.dat        ← OP movie
```

| Target | Source File | How to Access |
|--------|-------------|------------|
| Dialogue / story text | `pack00m.bin` / `patch00m.bin` | `unpack` → `epk dec` → edit → `patch build` |
| UI text (menus, buttons) | `pack00m.bin` (EPK `uistring`, `statictext`) | same |
| Audio files | `pack00m.bin` / `patch00m.bin` | `unpack` → extract manually |

### `/pack/` — UI Graphic Assets (WebP)

```
pack/
├── fileinfo_*.txt   ← index: list of file names & offsets inside the .dat
└── *.dat            ← image asset container (WebP, PNG, etc.)
```

Open `fileinfo_*.txt` with a text editor to view its contents. Use `python fsn-tools.py unpack dat <pack_dir> --out <dir>` to extract.

### Locale EPK Groups in pack00m.bin

| Path | Count | Function |
|------|--------|------|
| `root/data/locale/ck/epk/` | 727 | **Chinese — main target** |
| `root/data/locale/us/epk/` | 727 | English (UI + some scenes) |
| `root/data/epk/` | 734 | Base/fallback + special EPK |

EPKs with special names (not per-scene):

| Name | Content |
|------|------|
| `uistring` | Menu labels, buttons, system text |
| `statictext` | Title screen, chapter names |
| `uiconst` | UI constants |
| `timeline_text` | Flowchart/timeline labels |
| `weapon_data` | Noble Phantasm descriptions |
| `servant_data` | Servant profiles |
| `correct_data` | Choice/answer data |
| `bgm_flag` | BGM track names |

---

## Troubleshooting

### `main.exe failed (code 3221225781)`

Code `0xC0000135` = Windows "DLL not found". There are three possible causes:

**A — Incorrect file name**

When FPD extracts an EPK, the filename uses the full path with `#` as a separator:
```
root#data#locale#ck#epk#HASH.epk
```
`main.exe` reads the stem from `argv[1]` to derive the cryptographic key. If the stem becomes `root#data#locale#ck#epk#HASH` (46 characters) instead of just `HASH` (26 characters) → the keystream is wrong → crash.

This toolkit already automatically renames the file to `HASH.epk` in a temp directory before calling `main.exe`. If using `main.exe` manually, rename it first:

```bash
# WRONG
main.exe dec root#data#locale#ck#epk#HASH.epk

# CORRECT
copy root#data#locale#ck#epk#HASH.epk HASH.epk
main.exe dec HASH.epk
```

**B — Visual C++ runtime missing (Windows 7/8.1)**

Already present on Windows 10+. For older Windows, install the [Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe) or Windows Update KB2999226.

**C — Wine not installed (Linux)**

```bash
sudo apt install wine
```

---

## Credits

- **kurikomoe/FSNr_tools** — EPK cryptography (`main.exe`, `SomeKey.bin`), unpack scripts, bonus redirect technique
- **DaZombieKiller/FatePackageManager** — FPD format documentation
- **@tea** — EPK filename hashing algorithm
