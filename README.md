# 📖 Kisah Sang Regresor — Reader Terjemahan Indonesia

Reader lokal untuk novel **A Regressor's Tale of Cultivation** (NeverluckySMILe)
terjemahan Indonesia, bisa dibuka di komputer maupun HP.

> ⚠️ Novel adalah karya cipta penulis asli. Terjemahan otomatis ini **hanya untuk
> pemakaian pribadi** — jangan disebarluaskan.

## 🚀 Cara Menjalankan

```bash
python3 server.py            # port default 8000
python3 server.py 3000       # ganti port jika perlu
```

Lalu buka:

| Perangkat | Alamat |
|---|---|
| Komputer | http://localhost:8000 |
| HP (sama satu Wi-Fi) | http://IP-KOMPUTER:8000 |

Cara cepat di HP: tekan tombol **📱 Info Koneksi** di halaman depan → scan QR-nya.

Berhenti server: `Ctrl+C`.

## ✨ Fitur Reader

- **Terjemahan Indonesia** + toggle ke teks asli Inggris (ikon **Aa**)
- **Penanda istilah** `?` di teks — ketuk untuk lihat penjelasan
  (mis. Regresi, Akar Spiritual, Formasi Inti, dll.)
- **Glosarium** lengkap semua istilah kultivasi
- **Penanda percakapan** (garis di kiri), **pikiran** (miring), **efek suara** (tebal)
- Tema Terang / Gelap / Sepia, ukuran & jenis huruf bisa diatur
- Progres baca tersimpan otomatis (lanjutkan dari terakhir)
- Swipe kiri/kanan di tepi layar (atau panah ← → di keyboard) ganti bab
- Cari bab di halaman depan

## 🗂 Struktur

```
├── server.py          server web (stdlib, tanpa dependensi)
├── scripts/
│   ├── fetch.py       unduh chapter dari Webnovel → data/en/
│   ├── translate.py   terjemahkan EN→ID + rapikan istilah → data/id/
│   └── glossary.json  daftar istilah & penjelasannya
├── data/
│   ├── toc.json       daftar chapter (Prolog + Bab 1–100)
│   ├── en/*.json      teks asli Inggris
│   └── id/*.json      terjemahan Indonesia (sudah diklasifikasi + beri catatan)
└── web/               tampilan (index.html, style.css, app.js)
```

> **Catatan repo:** teks novel (`data/en`, `data/id`) dan sampul (`web/cover.jpg`)
> tidak ikut diunggah karena merupakan materi berhak cipta. Setelah clone,
> jalankan `scripts/fetch.py` lalu `scripts/translate.py` untuk menghasilkannya
> sendiri secara lokal. Sampul opsional: unduh gambar sampul novel ke
> `web/cover.jpg` (tanpa itu, tampilan tetap jalan tanpa gambar).

## 🔄 Menambah / Memperbarui Chapter

```bash
# 1. unduh chapter (Prolog + Bab 1–100 sudah ada; ubah MAX_N di fetch.py untuk bab lain)
python3 scripts/fetch.py

# 2. terjemahkan (yang sudah ada otomatis dilewati; --force untuk ulang)
python3 scripts/translate.py
python3 scripts/translate.py --only 42      # satu bab saja
```

Kemudian muat ulang halaman reader.

## 🛠 Keterangan Teknis

- **Anti-Cloudflare**: pemakaian `curl_cffi` (impersonate Chrome).
- **Terjemahan**: endpoint Google Translate (`gtx`), dikelompokkan ±4.500 karakter
  per request, dengan fallback pecah-bagi jika jumlah baris tidak cocok.
- **Istilah**: `glossary.json` menormalkan terjemahan agar konsisten
  (mis. *Qi Refining* selalu jadi **Pemurnian Qi**) dan menyisipkan penanda
  catatan pada kemunculan pertama tiap bab.
- **Klasifikasi paragraf** (percakapan/pikiran/efek suara) ditentukan dari
  teks asli Inggris, bukan hasil terjemahan.
- Tidak ada database — semua berkas JSON statis, server hanya membaca file.
