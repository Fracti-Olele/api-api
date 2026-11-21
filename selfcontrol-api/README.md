# Self-Control API — Tahap 2

Backend pribadi (FastAPI + SQLAlchemy + SQLite) untuk app disiplin diri di Android.
Server menyimpan **fakta & status**; HP yang menegakkan (mengunci/memblokir) berdasarkan status itu.
Butuh **Python 3.11+**.

## Arsitektur: tiga lapis, satu arah

```
app/rules/      LOGIKA MURNI: semua aturan waktu & penilaian. Tanpa database, tanpa FastAPI -> mudah diuji.
app/services/   Menyambungkan rules ke database (muat fakta -> panggil rules -> simpan hasil).
app/routers/    Endpoint HTTP tipis. Memanggil services.
app/models.py   Struktur database.   app/schemas.py  Bentuk request/response.
```

Semua angka aturan (40 menit, +20 menit, 5x/3x restorasi, 07.00/09.00, 30 menit berangkat, 3 konfirmasi, dst.)
ada di satu tempat: **`app/rules/ruleset.py`**.

Streak **tidak disimpan sebagai counter**. Ia dihitung ulang dari fakta harian (`day_records`) + daftar restorasi,
jadi memulihkan hari yang gagal otomatis memperbaiki hitungannya, dan tidak ada angka yang bisa "tidak sinkron".
Hari yang terlewat (server mati / HP tidak menghubungi) disusul pada request berikutnya (*lazy sweep*, tanpa cron).

## Deploy: Vercel (API + tampilan) + Neon (database)

Satu proyek Vercel melayani **keduanya**: `public/index.html` adalah tampilannya (dilayani CDN), `index.py` mengekspor API FastAPI.
Satu alamat = tanpa CORS, dan tidak perlu Cloudflare Pages.

1. **Neon** → Dashboard → *Connect* → salin connection string **Pooled connection**.
2. **Vercel** → Add New Project → pilih repo ini. Di *Settings → Environment Variables* isi:
   `API_KEY` (kunci acak panjang), `DATABASE_URL` (string Neon), `TIMEZONE=Asia/Jakarta`.
   Jangan taruh nilai asli di file yang di-commit.
3. Deploy. Buka `https://<proyek>.vercel.app`, masukkan API key di layar masuk. Tabel dibuat otomatis pada request pertama.
4. Di HP: buka alamat itu di Chrome → menu ⋮ → *Tambahkan ke layar utama*.

Catatan:
- `vercel.json` memasang fungsi di **sin1 (Singapura)**, sama dengan database Neon di Singapura. Tanpa ini fungsi berjalan di AS dan tiap query ±200 ms.
- Vercel membatasi isi request **4,5 MB** dan tidak punya disk yang bisa ditulis: tampilan mengompres foto (±300 KB) dan foto disimpan di database (tabel `photos`).
- Neon gratis tidur setelah ±5 menit tidak dipakai; request pertama setelahnya lebih lambat beberapa detik.
- Ubah skema tabel nanti? `create_all` tidak mengubah tabel yang sudah ada. Pakai Alembic, atau hapus tabel lewat konsol Neon (data ikut hilang).

## Menjalankan lokal

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # isi API_KEY; kosongkan DATABASE_URL = SQLite lokal
pytest
uvicorn app.main:app --reload --port 8000              # buka http://127.0.0.1:8000
```

## Endpoint (semua `/api/v1/...`, header `X-API-Key`)

| Modul | Endpoint |
|---|---|
| **Ringkasan HP** | `GET /status` — wake, study, reflection, main, chores, les_today, violations_today, blocked_packages |
| **Bangun tidur** | `POST /wake/checkin` (foto) · `GET /wake/status` · `POST /wake/restore` · `GET /wake/violations` |
| **Belajar** | `POST /study/start` (foto) · `POST /study/end` (foto) · `GET /study/status` · `GET /study/sessions` · `POST /study/restore` · `GET /study/violations` |
| **Refleksi & histori** | `GET /reflection` · `PUT /reflection/today` · `GET /history` · `PUT /history/{tanggal}/star` |
| **Streak** | `GET /streaks` · `GET /streaks/main` |
| **Tugas mingguan** | `GET /chores` · `POST /chores/{setrika\|pakan_hewan}/checkin` (foto) · `GET /chores/history` |
| **Les** | `GET/POST /les/schedules` · `POST /les/schedules/{id}/changes` → `POST /les/changes/{id}/confirm` (x3) → `POST /les/changes/{id}/finalize` · `POST /les/checkin` (foto) · `POST /les/excuses` · `POST /les/extras` (foto) → `PUT /les/extras/{id}/reason` · `GET /les/history` · `GET /les/today` |
| **Pelanggaran** | `GET /violations?category=wake\|study\|les` |
| **Keuangan** | `GET /finance` · `POST /finance/entries` (kind ±1, source irl\|dig, amount, reason wajib) |
| **Pemakaian app** | `PUT /limits/{package}` · `GET /limits` · `POST /usage` → `allowed`/`blocked` |

## Aturan & asumsi (ubah di `rules/ruleset.py` bila maksudmu berbeda)

**Konvensi waktu.** "Sampai 07.00" = sampai akhir menit 07:00 (07:00:59). Berlaku sama untuk 09.00, 17.30 (les), Minggu 23.59 (tugas), 23.59 (refleksi). "Hari" = hari kalender lokal (`TIMEZONE`).

**Belajar.** Target hari itu = 40 menit (+20 bila bangun terlambat/gagal), dijumlahkan dari semua sesi mulai→setelah di hari itu (`>=`). Sesi yang foto "setelah"-nya tidak diupload sampai 23:59 *kedaluwarsa* dan tidak dihitung. Jumat & Sabtu = libur: streak belajar stagnan (tidak bertambah, tidak putus).
**Tabungan restorasi:** belajar di hari libur sampai target hari itu tercapai = +0.5 (sekali per hari). Kuota belajar sebuah bulan = 5 + seluruh tabungan sebelum bulan itu (mode `permanent`; tidak pernah berkurang). Mode `monthly` = hanya tabungan bulan lalu.

**Bangun.** Batas 07.00 (Sen–Jum) / 09.00 (Sab–Min). Foto terlambat tetap diterima (dicatat `WAKE_LATE`); tidak check-in sama sekali dicatat `WAKE_MISSED` keesokan harinya. Kuota restorasi: 3 per bulan.

**Restorasi.** Dipakai manual lewat `POST /wake|study/restore` untuk hari yang gagal, paling lambat sampai akhir hari berikutnya. Hari yang dipulihkan *menjembatani* streak (tidak putus, tidak +1). Denda +20 menit tetap berlaku. Satu hari = satu restorasi per subsistem; kuota dihitung per bulan saat restorasi dipakai.

**Streak utama.** Hari dihitung bila: bangun tepat waktu ∧ belajar memenuhi target (di hari libur: dianggap terpenuhi) ∧ refleksi dijawab (12.00–23.59; wajib `happy` + `text`). Hari bisa diselamatkan lewat restorasi bangun/belajar (menjadi `bridged`); refleksi yang terlewat tidak bisa dipulihkan.

**Histori & tugas.** Refleksi (histori harian) dihapus otomatis setelah 7 hari kecuali berbintang. Check-in tugas + fotonya (baris di tabel `photos`) dihapus setelah 7 hari. Tugas hanya bisa di-check-in di dalam jendelanya (setrika Jum 00.00–Min 23.59; pakan hewan Rab 00.00–Min 23.59), sekali per pekan.

**Les.** Berangkat = jam les − `travel_minutes` (default 30). Foto valid dari saat berangkat sampai 1 jam kemudian; lewat itu tanpa foto/izin = bolos (`LES_ABSENT`). Menambah jadwal bebas; mengubah/menghentikan wajib: 3 konfirmasi + mengetik teks persis (permintaan berlaku 30 menit). Izin hanya bisa diajukan sebelum jendela check-in berakhir. Les tambahan: foto dulu, lalu alasan (sekali).

**Mulai dinilai.** Dari hari pertama yang batas bangunnya belum lewat saat sistem pertama kali dipakai.

## Menyambungkan HP

Sama seperti Tahap 1: uji di Wi-Fi yang sama, pemakaian nyata lewat HTTPS (Tailscale / Cloudflare Tunnel), jangan host di HP yang sama.
App Android memanggil `GET /status` berkala dan menegakkan sisanya; foto dikirim `multipart/form-data` field `photo`.

## Tambahan: PR, ujian, pengaturan pribadi (untuk aplikasi Kith)

| Modul | Endpoint |
|---|---|
| **PR & ujian** | `GET/POST /tasks` (`kind` = `pr` atau `uj`, `title`, `due_date`, `due_time` opsional) · `PATCH /tasks/{id}` (`done`) · `DELETE /tasks/{id}` |
| **Pengaturan** | `GET/PUT /settings` (kunci yang diterima: `name`, `avatar`, `alloc`) |

Tabel `tasks` dan `settings` dibuat otomatis. Untuk aplikasi Android (Capacitor) isi `CORS_ORIGINS` dengan `https://localhost` (asal APK) dan alamat Cloudflare Pages-mu, dipisah koma.
