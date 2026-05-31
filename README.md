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

> Prefix default adalah `w!` dan bisa diubah lewat `.env` (`BASIC_PREFIX_1`). Contoh di bawah menggunakan prefix default.

| Command | Alias | Deskripsi |
|---|---|---|
| `{prefix}help` | | Menampilkan menu bantuan interaktif dengan sistem dropdown. |
| `{prefix}play <query/link>` | `{prefix}p` | Memutar lagu dari judul, video URL, atau playlist URL YouTube. |
| `{prefix}nowplaying` | `{prefix}np` | Menampilkan lagu yang sedang diputar + tombol interaktif. |
| `{prefix}queue` | `{prefix}q` | Melihat isi antrean lagu. |
| `{prefix}history` | | Melihat daftar riwayat 10 lagu terakhir yang diputar. |
| `{prefix}pause` | | Menjeda pemutaran musik (khusus Pemilik Sesi). |
| `{prefix}resume` | | Melanjutkan lagu yang dijeda (khusus Pemilik Sesi). |
| `{prefix}skip` | `{prefix}s` | Melewati lagu ke trek berikutnya (khusus Pemilik Sesi). |
| `{prefix}voteskip` | | Voting bersama untuk melewati lagu tanpa harus menjadi Pemilik Sesi (butuh 50% suara VC). |
| `{prefix}stop` | `{prefix}leave` | Mematikan bot, membersihkan queue, dan keluar dari VC. |
| `{prefix}remove <nomor>` | | Menghapus lagu tertentu dari antrean. |
| `{prefix}clear` | | Mengosongkan seluruh antrean tanpa mematikan lagu yang sedang terputar. |
| `{prefix}volume <0-100>` | `{prefix}vol` | Mengatur volume lagu. Setingan ini persisten untuk server Anda. |
| `{prefix}quality <low/basic>` | | Mengubah *bitrate* audio. |
| `{prefix}transfer <@user>` | | Memindahkan hak Pemilik Sesi ke pengguna lain di dalam VC. |
| `{prefix}sync` | | *[Owner Only]* Menyinkronkan daftar *slash command* ke Discord. |

---

## 📁 Struktur File & Arsitektur

Bot ini dipisah menjadi tiga file utama untuk mempermudah *maintenance* dan menjaga stabilitas:

* **`launcher.py`**: Bertindak sebagai entri utama dan *Process Manager*. Tugasnya membaca daftar *environment variables* (`BASIC_TOKEN_1`, `BASIC_TOKEN_2`, dst.), meluncurkan beberapa *subprocess* bot secara paralel, meneruskan prefix masing-masing bot, serta memantau semua bot dengan fitur *auto-restart* otomatis jika terjadi *crash*.
* **`bot.py`**: Merupakan *Discord Client Setup*. File ini mengatur konfigurasi *Discord bot*, pengaturan prefix (`BOT_PREFIX`), inisialisasi *intents*, menyusun menu bantuan interaktif (*help menu*), menangani *global error handler*, dan memuat modul tambahan (*cog*).
* **`music.py`**: Adalah inti dari pemutar musik. Semua fitur berfokus di sini: *play*, *queue*, *playlist*, *yt-dlp*, integrasi *FFmpeg*, *Now Playing Component*, *history*, pengatur *volume*, sistem *session ownership*, dan logika utama *playback*.

### 🔄 Fitur Multi-Bot & Alur Konfigurasi (Environment Flow)

1. Bot dijalankan secara normal menggunakan command:
   ```bash
   python launcher.py
   ```
2. `launcher.py` akan membaca konfigurasi dari `.env` dan mendukung hingga **5 bot sekaligus**. Variabel dibaca berpasangan:
   - `BASIC_TOKEN_1` & `BASIC_PREFIX_1` (Untuk Bot 1)
   - `BASIC_TOKEN_2` & `BASIC_PREFIX_2` (Untuk Bot 2)
   - ...dan seterusnya hingga 5 bot. Jika token kosong, slot bot tersebut otomatis dilewati.
3. `launcher.py` lalu mengatur dan meneruskan variabel internal bernama `BOT_PREFIX` untuk tiap *subprocess* bot.
4. Terakhir, `bot.py` menggunakan `BOT_PREFIX` khusus miliknya sebagai *command prefix* utamanya.

**Catatan Prefix:**
Prefix bot sepenuhnya dinamis dan terpisah per bot. Sebagai contoh, Anda bisa mengatur `BASIC_PREFIX_1=w!` untuk bot utama, dan `BASIC_PREFIX_2=w2!` untuk bot cadangan. Default prefix jika tidak diatur (tapi token ada) adalah `w1!`, `w2!`, dst.

---

## ⚙️ Cara Menjalankan Bot (Manual via Terminal)

Bot ini menggunakan arsitektur *Cluster Manager* (`launcher.py`) yang memungkinkan Anda menjalankan beberapa bot sekaligus dan memiliki fitur *auto-restart* jika terjadi *crash*.

1. Pastikan **FFmpeg** telah terinstal di sistem Anda (wajib untuk memproses audio Discord).
2. Install modul Python yang dibutuhkan:
   ```bash
   pip install -r requirements.txt
   ```
3. Buat file `.env` di direktori proyek, salin dari `.env.example`, lalu sesuaikan tokennya:
   ```env
   BASIC_TOKEN_1=your_first_token_here
   BASIC_PREFIX_1=w!

   BASIC_TOKEN_2=your_second_token_here
   BASIC_PREFIX_2=w2!
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
- **KEAMANAN TOKEN**: Jika token asli bot Anda pernah bocor atau terlihat di screenshot, chat, log publik, atau source code, token tersebut sudah dikompromikan. Segera lakukan **Regenerate Token** dari [Discord Developer Portal](https://discord.com/developers/applications).

### 🛠️ Troubleshooting Docker (yt-dlp Cookies)
Jika bot gagal memutar lagu dari YouTube dengan pesan `Sign in to confirm you're not a bot`, pastikan konfigurasi cookies sudah benar untuk Docker:
1. Ekspor cookies dari browser Anda ke dalam file `youtube_cookies.txt`.
2. Letakkan file tersebut di dalam folder `cookies/` pada host Anda.
3. Untuk Docker, gunakan path berikut di dalam file `.env`:
   ```env
   YTDLP_COOKIES_FILE=/app/cookies/youtube_cookies.txt
   ```
4. Pastikan file `docker-compose.yml` telah melampirkan mount berikut:
   ```yaml
   volumes:
     - ./cookies:/app/cookies:ro
   ```
5. Setelah mengubah `.env` atau menambahkan file cookies, muat ulang kontainer dengan:
   ```bash
   docker compose down
   docker compose up -d --build
   ```

