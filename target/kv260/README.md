# target/kv260

Target Kria KV260 Vision AI Starter Kit (SOM K26, `XCK26-SFVC784-2LV-C`, Zynq UltraScale+). Menjalankan `suaratb_top` di PL.
Demo utama lewat UART (mode dataset); mikrofon INMP441 (I2S) adalah bonus bila memungkinkan. `rtl/` dan `golden/` tidak diubah.

| Berkas | Peran |
|---|---|
| `kv260_top.sv` | Pembungkus: clock inti dari block design, sinkronisasi reset dan masukan asinkron, pemetaan ke Pmod |
| `create_bd.tcl` | Block design `kv260_clk`: `zynq_ultra_ps_e` (hanya `pl_clk0`, `pl_resetn0`) -> `clk_wiz` (MMCM) -> `proc_sys_reset` |
| `kv260.xdc` | Pin Pmod, standar I/O, false path untuk masukan asinkron |
| `synth.tcl` | Sintesis/implementasi untuk XCK26: `MODE=ooc` (suaratb_top saja) atau `MODE=full` (sampai bitstream) |
| `run.sh` | Pemanggil `synth.tcl` untuk beberapa nilai P (perintah dan variabel di header skrip) |

## Clock dan parameter
Clock inti 300,032 MHz = 293 x 1,024 MHz (K-24): `CLK_PER_BCLK = 293` (BCLK I2S 1,024 MHz, fs 16 kHz di nominal) dan
`CLK_PER_BIT = 2604` (UART 115200 baud, dibulatkan ke bawah); keduanya dihitung di `kv260_top` dari `CORE_HZ` dan `UART_BAUD`.
`pl_clk0` dari PS (aktual 99,999001 MHz) melalui MMCM menghasilkan **299,997 MHz** (dibaca dari log build, bukan 300,032), jadi
BCLK aktual sekitar 1,0239 MHz (fs sekitar 15,998 kHz, -0,012%) dan baud aktual sekitar 115.200. Untuk Artix-7/147,456 MHz (K-22)
berikan `CORE_MHZ=147.456`.

## Pin Pmod (J2)
Sumber pin: XDC resmi AMD `kria-vitis-platforms/kv260/platforms/kv260_bist/xdc/pin.xdc` (commit `60c3f54`, 2026-07-08):
`PMOD_GPIO_tri_io[0..7]` = HDA11..HDA18 = `H12 E10 D10 C11 B10 E12 D11 B11`, LVCMOS33. Berkas board `kv260_som`/`kv260_carrier`
(XilinxBoardStore) tidak mendefinisikan Pmod, jadi pin tidak diambil dari sana.

| Indeks | Pin FPGA | Sinyal | Pin Pmod (diasumsikan) | Sambungan |
|---|---|---|---|---|
| 0 | H12 | `uart_rx` | 1 | TXD adaptor USB-UART (3,3 V) |
| 1 | E10 | `uart_tx` | 2 | RXD adaptor USB-UART |
| 2 | D10 | `i2s_bclk` | 3 | SCK INMP441 |
| 3 | C11 | `i2s_ws` | 4 | WS INMP441 |
| 4 | B10 | `i2s_sd` | 7 | SD INMP441 |
| 5 | E12 | `led_busy` | 8 | LED eksternal opsional |
| 6 | D11 | `led_rec` | 9 | LED eksternal opsional |
| 7 | B11 | (tidak dipakai) | 10 | - |

Pmod pin 5 dan 6 = GND, pin 11 dan 12 = 3,3 V. INMP441: VDD ke 3,3 V, GND ke GND, L/R ke GND (kanal kiri), SCK/WS/SD seperti tabel.
Adaptor USB-UART wajib level 3,3 V dan berbagi GND dengan Pmod. UART bawaan board terhubung ke PS, bukan ke PL, sehingga UART PL
memakai Pmod.

## Memuat bitstream
Dengan Vivado Hardware Manager (JTAG/USB) memuat `kv260_top_P<P>.bit`, atau di Linux KV260 memuat `.bit.bin` dengan `fpgautil`.
Konfigurasi PS di Linux KV260 (mengaktifkan `pl_clk0`) belum diuji.

## Hasil build
Vivado 2026.1, XCK26-SFVC784-2LV-C, satu run per titik, tanpa seed sweep. Sumber: laporan alat di `$SUARATB_DATA/build/kv260/`.

Build penuh (`MODE=full`: MMCM, I/O, XDC, post-route) pada clock inti 300,032 MHz (aktual 299,997 MHz):

| P | LUT | FF | DSP48E2 | BRAM36 | WNS | WHS | WPWS | Daya (vectorless) |
|---|---|---|---|---|---|---|---|---|
| 16 | 5.954 (5,08%) | 7.845 (3,35%) | 17 | 12 (8,33%) | +0,065 ns | +0,016 ns | +0,905 ns | 2,938 W |
| 32 | 8.147 (6,96%) | 10.292 (4,39%) | 17 | 12 (8,33%) | +0,219 ns | +0,010 ns | +0,905 ns | 2,964 W |

Pembanding pada 333,82 MHz (build penuh): P=16 gagal (WNS -0,270 ns, WHS -0,035 ns); P=32 lolos tipis (WNS +0,018 ns, WHS +0,011 ns).
Dari situ 300,032 MHz dipilih; Fmax sistem tidak dicari lebih jauh.

Fmax OOC (`suaratb_top` saja, tanpa I/O dan MMCM, bukan Fmax sistem):

| P | Terpenuhi (periode terkecil) | Gagal |
|---|---|---|
| 16 | 2,997 ns, 333,7 MHz (WNS +0,077 ns) | 2,941 ns, 340,0 MHz (-0,100 ns); 351,3 MHz; 370,8 MHz |
| 32 | 2,995 ns, 333,9 MHz (WNS +0,061 ns) | tidak dicari |

WNS tidak monoton terhadap periode (satu seed), jadi angka ini batas untuk satu run, bukan jaminan. Rekomendasi: **P = 32**, WNS
paling longgar pada clock terpilih dan siklus CNN paling sedikit. Margin hold tipis (+0,010 sampai +0,016 ns).

Latensi CNN turunan (siklus simulasi `cnn_top` dari `start` sampai `done`, Icarus, dikali periode 299,997 MHz; bukan pengukuran
papan): P=16 226.520 siklus = 0,76 ms; P=32 122.872 siklus = 0,41 ms. Pengiriman klip lewat UART 115200 baud (16.481 byte)
sekitar 1,43 s dan mendominasi waktu demo.

## Belum terverifikasi
- Nomor pin fisik Pmod untuk tiap indeks HDA11..HDA18 (kolom "diasumsikan"); periksa UG1089 atau multimeter.
- Bitstream `.bit` dibuat, tetapi belum dimuat ke papan; konversi ke `.bit.bin` untuk `fpgautil` belum dibuat.
- Nama properti PS/MMCM pada versi IP 2026.1 dan penerapan preset papan `kv260_som`.
- I2S nyata dari INMP441, level tegangan Pmod, konfigurasi PS di Linux, dan UART ke host: hanya bisa diuji dengan papan.
