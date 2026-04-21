# fsn-tools — Panduan Terjemahan Fate/Stay Night Remastered

Toolkit all-in-one untuk mentranslasi **Fate/Stay Night Remastered** (versi Steam maupun crack).

Pure Python 3.8+, tanpa dependensi eksternal.  
Berjalan native di Windows. Linux/macOS membutuhkan Wine untuk operasi EPK.

---

## Daftar Isi

- [Gambaran Umum](#gambaran-umum)
- [Persyaratan](#persyaratan)
- [File Key yang Dibutuhkan](#file-key-yang-dibutuhkan)
- [Alur Kerja Lengkap](#alur-kerja-lengkap)
  - [Langkah 1 — Ekstrak Pack Game](#langkah-1--ekstrak-pack-game)
  - [Langkah 2 — Dekripsi File EPK Satu Adegan](#langkah-2--dekripsi-file-epk-satu-adegan)
  - [Langkah 3 — Export ke JSON untuk Ditranslasi](#langkah-3--export-ke-json-untuk-ditranslasi)
  - [Langkah 4 — Edit Terjemahan](#langkah-4--edit-terjemahan)
  - [Langkah 5 — Import Terjemahan Kembali](#langkah-5--import-terjemahan-kembali)
  - [Langkah 6 — Build Patch](#langkah-6--build-patch)
  - [Langkah 7 — Deploy Patch ke Game](#langkah-7--deploy-patch-ke-game)
- [Memilih Bahasa Target: `ck` vs `us`](#memilih-bahasa-target-ck-vs-us)
- [Bukti Keberhasilan](#bukti-keberhasilan)
- [Referensi Command Lengkap](#referensi-command-lengkap)
- [Format Teks EPK](#format-teks-epk)
- [Struktur File Game](#struktur-file-game)
- [Troubleshooting](#troubleshooting)
- [Kredit](#kredit)

---

## Gambaran Umum

FSN Remastered menyimpan dialog dalam file **EPK** (encrypted locale packages) yang ada di dalam arsip **FPD `.bin`**.

```
pack00m.bin  (pack utama game, 494 MB, 728 skrip)
patch00m.bin (pack patch, 59 MB, 301 skrip)
      │
      ▼  unpack  ← butuh decryptKey.bin
  extracted/  [*.ks scripts + *.epk locale files]
      │
      ▼  epk dec  ← butuh main.exe + SomeKey.bin
  HASH.epk_dec   [teks UTF-8 biasa, bisa diedit]
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

## Persyaratan

- Python 3.8 atau lebih baru
- Windows (native) **atau** Linux/macOS dengan Wine terinstal
- Tiga file key (lihat bagian berikutnya)

**Install Wine (Linux):**

```bash
sudo apt install wine       # Debian / Ubuntu
sudo pacman -S wine         # Arch Linux
```

---

## File Key yang Dibutuhkan

Letakkan ketiga file ini di dalam folder `keys/`:

| File | Ukuran | Kegunaan | Cara Mendapatkan |
|------|--------|----------|-----------------|
| `keys/decryptKey.bin` | 65.536 B | Unpack arsip FPD `.bin` | Repo `kurikomoe/FSNr_tools` → folder `keys/` |
| `keys/main.exe` | ~1,4 MB | Dekripsi / enkripsi EPK | Compile dari `kurikomoe/FSNr_tools` (lihat di bawah) |
| `keys/SomeKey.bin` | 5.120 B | Seed kriptografi EPK | Dibundel bersama rilis `main.exe` |

**Compile main.exe (Windows / MinGW):**

```bash
git clone https://github.com/kurikomoe/FSNr_tools
cd FSNr_tools
g++ --std=c++20 -O2 main.cpp -o main.exe
# salin main.exe DAN keys/SomeKey.bin ke dalam folder fsn-tools/keys/
```

Jalankan `python fsn-tools.py --key-info` untuk instruksi detail tiap file.

---

## Alur Kerja Lengkap

Berikut adalah alur lengkap dari nol hingga patch berjalan di dalam game.

### Langkah 1 — Ekstrak Pack Game

Ekstrak semua file dari folder `obb/pack/` game ke direktori kerja lokal.

```bash
python fsn-tools.py unpack auto obb/pack/ \
    --key keys/decryptKey.bin \
    --out ./extracted/
```

Hasilnya adalah folder `extracted/` yang berisi subfolder per file `.bin`, masing-masing berisi skrip `.ks` dan file `.epk`.

Untuk melihat isi sebuah pack tanpa mengekstraknya:

```bash
python fsn-tools.py info fpd pack00m.bin --key keys/decryptKey.bin
```

Untuk melihat daftar semua file EPK beserta nama skrip yang terbaca manusia:

```bash
python fsn-tools.py epk list extracted/pack00m.bin/
```

---

### Langkah 2 — Dekripsi File EPK Satu Adegan

Gunakan nama skrip KiriKiri (dalam huruf Jepang) untuk mengekstrak dan langsung mendekripsi EPK dari adegan yang ingin ditranslasi.

```bash
python fsn-tools.py patch extract-epk pack00m.bin "プロローグ1日目" \
    --key keys/decryptKey.bin \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./work/
```

> **Tip:** Gunakan `python fsn-tools.py info epk --route prologue` (atau `saber`, `rin`, `sakura`) untuk melihat daftar nama skrip per rute.

Jika ingin mendekripsi file `.epk` secara langsung (tanpa extract dari pack):

```bash
python fsn-tools.py epk dec \
    extracted/pack00m.bin/root#data#locale#ck#epk#1jftmqc2rr04kclvl0ql71s2ef.epk \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./work/
```

Hasilnya adalah file `HASH.epk_dec` — teks UTF-8 biasa yang langsung bisa dibuka dengan editor teks apapun.

---

### Langkah 3 — Export ke JSON untuk Ditranslasi

Konversi file `.epk_dec` ke format JSON agar mudah diedit.

```bash
python fsn-tools.py translate export work/*.epk_dec \
    --out translations/batch1.json
```

Untuk beberapa file sekaligus:

```bash
python fsn-tools.py translate export \
    work/1jftmqc2rr04kclvl0ql71s2ef.epk_dec \
    work/46hemeh77jjsiv82vkljdobkr7.epk_dec \
    --out translations/batch_prologue.json
```

Cek progress terjemahan:

```bash
python fsn-tools.py translate status translations/batch1.json
```

---

### Langkah 4 — Edit Terjemahan

Buka file JSON dengan editor teks (VS Code, Notepad++, dll). Isi kolom `"translation"` pada setiap entri:

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
      },
      {
        "id": "27245",
        "placeholder": "$$$message_0234_0000_0001$$$",
        "original": "迎面刺来的枪尖试图贯穿心脏。[lr]",
        "translation": "Ujung tombak itu melesat ke arahku, hendak menembus jantungku.[lr]"
      }
    ]
  }
]
```

> **Penting:** Pertahankan tag markup seperti `[lr]`, `[l]`, `[p]`, `[r]`, dan `[ruby text="X"]`.  
> Biarkan `"translation"` kosong (`""`) jika ingin teks tetap menggunakan bahasa aslinya.

---

### Langkah 5 — Import Terjemahan Kembali

Setelah selesai mengisi terjemahan, import kembali ke format `.epk_dec`:

```bash
python fsn-tools.py translate import translations/batch1.json \
    --out work/translated/
```

Hasilnya adalah file `HASH_translated.epk_dec` di dalam folder `work/translated/`.

---

### Langkah 6 — Build Patch

Enkripsi kembali file `.epk_dec` yang sudah ditranslasi dan susun ke dalam struktur direktori patch yang siap pakai.

```bash
python fsn-tools.py patch build ./work/translated/ \
    --main-exe keys/main.exe \
    --some-key keys/SomeKey.bin \
    --out ./my_patch/
```

Hasilnya adalah folder `my_patch/` dengan struktur seperti ini:

```
my_patch/
└── root/
    └── data/
        └── locale/
            └── ck/          ← folder bahasa target (lihat bagian selanjutnya)
                └── epk/
                    └── 1jftmqc2rr04kclvl0ql71s2ef.epk
```

---

### Langkah 7 — Deploy Patch ke Game

**Versi Steam (direkomendasikan):**

```bash
python fsn-tools.py patch deploy ./my_patch/
```

Perintah ini menyalin file EPK ke:
```
%LOCALAPPDATA%\typemoon\fsn2\data\root\data\locale\ck\epk\
```
Game membaca override dari lokasi ini secara otomatis — **file game asli tidak disentuh sama sekali**.

**Versi Crack / Portable:**

```bash
python fsn-tools.py patch launcher ./my_patch/ \
    --game-exe "C:\Games\Fate\fsn2-win64vc14-release.exe"
```

Membuat file batch yang mengatur `%LOCALAPPDATA%` ke subfolder patch sebelum meluncurkan game. File game asli **tidak pernah diubah**.

**Dry run (simulasi tanpa menulis file):**

```bash
python fsn-tools.py patch deploy ./my_patch/ --dry-run
```

---

## Memilih Bahasa Target: `ck` vs `us`

Setelah `patch build`, hasil patch akan berada di:

```
my_patch/root/data/locale/ck/epk/HASH.epk
```

Game FSN Remastered memiliki dua locale teks:

| Folder | Bahasa | Keterangan |
|--------|--------|-----------|
| `ck`   | Mandarin (Chinese) | Target terjemahan utama, berisi 727 EPK |
| `us`   | Inggris (English)  | Teks UI dan beberapa adegan, berisi 727 EPK |

**Untuk menarget teks bahasa Inggris**, cukup rename folder `ck` menjadi `us` di dalam hasil `patch build` sebelum deploy:

**Cara rename di Windows Explorer:**
1. Buka `my_patch\root\data\locale\`
2. Klik kanan folder `ck` → **Rename** → ketik `us`
3. Jalankan `patch deploy` seperti biasa

**Cara rename via Command Prompt / PowerShell:**

```powershell
# PowerShell
Rename-Item "my_patch\root\data\locale\ck" "us"

# Command Prompt
ren "my_patch\root\data\locale\ck" "us"
```

Setelah rename, struktur patch menjadi:

```
my_patch/
└── root/
    └── data/
        └── locale/
            └── us/          ← hasil rename dari ck
                └── epk/
                    └── HASH.epk
```

Kemudian deploy seperti biasa:

```bash
python fsn-tools.py patch deploy ./my_patch/
```

> **Catatan:** Kamu juga bisa men-deploy keduanya sekaligus dengan memiliki folder `ck` dan `us` di dalam `my_patch/root/data/locale/` secara bersamaan, jika ingin menimpa kedua bahasa.

---

## Bukti Keberhasilan

Berikut adalah bukti bahwa proses translasi berhasil dijalankan — teks di dalam game berhasil diubah menggunakan toolkit ini:

![Bukti script berhasil diubah](https://i.imgur.com/q9K7bpr.png)

*File `.epk_dec` berhasil diekstrak, diedit, di-enkripsi ulang via `patch build`, dan terbaca oleh game setelah `patch deploy`.*

---

## Referensi Command Lengkap

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
    extract-epk  <file.bin>  <"nama skrip">  --key <decryptKey.bin>
                                              --main-exe <exe>  --some-key <key>
                                              --out <dir>

  info
    fpd   <file.bin>  --key <decryptKey.bin>  [--type epk|ks|png]  [-v]
    epk   [--route saber|rin|sakura|prologue]
    hash  <"nama skrip"> [...]
```

> Default path untuk `--main-exe` dan `--some-key` adalah `keys/main.exe` dan `keys/SomeKey.bin`.  
> Jika key berada di lokasi default, kedua argumen tersebut bisa dihilangkan dari perintah.

---

## Format Teks EPK

Setelah didekripsi, file EPK adalah teks UTF-8 biasa:

```
DAT
id=qid::label=str::text=lstr::
27244::$$$message_0234_0000_0000$$$::那是有如闪电的枪尖。[lr]::
27245::$$$message_0234_0000_0001$$$::迎面刺来的枪尖试图贯穿心脏。[lr]::
```

Field: `id :: $$$placeholder$$$ :: text :: [markup tambahan]`

**Tag markup — harus dipertahankan saat menerjemahkan:**

| Tag | Arti |
|-----|------|
| `[lr]` | Ganti baris + tunggu klik |
| `[l]`  | Tunggu klik |
| `[p]`  | Ganti halaman |
| `[r]`  | Baris baru |
| `[ruby text="X"]` | Anotasi furigana / ruby |

---

## Struktur File Game

```
obb/pack/
├── fileinfo_*.txt         ← file indeks untuk container .dat
├── *.dat                  ← container aset mentah (gambar, video, dll.)
├── pack00m.bin            ← FPD pack UTAMA: 6805 entri (728 KS + 2188 EPK + aset)
├── patch00m.bin           ← FPD patch: 628 entri (subset)
├── patch00d.bin           ← FPD patch: grafis UI saja
└── movie.dat              ← file OP movie
```

### Grup locale EPK di dalam pack00m.bin

| Path | Jumlah | Fungsi |
|------|--------|--------|
| `root/data/locale/ck/epk/` | 727 | **String Mandarin — target translasi utama** |
| `root/data/locale/us/epk/` | 727 | String Inggris (UI + beberapa adegan) |
| `root/data/epk/` | 734 | Salinan base/fallback + EPK khusus |

EPK bernama khusus (bukan spesifik per adegan):

| Nama | Isi |
|------|-----|
| `uistring` | Label menu, tombol, teks sistem |
| `statictext` | Layar judul, nama chapter |
| `uiconst` | Konstanta UI |
| `timeline_text` | Label flowchart / timeline |
| `weapon_data` | Deskripsi Noble Phantasm |
| `servant_data` | Teks profil Servant |
| `correct_data` | Data pilihan / jawaban |
| `bgm_flag` | Nama track BGM |

---

## Troubleshooting

### `main.exe failed (code 3221225781)`

Kode `0xC0000135` adalah status Windows "DLL not found". Ada tiga penyebab:

**Penyebab A — Nama file salah (sudah diperbaiki di toolkit ini)**

Saat FPD mengekstrak EPK, file diberi nama dengan path penuh menggunakan `#` sebagai pemisah:
```
root#data#locale#ck#epk#HASH.epk
```
`main.exe` membaca stem dari `argv[1]` untuk menurunkan kunci kriptografi. Jika menerima nama lengkap, stem-nya menjadi `root#data#locale#ck#epk#HASH` (46 karakter) alih-alih hanya `HASH` (26 karakter) — stem salah → keystream salah → crash.

Toolkit ini sudah otomatis mengganti nama file ke `HASH.epk` di direktori temp terisolasi sebelum memanggil `main.exe`. Jika memanggil `main.exe` secara manual, selalu rename file lebih dulu:

```bash
# SALAH
main.exe dec root#data#locale#ck#epk#HASH.epk

# BENAR
copy root#data#locale#ck#epk#HASH.epk HASH.epk
main.exe dec HASH.epk
```

**Penyebab B — Visual C++ runtime tidak ada (Windows 7 / 8.1)**

Windows 10+ sudah menyertakan runtime yang dibutuhkan. Untuk Windows lama:
- Install [Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- Atau Windows Update KB2999226

**Penyebab C — Wine belum terinstal (Linux)**

```bash
sudo apt install wine
```

---

## Kredit

- **kurikomoe/FSNr_tools** — Kripto EPK (`main.exe`, `SomeKey.bin`), skrip unpack, teknik redirect bonus
- **DaZombieKiller/FatePackageManager** — Dokumentasi format FPD
- **@tea** — Algoritma hash nama file EPK
