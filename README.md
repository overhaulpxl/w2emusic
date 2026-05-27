# 🎵 W2E Music Bot Ecosystem

Proyek ini berisi ekosistem Bot Musik Discord **Way 2 Eternal (W2E)** yang terbagi menjadi dua sistem independen: **Basic Bot** (untuk pengguna publik/kasual) dan **Premium Bot** (untuk pelanggan berbayar/VIP dengan fitur "Sultan").

---

## 📁 Struktur Proyek
- `/` (Root): Berisi kode sumber untuk **Basic Bot**.
- `/premium_bot`: Berisi kode sumber eksklusif untuk **Premium Bot**.

Kedua bot berjalan secara independen dan memiliki file `.env` serta database masing-masing.

---

## 🥉 Basic Bot (`w!`)
Bot kasual yang dirancang dengan antarmuka yang sangat bersih dan minimalis (Jockie Music Style). Sangat ringan dan cocok untuk server publik.
* **Minimalist UI**: Tidak ada *progress bar* yang panjang. Menampilkan pesan Now Playing yang sangat tipis dan elegan.
* **Audio Hemat Kuota**: Default berjalan di kualitas standar (128kbps) dan bisa diturunkan hingga (64kbps) menggunakan command `/quality`.
* **Fitur Utama**: Hybrid Command (`w!play` atau `/play`), Sistem Kepemilikan Sesi (Anti-Rebutan), `/skip`, `/stop`, `/queue`, dan `/history` (merekam 10 lagu terakhir).
* **Anti-Spam**: Pesan Now Playing akan selalu menimpa/mengedit pesan sebelumnya agar chat Discord tidak kotor.

---

## 💎 Premium Bot (`p!`)
Bot VIP dengan fitur komersial kelas atas yang sangat mewah dan eksklusif bagi *user* yang di-*whitelist*.
* **Music Card UI (Rich Embed)**: Tampilan visual *Now Playing* yang sangat besar dan memukau, lengkap dengan *Thumbnail* gambar dari YouTube/sumber lagu.
* **Lossless Audio (Studio Quality)**: Mendukung pengubahan kualitas suara hingga **320kbps (HD)** menggunakan command `/quality hq`.
* **Sistem "Sultan" Eksklusif**:
  * **Lagu Kedatangan (`/set_theme`)**: User bisa memasang lagu tema yang akan otomatis diputar bot selama 5 detik setiap kali mereka memasuki Voice Channel.
  * **Papan Suara Pribadi (`/sfx_add` & `/sfx`)**: User bisa mengunggah file MP3 efek suara lucu/meme mereka sendiri dan memutarnya secara instan di VC.
  * **Spotify Wrapped Pribadi (`/wrapped`)**: Bot mencatat statistik mendengarkan musik (*Total Durasi, Top 3 Artis, Top 3 Lagu*) untuk dipamerkan.
* **Kontrol Musik Tingkat Lanjut**:
  * **`/seek`**: Melompat ke menit/detik tertentu di pertengahan lagu.
  * **`/queue_export` & `/queue_import`**: Mencetak ratusan lagu di antrean ke file `.txt` dan memasukkannya kembali.
  * **`/stay`**: Memaksa bot berjaga di Voice Channel 24/7 (Sangat cocok untuk radio Lo-Fi).
  * **Autoplay & Custom Playlist**: Menarik lagu otomatis saat antrean habis, dan menyimpan *playlist* pribadi dalam JSON.

---

## ⚙️ Cara Menjalankan Bot

1. Pastikan **FFmpeg** telah terinstal di sistem Anda dan terdaftar di PATH.
2. Install modul yang dibutuhkan:
   ```bash
   pip install -r requirements.txt
   ```
3. Buat file `.env` di direktori masing-masing bot (Root dan `premium_bot`) dan isi dengan:
   ```env
   DISCORD_TOKEN=token_bot_anda
   BOT_PREFIX=w!
   ```
   *(Ganti `BOT_PREFIX` menjadi `p!` untuk folder Premium).*
4. Jalankan bot melalui terminal secara terpisah:
   * **Terminal 1 (Basic)**: `python bot.py`
   * **Terminal 2 (Premium)**: `cd premium_bot && python bot.py`

---
*Dibuat khusus untuk ekosistem Way 2 Eternal.*
