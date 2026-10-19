# Setup perangkat untuk SuaraTB (runbook untuk Claude Code)

Dokumen ini ditujukan untuk **Claude Code** yang berjalan di Ubuntu (WSL2) di laptop anggota tim, untuk menyiapkan
lingkungan simulasi RTL dan layout ASIC sky130 dari clone repo ini (branch `layouting`). Kerjakan langkah berurutan.
Tiap langkah: **cek** dulu (lewati bila sudah terpenuhi), **tindakan**, lalu **verifikasi**. Langkah bertanda
**[MANUSIA]** tidak bisa dilakukan dari dalam WSL: minta pengguna melakukannya dan tunggu konfirmasi.

Berkas di direktori ini (pengganti `SETUP.md`, `scripts/`, `requirements.txt` milik pemilik repo yang ada di `.gitignore`):

| Berkas | Isi |
|---|---|
| `python-requirements.txt` | Paket Python untuk golden, testbench cocotb, skrip `target/` |
| `env.sh` | `SUARATB_DATA`, `SV2V`, aktivasi `.venv` (`source setup/env.sh` dari ROOT repo) |
| `link_data.sh` | Membuat folder data dan symlink `data/raw`, `model/out`, `target/build`, dst. |
| `check_env.sh` | Memeriksa semua alat (hanya membaca); jalankan di awal dan di akhir |

## Batasan untuk Claude

- Jangan commit atau push tanpa persetujuan pengguna; jangan menghapus tag atau riwayat remote.
- Jangan menaruh token, kredensial, data audio, bobot model, atau hasil build di repo (semua besar di `$SUARATB_DATA`).
- Jangan mengubah `rtl/` dan `golden/` untuk keperluan setup; kode spesifik perangkat atau proses hanya di `target/`.
- Jangan bekerja di `/mnt/c/...`: lambat dan izin berkas buatan Docker (milik root) bermasalah. Repo dan data di `~`.
- Perintah `sudo` butuh kata sandi pengguna: minta pengguna menjalankannya bila tidak bisa interaktif.
- Laporkan hasil apa adanya; bila langkah gagal, tampilkan pesan galatnya, jangan menebak.

## 0. Kebutuhan mesin (cek: `free -g`, `df -h ~`, `nproc`)

| Pekerjaan | RAM terlihat di WSL | Disk kosong |
|---|---|---|
| Simulasi cocotb dan golden | 8 GB | 5 GB |
| Layout 13 modul (`target/asic/layout_modules.py`) | 8 GB | 25 GB (alat 10 GB + hasil 14 GB) |
| Layout `cnn_top` dengan 14 makro SRAM (`target/asic/layout_cnn_macro.py`) | **>= 16 GB, sebaiknya 24-32 GB** | +10 GB (P16 + P32) |

Ukuran terukur di laptop asal: citra Docker OpenLane 7,4 GB, PDK sky130 (volare) 2,1 GB, hasil 13 layout 14 GB,
`cnn_top` P16 sekitar 3,7 GB. Siapkan sekitar 40-45 GB kosong di drive C (isi WSL2 disimpan di sana).

Bila RAM yang terlihat jauh di bawah RAM laptop, lakukan langkah 1.2.

## 1. Sisi Windows [MANUSIA]

1. **WSL2 + Ubuntu**: PowerShell sebagai administrator: `wsl --install -d Ubuntu-24.04`, restart Windows.
2. **Memori WSL2** (bawaan hanya sekitar 50% RAM): buat `C:\Users\<nama>\.wslconfig`:
   ```
   [wsl2]
   memory=24GB
   swap=16GB
   processors=8
   ```
   Sesuaikan dengan RAM laptop (sisakan sekitar 4 GB untuk Windows), lalu `wsl --shutdown` dan buka Ubuntu lagi.
3. **Docker Desktop**: pasang, aktifkan *Use the WSL 2 based engine* dan *Settings > Resources > WSL Integration*
   untuk Ubuntu-24.04.

Verifikasi (di Ubuntu): `free -g` menunjukkan memori sesuai `.wslconfig`; `docker run --rm hello-world` berhasil.
Bila `docker` menolak izin: `sudo usermod -aG docker $USER`, lalu buka terminal baru.

## 2. Paket sistem

Cek: `command -v iverilog verilator yosys klayout gtkwave make`.
Tindakan:
```bash
sudo apt update
sudo apt install -y git make build-essential python3-venv python3-dev iverilog verilator yosys gtkwave klayout unzip curl
```
Versi saat hasil di repo dibuat: Ubuntu 24.04, Icarus Verilog 12.0, Verilator 5.020, Yosys 0.33, KLayout 0.28.16.

## 3. Repo dan Python

Cek: `git branch --show-current` = `layouting`; `.venv/bin/python -c "import cocotb"` berhasil.
Tindakan (dari ROOT repo):
```bash
git switch layouting
python3 -m venv .venv && . .venv/bin/activate
pip install -r setup/python-requirements.txt
```
Python 3.12; cocotb 2.1.0. Paket pelatihan model (torch, librosa, dll.) sengaja tidak dipasang.

## 4. sv2v

Cek: `command -v sv2v && sv2v --version` (harus v0.0.13).
Tindakan: unduh `sv2v-Linux.zip` rilis v0.0.13 dari `https://github.com/zachjs/sv2v/releases`, ekstrak, salin biner
`sv2v` ke `~/.local/bin`, `chmod +x`, pastikan `~/.local/bin` ada di `PATH` (`~/.bashrc`).

## 5. Folder data dan variabel lingkungan

Cek: `echo $SUARATB_DATA` terisi dan foldernya ada; `readlink target/build` menunjuk ke `$SUARATB_DATA/build`.
Tindakan:
```bash
echo 'export SUARATB_DATA=$HOME/suaratb-data' >> ~/.bashrc && export SUARATB_DATA=$HOME/suaratb-data
bash setup/link_data.sh
source setup/env.sh
```
Symlink yang dibuat (`data/raw`, `data/processed`, `data/features`, `model/out`, `target/build`) ada di `.gitignore`.

## 6. Verifikasi simulasi

```bash
make test-golden
make test-unit M=preemph
make test-unit M=cnn_top
```
Harus lulus semua (cocotb + Icarus, `SIM=icarus` bawaan di `Makefile`). Regresi penuh (`make test`) opsional, lebih lama.

## 7. Layout ASIC sky130 (OpenLane 2)

Cek: `docker image inspect ghcr.io/efabless/openlane2:2.3.10`; `ls ~/.volare/volare/sky130/versions` berisi
`0fe599b2afb6708d281543108caf8310912f54af`; `ls $SUARATB_DATA/build/synth/P16/cnn_cfg_pkg.sv`.
Tindakan:
```bash
docker pull ghcr.io/efabless/openlane2:2.3.10
volare enable --pdk sky130 0fe599b2afb6708d281543108caf8310912f54af
python target/artix7/prep_synth.py --p 16 --out $SUARATB_DATA/build/synth/P16
python target/artix7/prep_synth.py --p 32 --out $SUARATB_DATA/build/synth/P32
```
`prep_synth.py` tanpa `--model` memakai bobot acak terkalibrasi; cukup untuk layout (isi bobot tidak mengubah ukuran
chip karena ROM bobot berupa makro SRAM). Bobot terlatih tidak ada di repo dan tidak boleh di-commit.

Verifikasi cepat (sekitar 5 menit): `python target/asic/layout_modules.py i2s_rx` lalu pastikan
`$SUARATB_DATA/build/asic/i2s_rx/runs/c1/final/metrics.json` ada dengan DRC 0 dan LVS 0 (ringkasan dicetak skrip).

Perintah dan variabel lingkungan lengkap ada di docstring `target/asic/layout_modules.py` dan
`target/asic/layout_cnn_macro.py`. Hasil, keputusan, dan batasan layout tercatat di `target/asic/README.md`.

## 8. Akhir setup

Jalankan `bash setup/check_env.sh` dan laporkan keluarannya ke pengguna, termasuk alat yang masih "TIDAK ADA".

## 9. Pekerjaan yang dilanjutkan (setelah setup)

| Pekerjaan | Status di laptop asal (8 GB) | Langkah |
|---|---|---|
| `cnn_top` P16 (6 makro RAM + 8 makro ROM bobot) | Routing 0 pelanggaran; timing TT/FF bersih; XOR, DRC, LVS, LEF top gagal OOM | `WROM=sram P=16 python target/asic/layout_cnn_macro.py` di mesin >= 16 GB |
| `cnn_top` P32 | Belum dijalankan | `WROM=sram P=32 ...`; cek nama instans makro RAM P32 dan kesetaraan fungsi wrapper ROM P32 (simulasi) |
| Corner SS `cnn_top` | Setup -1,98 ns, hold -1,26 ns | Makro OpenRAM hanya punya lib TT (dipakai untuk semua corner); periksa ulang |
| Antena dan slew/kapasitansi modul kecil | Belum diperbaiki: `window`, `log_q`, `cough_det`, `power`, `requant` P16/P32, `pe_array` P16 | `FIX=1 python target/asic/layout_modules.py <modul>` (`P=32` untuk varian P32) |
| Slew dan fanout `mel` | Naik setelah perbaikan antena (antena 189 -> 9) | Atur ulang perbaikan: tanpa dioda heuristik, batas kabel lebih longgar |

## 10. Graf repo (graphify)

`graphify-out/` (graf pengetahuan repo) ikut di branch ini. `graphify-out/GRAPH_REPORT.md` merangkum modul dan
komunitas; `graphify-out/graph.html` dibuka di browser. Baca `GRAPH_REPORT.md` sebelum menelusuri kode. Memperbarui
setelah perubahan kode: `pip install graphifyy` lalu `graphify update .`. Catatan: graphify selalu melewati folder bernama `target`
(dianggap folder build), sehingga `target/` (asic, kv260, artix7, yosys) di graf ini diekstrak terpisah dengan ID path
lengkap dan **tidak** ikut diperbarui oleh `graphify update .`.

## Konteks proyek

SuaraTB: akselerator triase TBC dari suara batuk (I2S -> log-mel -> CNN int8 -> skor), Hackathon Deeptech 2026. Alat
triase/prioritas rujukan, **bukan** alat diagnosis. Baca `README.md` di ROOT, lalu `docs/vault/status-fase.md`,
`docs/vault/spesifikasi.md`, `docs/vault/keputusan.md`. Angka hardware hanya dari laporan alat; selain itu diberi label
estimasi.
