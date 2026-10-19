# target/asic: studi kelayakan ASIC sky130

Layout fisik blok-blok SuaraTB di proses terbuka SkyWater 130 nm untuk menunjukkan bahwa hardware ini bisa dibuat sebagai
chip. Alur: OpenLane 2.3.10 (Yosys, OpenROAD, Magic, KLayout, Netgen) di Docker, PDK sky130A (volare
`0fe599b2afb6708d281543108caf8310912f54af`), sel standar `sky130_fd_sc_hd`. RTL di `rtl/` tidak diubah; semua kode khusus
proses ada di sini.

## Isi

| Berkas | Fungsi |
|---|---|
| `synth_sky130.sh` | Sintesis Yosys ke sel sky130 (perkiraan ukuran per modul) |
| `layout_modules.py` | Layout per modul tanpa RAM (13 layout); `FIX=1` = perbaikan antena dan slew/kapasitansi |
| `layout_cnn_macro.py` | Layout `cnn_top` dengan RAM dan ROM bobot sebagai makro SRAM OpenRAM (`WROM=sram`) |
| `ram/ram_sdp_sky130.sv` | Pengganti `ram_sdp` (port sama) dari makro `sky130_sram_2kbyte_1rw1r_32x512_8` |
| `ram/wrom_sky130.sv` | ROM bobot CNN sebagai makro SRAM yang diisi lewat port muat `wl_*` |
| `ram/patch_wrom.py` | Salinan `cnn_top` (di direktori build) yang memakai `wrom_sky130` dan port `wl_*` |
| `ram/check_ram_wrapper.py`, `ram/test_wrom_load.py` | Simulasi cocotb: `cnn_top` dengan makro vs golden, dan jalur muat bobot |
| `render_layout.py` | GDS ke PNG dengan label layer dan legenda |
| `collect_results.py` | Salin metrik ke `results/` dan buat paket serah-terima (zip) |
| `results/` | `metrics.csv` (ringkasan), `metrics/<layout>.json` (metrik lengkap OpenLane), `<layout>.png` |

Hasil lengkap per run ada di `$SUARATB_DATA/build/asic/<layout>/runs/<run>/` (tidak di git). Paket serah-terima
`$SUARATB_DATA/handoff/suaratb_asic_layout.zip` (138 MB) berisi `final/` tiap layout: GDS, DEF, netlist, SDC, SPEF
(nominal), LEF, Liberty, metrik.

## Hasil: 13 layout modul

Clock 25 ns (40 MHz). Semua angka dari `results/metrics.csv` (metrik OpenLane `final/metrics.json`). Slack = terburuk dari
semua corner proses/suhu/tegangan. Daya = estimasi OpenROAD tanpa vektor aktivitas.

Ke-13 layout: DRC Magic 0, DRC KLayout 0, LVS 0, XOR Magic vs KLayout 0, sisa pelanggaran routing 0, pelanggaran
setup/hold 0.

| Layout | Run | Pin | Sel | Area sel (µm²) | Die (mm²) | Setup (ns) | Hold (ns) | Antena | Slew | Kap. | Fanout | Daya (mW) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| i2s_rx | c1 | 25 | 393 | 3.452 | 0,011 | +17,67 | +0,112 | 0 | 0 | 0 | 0 | 0,24 |
| preemph | c1 | 62 | 2.424 | 16.551 | 0,059 | +12,50 | +0,112 | 0 | 0 | 0 | 10 | 2,01 |
| uart_bridge | c1 | 83 | 1.232 | 10.055 | 0,031 | +15,42 | +0,108 | 0 | 0 | 0 | 12 | 0,71 |
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
`fix` = run ulang dengan perbaikan antena dan slew/kapasitansi (netlist dan die sama).

Perbaikan (`fix`) dibanding run asli:

| Layout | Antena | Slew | Kapasitansi | Fanout | Sel | Setup (ns) |
|---|---|---|---|---|---|---|
| mel | 189 -> 9 | 1.357 -> 2.840 | 272 -> 75 | 467 -> 3.156 | 48.068 -> 82.308 | +6,57 -> +5,15 |
| pe_array (P32) | 141 -> 18 | 117 -> 47 | 70 -> 10 | 262 -> 1.339 | 71.062 -> 91.006 | +12,12 -> +10,35 |

## Hasil: `cnn_top` dengan makro SRAM (belum selesai)

- ROM bobot (116 Kbit) yang disintesis sebagai logika membuat global routing macet (run diagnosis: ROM diganti stub
  -> global routing lolos 27 s, overflow 0; dengan ROM asli macet > 40 menit). Karena itu ROM bobot dijadikan 8 makro SRAM.
- Simulasi (cocotb, Icarus, P=16): `cnn_top` dengan RAM dan ROM sebagai model makro OpenRAM bit-exact terhadap golden
  pada 5 kasus uji; jalur muat `wl_*` cocok untuk 921 alamat x 4 lane.
- Layout P16 (14 makro: 6 RAM + 8 ROM; die 2.972 x 2.826 µm = 8,40 mm²; 85.714 sel): routing 0 pelanggaran; timing TT
  (setup +4,80 ns, hold +0,25 ns) dan FF bersih; corner SS gagal (setup -1,98 ns, hold -1,26 ns); antena 124 net;
  daya 59,3 mW (estimasi). XOR, DRC, LVS, dan LEF top **belum ada**: Magic dan KLayout kehabisan memori (> 7 GB) di laptop
  8 GB. P32 belum dijalankan.

## Keputusan

- **Clock 40 MHz (25 ns)** untuk semua layout sky130. Tidak sebanding langsung dengan clock FPGA (KV260 300 MHz):
  proses dan sel berbeda.
- **Memori sebagai makro SRAM, bukan flip-flop.** RAM dan ROM bobot `cnn_top` memakai makro OpenRAM 2 KB. Untuk versi
  ASIC, bobot dimuat lewat port `wl_*` sebelum CNN dipakai (beda perilaku dari RTL FPGA yang memakai ROM terisi).
- **Makro OpenRAM dibaca penuh oleh Magic** (`MAGIC_MACRO_STD_CELL_SOURCE=PDK`): mode kotak hitam menghasilkan GDS Magic
  rusak ("Structure name not found"). Saat membaca, Magic melapor layer penanda OpenRAM yang tidak dikenalnya
  (22/21, 22/22, 33/42, 33/43, 235/0); kebenaran GDS diperiksa lewat XOR terhadap KLayout.
- **Perbaikan antena** (`FIX=1`): dioda heuristik, 10 iterasi perbaikan antena, margin 15%, batas kabel 400 µm,
  perbaikan desain diulang setelah global routing.

## Batasan

- **Slew dan fanout `mel` memburuk** setelah perbaikan antena (slew corner SS 913 -> 2.197; fanout 467 -> 3.156);
  harus diperbaiki sebelum tape-out. Dugaan: dioda heuristik menambah beban dan buffer kecil memperlambat transisi di SS.
- **Antena dan slew/kapasitansi modul lain belum diperbaiki** (`window`, `log_q`, `cough_det`, `power`, `requant`,
  `pe_array` P16).
- **Fanout naik** di kedua layout `fix`; batas fanout adalah panduan desain, bukan aturan fisik.
- **Layout per modul, bukan chip utuh.** Modul ber-RAM (`fft512`, `frame_buf`, `feat_buf`) dan integrasi (`suaratb_top`)
  belum di-layout; `cnn_top` belum selesai (lihat atas).
- **LVS membuktikan layout = netlist sintesis.** Kesetaraan RTL vs golden dari simulasi cocotb; simulasi gate-level belum.
- **Corner SS `cnn_top`**: makro OpenRAM hanya punya lib TT, dipakai untuk semua corner; hasil SS belum bisa dipercaya.
- **Wrapper ROM P32** belum diuji simulasi; nama instans makro RAM P32 belum dicek.
