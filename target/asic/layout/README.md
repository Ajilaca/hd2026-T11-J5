# layout: paket hasil layout ASIC SuaraTB (sky130)

Paket serah-terima hasil layout fisik blok-blok SuaraTB di proses terbuka SkyWater 130 nm (sky130A, sel standar
`sky130_fd_sc_hd`), dibuat dengan OpenLane 2.3.10 (Yosys, OpenROAD, Magic, KLayout, Netgen). Isi paket ini adalah
**hasil**, bukan sumber: skrip pembuatnya ada di `target/asic/scripts/` di repo (`layout_modules.py`, `layout_cnn_macro.py`,
`collect_results.py`), RTL di `rtl/`.

Unduhan: GitHub Release `asic-cnn-top-p16-10m24-v1` (https://github.com/Ajilaca/hackaton-deeptech-suaratb/releases/tag/asic-cnn-top-p16-10m24-v1).
Isi paket ini = zip `suaratb_asic_13modul_40MHz.zip` (SHA-256 `c7f04147a6ad3c00a9c71d482d54cef8728d43985dab0ffd6c83c9c048fa93ab`); `cnn_top` final ada di zip terpisah di Release yang sama.

Status ringkas (22 Okt 2026): `cnn_top` P=16 pada 10,24 MHz selesai dan bersih, tetapi **belum ada di paket ini**;
paket ini berisi 13 layout modul pada 40 MHz. Chip penuh (top) belum di-layout dan belum siap tape-out.
Lihat bagian Progres dan Keterbatasan.

## Isi direktori

Tiap direktori modul punya struktur yang sama. Satu direktori = satu layout (satu run OpenLane).

| Direktori / berkas | Fungsi |
| --- | --- |
| `metrics.csv` | Ringkasan semua layout dalam satu tabel: pin, sel, area, die, utilisasi, DRC, LVS, XOR, slack setup/hold, antena, slew, kapasitansi, fanout, daya, panjang kabel |
| `i2s_rx/` | Penerima I2S dari mikrofon (393 sel) |
| `preemph/` | Filter pre-emphasis audio (2.424 sel) |
| `window/` | Windowing Hamming 400 sampel dengan ROM jendela (4.591 sel) |
| `power/` | Daya spektrum dari keluaran FFT (10.365 sel) |
| `mel/` | Filterbank mel dengan ROM bobot (82.308 sel; blok terbesar di luar CNN, masih bermasalah) |
| `log_q/` | Log dan kuantisasi fitur dengan LUT log (1.537 sel) |
| `cough_det/` | Detektor batuk berbasis energi (5.225 sel) |
| `gap/` | Global average pooling CNN (1.128 sel) |
| `requant/` | Requantisasi keluaran CNN, P=16 (9.143 sel) |
| `requant_P32/` | Requantisasi dengan P=32 (16.280 sel); tidak dipakai di ASIC, hanya perbandingan |
| `pe_array/` | Array PE (MAC) CNN, P=16 (26.435 sel) |
| `pe_array_P32/` | Array PE dengan P=32 (91.006 sel); tidak dipakai di ASIC, hanya perbandingan |
| `uart_bridge/` | Jembatan UART host. **Sudah tidak dipakai**: antarmuka host ASIC adalah AXI4-Lite (`axil_ctrl`) |

Isi di dalam tiap direktori modul:

| Subdirektori / berkas | Fungsi |
| --- | --- |
| `gds/<modul>.gds` | Layout akhir (GDSII) |
| `def/<modul>.def` | Layout akhir (DEF): penempatan dan routing |
| `lef/<modul>.lef` | Abstrak (LEF) untuk dipakai sebagai makro di layout yang lebih besar |
| `lib/<corner>/` | Model timing Liberty untuk 9 corner (min/nom/max dikali ss/tt/ff) |
| `nl/<modul>.nl.v` | Netlist Verilog hasil sintesis dan routing (tanpa pin daya) |
| `pnl/<modul>.pnl.v` | Netlist Verilog dengan pin daya (VPWR/VGND), dipakai untuk LVS dan simulasi gate-level |
| `sdc/<modul>.sdc` | Batasan timing (clock, delay input/output) yang dipakai saat layout |
| `spef/nom/` | Parasitik hasil ekstraksi (SPEF), corner nominal |
| `metrics.json` | Seluruh metrik OpenLane run final |
| `metrics.csv` | Satu baris ringkasan modul ini |

Catatan: semua modul di sini dijalankan pada **clock 25 ns (40 MHz)** dengan utilisasi inti 30% (`mel` 20%), kecuali
`requant_P32` dan `pe_array`, yang die-nya diperbesar karena jumlah pin melebihi keliling die. `mel` dan `pe_array_P32` adalah run
ulang dengan perbaikan antena dan slew/kapasitansi.

## Progres

| Bagian | Status |
| --- | --- |
| 13 layout modul di paket ini | DRC Magic 0, DRC KLayout 0, LVS 0, XOR 0, routing DRC 0, setup/hold 0 pelanggaran |
| `cnn_top` P=16, 10,24 MHz, 14 makro SRAM OpenRAM | **Selesai, tidak ada di paket ini.** Kapasitansi 0, antena 0, LVS 0, routing DRC 0, signoff XOR/DRC (tanpa makro) 0/0, timing bersih 9 corner. Die 3.072 × 2.926 µm. Lokasi: `~/suaratb-data/build/asic/cnn_top/p16_10m_eco8/run/final/` di WSL |
| `fft512`, `frame_buf`, `feat_buf`, `quant`, `dsp_chain`, `axil_ctrl` | Belum pernah di-layout |
| Top chip (`suaratb_axil_top` versi ASIC) | Belum dibuat. Perlu register muat bobot CNN (WL_ADDR/WL_DATA) di salinan ASIC `axil_ctrl` |
| Tape-out | Belum: platform shuttle belum dipilih |

## Keterbatasan

- **Clock tidak seragam.** Modul di paket ini di 40 MHz; `cnn_top` final di 10,24 MHz. Target ASIC adalah 10,24 MHz
  (I2S 1,024 MHz). Angka setup modul di sini terlalu pesimistis dibanding target; antena dan slew tidak berubah
  oleh clock dan tetap harus diperbaiki.
- **Pelanggaran tersisa di beberapa modul.** `mel`: antena 9, kapasitansi 75, slew 2.840, fanout 3.156. `power`: antena 9,
  slew 18. `cough_det`: antena 1, slew 8. `window`: slew 106. `log_q`: slew 7. Detail di `metrics.csv`.
- **`cnn_top`:** slew 666 dan fanout 1.205 belum ditangani (timing aman, slack setup +34 ns). Magic DRC melaporkan sekitar
  33 juta pelanggaran di dalam makro OpenRAM (0 di luar makro): perlu konfirmasi waiver dengan penyelenggara shuttle.
  Signoff XOR/DRC dijalankan pada GDS dengan makro dikeluarkan (`target/asic/signoff_nomacro.py` di WSL).
- **Luas.** Die `cnn_top` saja 8,99 mm² dan lebarnya 3,07 mm; area pengguna Caravel sekitar 2,92 × 3,52 mm. Seluruh
  sistem kemungkinan tidak muat tanpa pemadatan.
- **Pin AXI.** `suaratb_axil_top` punya sekitar 116 pin; Caravel hanya 38 GPIO. AXI-Lite harus tetap di dalam chip
  (jembatan Wishbone ke AXI-Lite) atau memakai platform dengan pad ring sendiri.
- **Bobot CNN tidak tertanam.** ROM bobot adalah SRAM yang kosong saat chip menyala; bobot dimuat lewat port `wl_*`
  (3.684 kata) oleh software saat start.
- **Daya adalah estimasi** OpenROAD tanpa vektor aktivitas, bukan hasil simulasi.
- **Skrip ECO tidak ada di repo.** Perbaikan kapasitansi dan antena `cnn_top` (8 putaran) memakai skrip di
  `~/suaratb-data/build/asic/cnn_top/p16_10m_eco*/eco_scripts/` di WSL; belum dipindahkan dan belum di-commit.
- **Platform signoff.** Laptop WSL 10 GB hampir kehabisan memori pada signoff `cnn_top`; signoff top kemungkinan perlu mesin
  32 GB ke atas.

## Langkah berikutnya

Urutan lengkap menuju tape-out ada di laporan "Laporan Layout ASIC SuaraTB: Progres dan Rencana Tape-out".
Ringkasnya: pilih platform, hitung anggaran luas dari sintesis blok yang belum di-layout, tulis RTL top chip, layout top,
signoff level chip, precheck platform.

## Sumber

- Skrip dan RTL: `target/asic/` (README di sana menjelaskan skrip; skripnya di `scripts/`), `rtl/`, `target/kv260/axi/`.
- Hasil lengkap per run (log, semua langkah): `$SUARATB_DATA/build/asic/<modul>/runs/<run>/` di WSL, tidak di git.
