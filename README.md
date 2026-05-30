# fsn-tools — Panduan Terjemahan Fate/Stay Night Remastered

Toolkit all-in-one buat translasi **Fate/Stay Night Remastered** (Steam maupun crack).

Pure Python 3.8+, tanpa dependensi eksternal. Native di Windows — Linux/macOS butuh Wine untuk operasi EPK.

---

## Proof of Concept

| Screenshot |
|:---:|
| ![Bukti script berhasil diubah](https://i.imgur.com/q9K7bpr.png) |
| *Teks in-game berhasil diubah via patch build + deploy* |

---

## Gambaran Umum

FSN Remastered nyimpen dialog di file **EPK** (encrypted locale packages) yang dibundel dalam arsip **FPD `.bin`**.

```
obb/pack00m.bin  (pack utama, 494 MB, 728 skrip)
obb/patch00m.bin (pack patch, 59 MB, 301 skrip)
      │
      ▼  unpack  ← butuh decryptKey.bin
  extracted/  [*.ks scripts + *.epk locale files]
      │
      ▼  epk dec  ← butuh main.exe + SomeKey.bin
  HASH.epk_dec   [teks UTF-8 biasa, bisa langsung diedit]
      │
      ▼  translate export → edit JSON → translate import
  HASH_translated.epk_dec
      │
      ▼  patch build  ← butuh main.exe + SomeKey.bin
  my_patch/root/data/locale/ck/epk/HASH.epk
      │
      ▼  patch deploy  (Steam)
      atau patch launcher  (crack / portable)
Game membaca teks hasil terjemahan ✓
```

---

## Requirements

- Python 3.8+
- Windows (native) **atau** Linux/macOS dengan Wine

**Install Wine (Linux):**
```bash
sudo apt install wine       # Debian/Ubuntu
sudo pacman -S wine         # Arch
```

---

## File Key yang Dibutuhkan

Taruh ketiga file ini di folder `keys/`:

| File | Ukuran | Kegunaan | Cara Dapat |
|------|--------|----------|------------|
| `keys/decryptKey.bin` | 65.536 B | Unpack arsip FPD `.bin` | Repo `kurikomoe/FSNr_tools` → folder `keys/` |
| `keys/main.exe` | ~1,4 MB | Dekripsi/enkripsi EPK | Compile dari `kurikomoe/FSNr_tools` |
| `keys/SomeKey.bin` | 5.120 B | Seed kriptografi EPK | Dibundel bareng rilis `main.exe` |

**Compile main.exe (Windows/MinGW):**
```bash
git clone https://github.com/kurikomoe/FSNr_tools
cd FSNr_tools
g++ --std=c++20 -O2 main.cpp -o main.exe
# salin main.exe DAN keys/SomeKey.bin ke fsn-tools/keys/
```

Jalankan `python fsn-tools.py --key-info` untuk instruksi detail tiap file.

---

## Alur Kerja Lengkap

### Langkah 1 — Ekstrak Pack Game

```bash
# Ekstrak semua .bin dari folder /obb sekaligus
python fsn-tools.py unpack auto obb/ \
    --key keys/decryptKey.bin \
    --out ./extracted/
```

Hasilnya folder `extracted/` berisi subfolder per file `.bin`, masing-masing ada skrip `.ks` dan file `.epk`.

```bash
# Kalau mau ekstrak aset UI gambar dari /pack/ (WebP)
python fsn-tools.py unpack dat pack/ --out ./extracted_ui/

# Lihat isi .bin tanpa ekstrak
python fsn-tools.py info fpd obb/pack00m.bin --key keys/decryptKey.bin

# Lihat daftar semua EPK + nama skripnya
python fsn-tools.py epk list extracted/pack00m.bin/
```

---

### Langkah 2 — Dekripsi EPK Satu Adegan

Pakai nama skrip KiriKiri (huruf Jepang) buat ekstrak dan langsung dekripsi EPK adegan yang mau ditranslasi:

```bash
python fsn-tools.py patch extract-epk pack00m.bin "プロローグ1日目" \
    --key keys/decryptKey.bin \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./work/
```

> **Tip:** `python fsn-tools.py info epk --route prologue` (atau `saber`, `rin`, `sakura`) buat lihat daftar nama skrip per rute.

Kalau mau dekripsi file `.epk` langsung (tanpa extract dari pack):
```bash
python fsn-tools.py epk dec \
    extracted/pack00m.bin/root#data#locale#ck#epk#1jftmqc2rr04kclvl0ql71s2ef.epk \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./work/
```

Hasilnya file `HASH.epk_dec` — teks UTF-8 biasa, bisa dibuka editor teks apapun.

---

### Langkah 3 — Export ke JSON

```bash
python fsn-tools.py translate export work/*.epk_dec \
    --out translations/batch1.json

# Beberapa file sekaligus
python fsn-tools.py translate export \
    work/1jftmqc2rr04kclvl0ql71s2ef.epk_dec \
    work/46hemeh77jjsiv82vkljdobkr7.epk_dec \
    --out translations/batch_prologue.json

# Cek progress
python fsn-tools.py translate status translations/batch1.json
```

---

### Langkah 4 — Edit Terjemahan

Buka JSON, isi field `"translation"` — jangan ubah yang lain:

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
        "translation": "Itu adalah ujung tombak secepat kilat.[lr]"
      }
    ]
  }
]
```

> ⚠️ Pertahankan tag markup seperti `[lr]`, `[l]`, `[p]`, `[r]`, `[ruby text="X"]`. Biarkan `"translation"` kosong kalau mau tetap pakai teks asli.

---

### Langkah 5 — Import Terjemahan

```bash
python fsn-tools.py translate import translations/batch1.json \
    --out work/translated/
```

Hasilnya file `HASH_translated.epk_dec` di `work/translated/`.

---

### Langkah 6 — Build Patch

```bash
python fsn-tools.py patch build ./work/translated/ \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./my_patch/
```

Hasilnya folder `my_patch/` dengan struktur:
```
my_patch/
└── root/data/locale/
    └── ck/epk/
        └── 1jftmqc2rr04kclvl0ql71s2ef.epk
```

---

### Langkah 7 — Deploy ke Game

**Steam:**
```bash
python fsn-tools.py patch deploy ./my_patch/
```
File disalin ke `%LOCALAPPDATA%\typemoon\fsn2\data\root\data\locale\ck\epk\` — file game asli nggak disentuh.

**Crack/Portable:**
```bash
python fsn-tools.py patch launcher ./my_patch/ \
    --game-exe "C:\Games\Fate\fsn2-win64vc14-release.exe"
```
Bikin file batch yang set `%LOCALAPPDATA%` ke subfolder patch sebelum launch game.

**Dry run (simulasi):**
```bash
python fsn-tools.py patch deploy ./my_patch/ --dry-run
```

---

## Memilih Bahasa Target: `ck` vs `us`

Game FSN Remastered punya dua locale:

| Folder | Bahasa | Jumlah EPK |
|--------|--------|------------|
| `ck` | Mandarin | 727 EPK — **target translasi utama** |
| `us` | Inggris | 727 EPK |

Kalau mau target teks Inggris, rename folder `ck` → `us` di hasil `patch build` sebelum deploy:

```powershell
# PowerShell
Rename-Item "my_patch\root\data\locale\ck" "us"

# Command Prompt
ren "my_patch\root\data\locale\ck" "us"
```

Bisa juga deploy keduanya sekaligus dengan punya folder `ck` dan `us` sekaligus di `my_patch/root/data/locale/`.

---

## Referensi Command Lengkap

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
    extract-epk  <file.bin>  <"nama skrip">  --key <decryptKey.bin>
                                              --main-exe <exe>  --some-key <key>
                                              --out <dir>

  info
    fpd   <file.bin>  --key <decryptKey.bin>  [--type epk|ks|png]  [-v]
    epk   [--route saber|rin|sakura|prologue]
    hash  <"nama skrip"> [...]
```

> Default `--main-exe` dan `--some-key` adalah `keys/main.exe` dan `keys/SomeKey.bin` — kalau udah di lokasi itu, dua argumen ini bisa dihilangkan.

---

## Format Teks EPK

Setelah dekripsi, file EPK adalah teks UTF-8 biasa:

```
DAT
id=qid::label=str::text=lstr::
27244::$$$message_0234_0000_0000$$$::那是有如闪电的枪尖。[lr]::
27245::$$$message_0234_0000_0001$$$::迎面刺来的枪尖试图贯穿心脏。[lr]::
```

Field: `id :: $$$placeholder$$$ :: text :: [markup tambahan]`

**Tag markup — harus dipertahankan:**

| Tag | Arti |
|-----|------|
| `[lr]` | Ganti baris + tunggu klik |
| `[l]` | Tunggu klik |
| `[p]` | Ganti halaman |
| `[r]` | Baris baru |
| `[ruby text="X"]` | Anotasi furigana/ruby |

---

## Struktur File Game

```
[root instalasi]/
├── obb/    ← skrip dialog, suara, UI (dalam .bin terenkripsi)
└── pack/   ← aset UI gambar (dalam .dat)
```

### `/obb/` — Skrip, Suara, UI

```
obb/
├── pack00m.bin      ← FPD pack UTAMA: 6805 entri
│                        728 skrip .ks, 2188 file .epk, grafis & audio
├── patch00m.bin     ← FPD patch/update: 628 entri
├── patch00d.bin     ← FPD khusus grafis UI
└── movie.dat        ← OP movie
```

| Target | File Sumber | Cara Akses |
|--------|-------------|------------|
| Dialog / teks cerita | `pack00m.bin` / `patch00m.bin` | `unpack` → `epk dec` → edit → `patch build` |
| Teks UI (menu, tombol) | `pack00m.bin` (EPK `uistring`, `statictext`) | sama |
| File suara | `pack00m.bin` / `patch00m.bin` | `unpack` → ekstrak manual |

### `/pack/` — Aset Grafis UI (WebP)

```
pack/
├── fileinfo_*.txt   ← indeks: daftar nama file & offset di dalam .dat
└── *.dat            ← container aset gambar (WebP, PNG, dll.)
```

Buka `fileinfo_*.txt` dengan editor teks untuk lihat isinya. Gunakan `python fsn-tools.py unpack dat <pack_dir> --out <dir>` untuk ekstrak.

### Grup Locale EPK di pack00m.bin

| Path | Jumlah | Fungsi |
|------|--------|--------|
| `root/data/locale/ck/epk/` | 727 | **Mandarin — target utama** |
| `root/data/locale/us/epk/` | 727 | Inggris (UI + beberapa adegan) |
| `root/data/epk/` | 734 | Base/fallback + EPK khusus |

EPK dengan nama khusus (bukan per adegan):

| Nama | Isi |
|------|-----|
| `uistring` | Label menu, tombol, teks sistem |
| `statictext` | Layar judul, nama chapter |
| `uiconst` | Konstanta UI |
| `timeline_text` | Label flowchart/timeline |
| `weapon_data` | Deskripsi Noble Phantasm |
| `servant_data` | Profil Servant |
| `correct_data` | Data pilihan/jawaban |
| `bgm_flag` | Nama track BGM |

---

## Troubleshooting

### `main.exe failed (code 3221225781)`

Kode `0xC0000135` = Windows "DLL not found". Ada tiga kemungkinan:

**A — Nama file salah**

Saat FPD mengekstrak EPK, nama filenya pakai path penuh dengan `#` sebagai pemisah:
```
root#data#locale#ck#epk#HASH.epk
```
`main.exe` baca stem dari `argv[1]` buat nurunkan kunci kriptografi. Kalau stemnya jadi `root#data#locale#ck#epk#HASH` (46 karakter) bukannya cuma `HASH` (26 karakter) → keystream salah → crash.

Toolkit ini sudah otomatis rename file ke `HASH.epk` di direktori temp sebelum panggil `main.exe`. Kalau pakai `main.exe` manual, rename dulu:

```bash
# SALAH
main.exe dec root#data#locale#ck#epk#HASH.epk

# BENAR
copy root#data#locale#ck#epk#HASH.epk HASH.epk
main.exe dec HASH.epk
```

**B — Visual C++ runtime tidak ada (Windows 7/8.1)**

Windows 10+ sudah ada. Untuk Windows lama, install [Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe) atau Windows Update KB2999226.

**C — Wine belum terinstall (Linux)**

```bash
sudo apt install wine
```

---

## Kredit

- **kurikomoe/FSNr_tools** — Kripto EPK (`main.exe`, `SomeKey.bin`), skrip unpack, teknik redirect bonus
- **DaZombieKiller/FatePackageManager** — Dokumentasi format FPD
- **@tea** — Algoritma hash nama file EPK
