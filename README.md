# 🎵 W2E Music Bot

Proyek ini adalah source code resmi untuk **Way 2 Eternal (W2E) Music Bot**, sebuah bot musik Discord yang dirancang sangat ringan, stabil, dan memiliki antarmuka (UI/UX) minimalis yang rapi. 

---

## 🌟 Fitur Utama
* **Hybrid Commands**: Mendukung prefix (`w!`) maupun *slash command* (`/`).
* **Minimalist UI & Empty States**: Tidak ada spam chat! Tampilan bersih dengan *Embeds* rapi untuk antrean kosong, riwayat kosong, maupun *Now Playing*.
* **Interactive Now Playing**: *Embed* lagu yang sedang diputar dilengkapi dengan tombol pintar (Pause/Resume, Skip, Stop, Queue) yang akan kedaluwarsa setelah 3 menit.
* **Sistem Kepemilikan Sesi (Session Ownership)**: Pengguna pertama yang memutar lagu akan menjadi "Pemilik Sesi". Mencegah troll/user iseng mengganggu antrean, menjeda, atau melewati lagu secara paksa (kecuali lewat sistem `/voteskip` atau status admin).
* **Hemat Kuota & Kualitas Audio**: Default berjalan di kualitas standar (128kbps) dan bisa diturunkan menjadi (64kbps) dengan `w!quality low`.
* **Thread-Safe Playback**: Bebas dari masalah `no running event loop` maupun bug tumpang-tindih saat memproses antrean lagu.
* **Auto-Idle Timeout**: Mencegah kebocoran memori (Memory Leak) dengan cara memutus koneksi bot secara aman (keluar dari VC) apabila menganggur selama 3 menit.

---

## 📜 Daftar Command

| Command | Alias | Deskripsi |
|---|---|---|
| `w!help` | | Menampilkan menu bantuan interaktif dengan sistem dropdown. |
| `w!play <query/link>` | `w!p` | Memutar lagu dari judul, video URL, atau playlist URL YouTube. |
| `w!nowplaying` | `w!np` | Menampilkan lagu yang sedang diputar + tombol interaktif. |
| `w!queue` | `w!q` | Melihat isi antrean lagu. |
| `w!history` | | Melihat daftar riwayat 10 lagu terakhir yang diputar. |
| `w!pause` | | Menjeda pemutaran musik (khusus Pemilik Sesi). |
| `w!resume` | | Melanjutkan lagu yang dijeda (khusus Pemilik Sesi). |
| `w!skip` | `w!s` | Melewati lagu ke trek berikutnya (khusus Pemilik Sesi). |
| `w!voteskip` | | Voting bersama untuk melewati lagu tanpa harus menjadi Pemilik Sesi (butuh 50% suara VC). |
| `w!stop` | `w!leave` | Mematikan bot, membersihkan queue, dan keluar dari VC. |
| `w!remove <nomor>` | | Menghapus lagu tertentu dari antrean. |
| `w!clear` | | Mengosongkan seluruh antrean tanpa mematikan lagu yang sedang terputar. |
| `w!volume <0-100>` | `w!vol` | Mengatur volume lagu. Setingan ini persisten untuk server Anda. |
| `w!quality <low/basic>` | | Mengubah *bitrate* audio. |
| `w!transfer <@user>` | | Memindahkan hak Pemilik Sesi ke pengguna lain di dalam VC. |
| `w!sync` | | *[Owner Only]* Menyinkronkan daftar *slash command* ke Discord. |

---

## ⚙️ Cara Menjalankan Bot (Manual via Terminal)

Bot ini menggunakan arsitektur *Cluster Manager* (`launcher.py`) yang memungkinkan fitur *auto-restart* jika terjadi *crash*.

1. Pastikan **FFmpeg** telah terinstal di sistem Anda (wajib untuk memproses audio Discord).
2. Install modul Python yang dibutuhkan:
   ```bash
   pip install -r requirements.txt
   ```
3. Buat file `.env` di direktori proyek, salin dari `.env.example`, lalu sesuaikan tokennya:
   ```env
   BASIC_TOKEN_1=MTEyMzQ1...
   BASIC_PREFIX_1=w!
   ```
4. Jalankan *launcher*:
   ```bash
   python launcher.py
   ```

---

## 🐳 Deployment via Docker (Rekomendasi)

Jalankan bot dengan mudah menggunakan Docker tanpa perlu menginstal FFmpeg maupun Python secara manual.

1. **Cara run dengan Docker (Background/Detached):**
   ```bash
   docker compose up -d --build
   ```

2. **Cara lihat logs real-time:**
   ```bash
   docker compose logs -f
   ```

3. **Cara mematikan bot:**
   ```bash
   docker compose down
   ```

**Catatan Environment & Docker:**
- Pastikan file `.env` (mengikuti format `.env.example` dengan prefix `BASIC_TOKEN_1`) sudah ada sebelum menjalankan *docker compose*.
- Direktori `logs/` otomatis di-*mount* ke *host machine* sehingga file log tetap persisten dan aman walau kontainer dimatikan.
- **JANGAN PERNAH** meng-upload/mendorong file `.env` ke layanan Git publik (Github/Gitlab).
