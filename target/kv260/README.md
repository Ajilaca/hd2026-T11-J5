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
Clock inti 147,456 MHz (K-22) memberi `CLK_PER_BCLK = 144` (BCLK 1,024 MHz, fs 16 kHz tepat) dan `CLK_PER_BIT = 1280` (UART
115200 baud tepat); keduanya dihitung di `kv260_top` dari `CORE_HZ` dan `UART_BAUD`. `pl_clk0` 100 MHz dari PS melalui MMCM
tidak dapat menghasilkan 147,456 MHz persis (hitung brute-force atas M fraksional 0,125, D, O fraksional 0,125); yang terdekat
147,4576 MHz (+11 ppm), jadi fs aktual 16.000,2 Hz dan baud aktual sekitar 115.201. Nilai yang benar-benar dipilih `clk_wiz`
harus dibaca dari laporan hasil build (belum ada, lihat bawah).

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
Belum ada. Vivado terpasang belum mendukung part XCK26 saat berkas ini ditulis (famili Zynq UltraScale+ sedang dipasang), jadi tidak
ada angka LUT/FF/DSP/BRAM/WNS/daya untuk K26. Pembanding Artix-7 150 MHz (laporan alat, `docs/vault/sintesis.md`):

| P | LUT | FF | DSP48E1 | BRAM tile | WNS |
|---|---|---|---|---|---|
| 16 | 5.926 | 7.799 | 17 | 12 | +0,222 ns |
| 32 | 8.120 | 10.071 | 17 | 12 | +0,023 ns |

## Belum terverifikasi
- Nomor pin fisik Pmod untuk tiap indeks HDA11..HDA18 (kolom "diasumsikan"); periksa UG1089 atau multimeter.
- Skrip `create_bd.tcl` dan mode `full` di `synth.tcl` belum pernah dijalankan (alat belum mendukung K26).
- Nama properti PS/MMCM pada versi IP 2026.1 dan penerapan preset papan `kv260_som`.
- I2S nyata dari INMP441, level tegangan Pmod, konfigurasi PS di Linux, dan UART ke host: hanya bisa diuji dengan papan.
