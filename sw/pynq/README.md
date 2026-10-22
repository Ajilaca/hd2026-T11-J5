# sw/pynq

Perangkat lunak host untuk SuaraTB di Kria KV260 lewat AXI4-Lite (satu-satunya jalur host).

| Direktori | Isi | Dijalankan di |
|---|---|---|
| `papan/` | Skrip yang disalin ke kartu SD (hanya pustaka standar, butuh `sudo` untuk `/dev/mem`): `axil1`, `axil2` (klip dataset), `mic1`, `mic2` (mikrofon), `cough1`, `cough_mic` (model batuk vs bukan batuk); pendukung `axil_smoke` (akses register, memuat aplikasi xmutil otomatis), `axil_batch`, `axil_mic`, `fusi`; `setup_papan.sh` (pintasan terminal: `axil1`, `axil2`, `mic1`, `mic2`, `cough1`, `cough_mic`, `papan_status`, `papan_bantuan`) | papan |
| `laptop/` | `make_clips.py` (membuat paket klip + logit golden + manifest; menyalin `papan/`), `fit_fusi.py` (melatih fusi gejala + audio, menulis `fusi.json`, `ambang.txt`), `calibrate_ambang.py` (ambang audio) | laptop (`.venv`) |
| `driver/` | `suaratb_axil.py`: driver PYNQ alternatif (butuh pustaka PYNQ) dan ujinya `test_suaratb_axil.py` | papan / laptop (uji) |

Alur paket: `calibrate_ambang` -> `make_clips` -> `fit_fusi` -> salin folder `paket/` ke kartu SD. Perintah lengkap ada di docstring tiap skrip.
Semua keluaran bersifat triase, bukan diagnosis; ambang dipilih pada data yang sama (optimistis) dan belum dikalibrasi untuk mikrofon INMP441.
