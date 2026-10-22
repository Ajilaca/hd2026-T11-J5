# target/asic: layout ASIC sky130

Layout fisik SuaraTB di proses terbuka SkyWater 130 nm (sky130A), untuk menunjukkan bahwa hardware ini bisa dibuat sebagai
chip dan sebagai bekal tape-out. Alur: OpenLane 2.3.10 (Yosys, OpenROAD, Magic, KLayout, Netgen) di Docker, PDK sky130A
(volare `0fe599b2afb6708d281543108caf8310912f54af`), sel standar `sky130_fd_sc_hd`. RTL di `rtl/` tidak diubah; semua kode
khusus proses ada di sini.

**Status (22 Okt 2026):** `cnn_top` P=16 pada 10,24 MHz selesai dengan semua cek 0. Chip penuh belum di-layout dan belum
siap tape-out. Rinciannya di bagian Hasil, Keterbatasan, dan Rencana.

## Isi direktori

| Direktori / berkas | Fungsi |
|---|---|
| `scripts/` | Skrip yang menjalankan alur (semua dijalankan dari root repo, lihat tabel berikut) |
| `ram/` | Pengganti RAM dan ROM bobot dengan makro SRAM OpenRAM, patch `cnn_top`, dan tes simulasinya |
| `results/` | Hasil yang di-commit: 13 layout modul (`metrics.csv` ringkasan, `metrics/<layout>.json` metrik lengkap OpenLane) dan `cnn_top/` (metrik final, ringkasan timing, signoff tanpa makro, `riwayat_eco.csv`) |
| `layout/` | Paket hasil layout per modul (GDS, DEF, LEF, Liberty, netlist, SDC, SPEF, metrik) dan README yang menjelaskan isinya. 774 MB: isinya di-ignore git (hanya README dan `metrics.csv` yang dilacak) dan diunduh dari Release (lihat Unduhan) |
| `README.md` | Dokumen ini |

Isi `scripts/`:

| Skrip | Fungsi |
|---|---|
| `synth_sky130.sh` | Sintesis Yosys ke sel sky130 untuk perkiraan luas per modul (tanpa layout) |
| `layout_modules.py` | Layout modul tanpa RAM; `CLK_NS` mengatur clock, `FIX=1` menjalankan ulang dengan perbaikan antena dan slew/kapasitansi |
| `layout_cnn_macro.py` | Layout `cnn_top` dengan RAM dan ROM bobot sebagai makro SRAM (`WROM=sram P=16`); `FLOOR=2` floorplan ulang, `FIX=1` perbaikan kabel panjang, `SIGNOFF=ip` signoff tanpa makro |
| `signoff_nomacro.py` | XOR (Magic vs KLayout) dan DRC KLayout pada GDS dengan instans makro dikeluarkan; dipanggil `layout_cnn_macro.py` atau sendiri |
| `cnn_top_eco/` | Skrip run dasar 10,24 MHz dan delapan putaran ECO kapasitansi/antena `cnn_top` (lihat README di sana) |
| `collect_results.py` | Menyalin metrik ke `results/` dan membuat paket serah-terima (zip) |

Isi `ram/`:

| Berkas | Fungsi |
|---|---|
| `ram_sdp_sky130.sv` | Pengganti `ram_sdp` (port sama) dari makro `sky130_sram_2kbyte_1rw1r_32x512_8` |
| `wrom_sky130.sv` | ROM bobot CNN sebagai makro SRAM yang diisi lewat port muat `wl_*` |
| `patch_wrom.py` | Membuat salinan `cnn_top` (di direktori build) yang memakai `wrom_sky130` dan port `wl_*` |
| `check_ram_wrapper.py`, `test_wrom_load.py` | Simulasi cocotb: `cnn_top` dengan makro vs golden, dan jalur muat bobot |

Skrip dan hasil `cnn_top` final sudah ada di repo (`scripts/layout_cnn_macro.py`, `scripts/signoff_nomacro.py`,
`scripts/cnn_top_eco/`, `results/cnn_top/`). Skrip ECO berpath `$HOME/suaratb-data/build/asic/cnn_top/...` dan dijalankan di
WSL dengan Docker, bukan dari root repo.

Hasil lengkap per run (log semua langkah, ODB) ada di `$SUARATB_DATA/build/asic/<layout>/` di WSL, tidak di git. Hasil
`cnn_top` final: `$SUARATB_DATA/build/asic/cnn_top/p16_10m_eco8/run/final/`.

## Unduhan

Berkas hasil (GDS, DEF, LEF, Liberty, netlist, SDC, SPEF) terlalu besar untuk git dan dirilis di GitHub Release
[`asic-cnn-top-p16-10m24-v1`](https://github.com/Ajilaca/hackaton-deeptech-suaratb/releases/tag/asic-cnn-top-p16-10m24-v1):

| Berkas | Ukuran | SHA-256 |
|---|---|---|
| `suaratb_asic_cnn_top_P16_10m24MHz.zip` (`cnn_top` final) | 52 MB | `22a4e18a254c2e97f4c033d4c3f7fc079515ca5c62515092292f45acd7dcf476` |
| `suaratb_asic_13modul_40MHz.zip` (13 modul 40 MHz, isi `layout/`) | 129 MB | `c7f04147a6ad3c00a9c71d482d54cef8728d43985dab0ffd6c83c9c048fa93ab` |

Untuk mengisi `layout/`: unduh zip 13 modul dan ekstrak ke `target/asic/layout/`.

## Hasil

### `cnn_top` P=16, 10,24 MHz (final, run `p16_10m_eco8`)

14 makro SRAM (6 RAM, 8 ROM bobot), 116.016 sel standar, die 3.072 × 2.926 µm (8,99 mm²), utilisasi inti 49,7%, daya
estimasi 15,7 mW (OpenROAD, tanpa vektor aktivitas).

| Cek | Hasil |
|---|---|
| Kapasitansi maksimum | 0 pelanggaran (9 corner) |
| Antena | 0 net |
| LVS | 0 |
| Routing DRC | 0 |
| Setup / hold | 0 pelanggaran; slack terburuk +34,4 ns / +0,10 ns |
| XOR Magic vs KLayout (GDS tanpa makro) | 0 |
| DRC KLayout (GDS tanpa makro) | 0 |
| Slew maksimum / fanout maksimum | 666 / 1.205 pelanggaran (belum ditangani, timing tetap aman) |

Perjalanan dari run dasar 10,24 MHz ke hasil final (pelanggaran pasca-routing):

| Putaran | Cara | Kapasitansi | Antena |
|---|---|---|---|
| Dasar | alur penuh, `CLOCK_PERIOD` 97,656 ns | 147 | 43 |
| 1–3 | ECO: buffer kapasitansi, GRT ulang, `repair_antennas`, jumper met1 | 11 → 2 → 1 | 38 → 17 → 31 |
| 4 | ECO + jumper kumulatif (87 net) | 0 | 12 |
| 5–7 | ECO tanpa GRT ulang: dioda, buffer pin makro | 2 → 1 → 2 | 5 → 3 → 4 |
| 8 | Buffer pemecah beban + dioda + jumper, tanpa GRT ulang | **0** | **0** |

Yang berhasil dan alasannya:
- **ECO tanpa GRT ulang.** GRT di tiap putaran membuat ulang semua route guide, sehingga jumper putaran lama hilang dan
  detailed routing mengacak net lain. Dari putaran 5, guide yang ada tidak diubah.
- **Memecah beban dengan buffer, bukan memperbesar sel.** Batas 0,2 pF (`MAX_CAPACITANCE_CONSTRAINT`) sama untuk semua
  ukuran sel, jadi sel lebih besar tidak menolong.
- **Dioda saja tidak cukup:** router kadang menyambung dioda lewat cabang lain. Jumper met1 memendekkan potongan kawat
  di gate.

### 13 layout modul (40 MHz)

Clock 25 ns. Angka dari `results/metrics.csv`. Slack = terburuk dari semua corner. Daya = estimasi OpenROAD.

Ke-13 layout: DRC Magic 0, DRC KLayout 0, LVS 0, XOR 0, routing DRC 0, pelanggaran setup/hold 0. Sisa pelanggaran ada di
kolom antena, slew, kapasitansi, dan fanout.

| Layout | Run | Pin | Sel | Area sel (µm²) | Die (mm²) | Setup (ns) | Hold (ns) | Antena | Slew | Kap. | Fanout | Daya (mW) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| i2s_rx | c1 | 25 | 393 | 3.452 | 0,011 | +17,67 | +0,112 | 0 | 0 | 0 | 0 | 0,24 |
| preemph | c1 | 62 | 2.424 | 16.551 | 0,059 | +12,50 | +0,112 | 0 | 0 | 0 | 10 | 2,01 |
| gap | c1 | 50 | 1.128 | 8.389 | 0,029 | +15,01 | +0,106 | 0 | 0 | 0 | 5 | 0,57 |
| window | c1 | 57 | 4.591 | 28.066 | 0,107 | +8,75 | +0,111 | 0 | 106 | 0 | 8 | 5,71 |
| log_q | c1 | 92 | 1.537 | 11.283 | 0,036 | +10,43 | +0,127 | 0 | 7 | 0 | 3 | 0,95 |
| cough_det | c1 | 152 | 5.225 | 39.490 | 0,119 | +4,19 | +0,106 | 1 | 8 | 0 | 26 | 4,59 |
| power | c1 | 122 | 10.365 | 59.206 | 0,237 | +3,43 | +0,114 | 9 | 18 | 0 | 13 | 12,45 |
| mel | fix | 121 | 82.308 | 411.302 | 1,335 | +5,15 | +0,108 | 9 | 2.840 | 75 | 3.156 | 26,13 |
| requant (P16) | c1 | 476 | 9.143 | 65.145 | 0,198 | +6,68 | +0,100 | 5 | 11 | 0 | 38 | 16,57 |
| requant (P32) | c2 | 860 | 16.280 | 95.958 | 0,548 | +6,56 | +0,091 | 16 | 9 | 1 | 47 | 19,36 |
| pe_array (P16) | c2 | 914 | 26.435 | 181.079 | 0,624 | +12,88 | +0,105 | 29 | 18 | 9 | 120 | 27,62 |
| pe_array (P32) | fix | 1.810 | 91.006 | 444.584 | 2,403 | +10,35 | +0,105 | 18 | 47 | 10 | 1.339 | 62,92 |

Run: `c1` = utilisasi inti relatif (30%, `mel` 20%); `c2` = die diperbesar karena jumlah pin melebihi keliling;
`fix` = run ulang dengan perbaikan antena dan slew/kapasitansi (netlist dan die sama). `pe_array`, `requant`, dan
`gap` sekarang sudah termasuk di dalam `cnn_top`; varian P32 dan `uart_bridge` tidak dipakai di ASIC.

## Keputusan desain

- **Clock 10,24 MHz (periode 97,656 ns)** untuk target ASIC; I2S 1,024 MHz. Pada 25 ns, hold corner SS gagal (−1,78 ns)
  karena delay input SDC (20% periode) lebih kecil dari latensi clock SS (8–12 ns); pada 97,656 ns penyebabnya hilang.
  Clock tidak sebanding langsung dengan FPGA (KV260 300 MHz): proses dan sel berbeda.
- **P = 16** untuk ASIC (bitstream FPGA yang diuji memakai P = 32).
- **Antarmuka host AXI4-Lite** (`axil_ctrl`), sama dengan FPGA. UART tidak dipakai di chip.
- **Memori sebagai makro SRAM, bukan flip-flop.** ROM bobot 116 Kbit yang disintesis jadi logika membuat global routing
  macet (> 40 menit; dengan ROM diganti stub, 27 detik). RAM dan ROM bobot `cnn_top` memakai makro OpenRAM 2 KB.
  Konsekuensinya bobot tidak tertanam: dimuat lewat port `wl_*` setelah chip menyala.
- **Simulasi:** `cnn_top` dengan model makro OpenRAM bit-exact terhadap golden pada 5 kasus uji (P16); jalur muat `wl_*`
  cocok untuk 921 alamat × 4 lane.
- **Makro OpenRAM dibaca penuh oleh Magic** (`MAGIC_MACRO_STD_CELL_SOURCE=PDK`): mode kotak hitam menghasilkan GDS Magic
  rusak ("Structure name not found"). Magic melapor layer penanda OpenRAM yang tidak dikenalnya (22/21, 22/22, 33/42,
  33/43, 235/0); kebenaran GDS diperiksa lewat XOR terhadap KLayout.
- **Signoff `cnn_top` tanpa makro.** XOR dan DRC dijalankan pada GDS dengan 14 instans makro dikeluarkan
  (`signoff_nomacro.py`); DRC Magic penuh melaporkan sekitar 33 juta pelanggaran di dalam makro OpenRAM (0 di luar) dan
  dilewati sengaja. Perlu konfirmasi waiver dengan penyelenggara shuttle.
- **Perbaikan antena modul** (`FIX=1`): dioda heuristik, 10 iterasi perbaikan antena, margin 15%, batas kabel 400 µm,
  perbaikan desain diulang setelah global routing.

## Keterbatasan

- **Belum ada layout chip utuh.** Blok yang belum pernah di-layout: `fft512`, `frame_buf`, `feat_buf`, `quant`,
  `dsp_chain`, `axil_ctrl`. Top chip (`suaratb_axil_top` versi ASIC) belum dibuat.
- **Clock modul tidak seragam.** 13 layout modul di 40 MHz; hanya `cnn_top` di 10,24 MHz. Antena dan slew tidak berubah
  oleh clock dan tetap harus diperbaiki.
- **Sisa pelanggaran di modul:** `mel` (antena 9, kapasitansi 75, slew 2.840, fanout 3.156; slew dan fanout memburuk setelah
  perbaikan antena), `power` (antena 9, slew 18), `cough_det` (antena 1, slew 8), `window` (slew 106), `log_q` (slew 7).
- **`cnn_top`:** slew 666 dan fanout 1.205 belum ditangani. Batas fanout adalah panduan desain, bukan aturan fisik.
- **Lib makro hanya TT.** Makro OpenRAM hanya punya lib TT, dipakai di semua corner; timing jalur melewati makro di corner
  SS dan FF tidak bisa dipercaya penuh.
- **Luas.** Die `cnn_top` saja 8,99 mm² dan lebarnya 3,07 mm; area pengguna Caravel sekitar 2,92 × 3,52 mm. Seluruh sistem
  kemungkinan tidak muat tanpa pemadatan.
- **Pin AXI.** `suaratb_axil_top` punya sekitar 116 pin; Caravel hanya 38 GPIO. AXI-Lite harus tetap di dalam chip
  (jembatan Wishbone ke AXI-Lite) atau memakai platform dengan pad ring sendiri.
- **Bobot CNN tidak tertanam;** `axil_ctrl` belum punya register muat bobot (`WL_ADDR`, `WL_DATA`).
- **LVS membuktikan layout = netlist sintesis.** Kesetaraan RTL vs golden dari simulasi cocotb; simulasi gate-level belum.
- **Daya adalah estimasi** OpenROAD tanpa vektor aktivitas.
- **Mesin.** WSL 10 GB hampir kehabisan memori pada signoff `cnn_top`; signoff top kemungkinan perlu mesin 32 GB ke atas.

## Rencana

Platform tape-out menentukan sisanya, jadi keputusan itu didahulukan.

1. **Pilih platform dan gelombang shuttle.** Caravel (AXI-Lite di dalam chip lewat Wishbone) atau pad ring sendiri
   (AXI-Lite sebagai pin).
2. **Anggaran luas.** Sintesis cepat (`scripts/synth_sky130.sh`) blok yang belum di-layout pada 10,24 MHz; jumlahkan
   dengan `cnn_top`; bandingkan dengan area platform. Putuskan RAM `fft512`, `frame_buf`, `feat_buf`: makro SRAM atau
   flip-flop.
3. **Padatkan `cnn_top`** bila perlu (die lebih kecil, tata ulang makro), lalu ulangi signoff.
4. **RTL top chip.** Salinan ASIC `suaratb_axil_top` dengan `cnn_top` versi makro, register `WL_ADDR` (0x024) dan `WL_DATA`
   (0x028, alamat naik otomatis) di `axil_ctrl`, dan (untuk Caravel) jembatan Wishbone ke AXI-Lite.
5. **Verifikasi RTL top.** Cocotb: muat bobot lewat AXI, jalankan klip, bandingkan dengan golden.
6. **Layout blok di 10,24 MHz** dengan perbaikan antena dan slew: enam blok kecil, `mel`, dan blok yang belum di-layout.
7. **Layout top**, lalu **signoff chip**: DRC, LVS, STA 9 corner, antena, kapasitansi, slew, fanout; simulasi gate-level
   dengan SDF.
8. **Precheck resmi platform** dan pengiriman.
9. **Rapikan repo** (hampir selesai): skrip, metrik final, dan paket hasil sudah ada di repo dan Release. Tersisa memasukkan
   `cnn_top` ke `collect_results.py`.
