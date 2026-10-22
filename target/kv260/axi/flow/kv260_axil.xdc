# Constraint KV260 untuk kv260_axil (host AXI4-Lite): hanya I2S INMP441 dan LED di Pmod 3,3 V. Tidak ada pin UART.
# SUMBER PIN: kria-vitis-platforms kv260_bist pin.xdc (commit 60c3f54) untuk pin FPGA; nomor pin fisik J2 dari tabel pengguna (tampaknya UG1089), belum dicocokkan
# dengan dokumen aslinya: pin J2 1..8 = H12 B10 E10 E12 D10 D11 C11 B11; pin 9,10 = GND; pin 11,12 = 3,3 V.
# Sambungan: i2s_sd = B10 (pin 2), led_busy = E12 (pin 4), i2s_bclk = D10 (pin 5), led_rec = D11 (pin 6), i2s_ws = C11 (pin 7).
# KOREKSI: catatan lama memakai tata letak Pmod standar (GND pin 5/11, 3,3 V pin 6/12) dan keliru untuk J2 KV260.
set_property PACKAGE_PIN D10 [get_ports i2s_bclk]
set_property PACKAGE_PIN C11 [get_ports i2s_ws]
set_property PACKAGE_PIN B10 [get_ports i2s_sd]
set_property PACKAGE_PIN E12 [get_ports led_busy]
set_property PACKAGE_PIN D11 [get_ports led_rec]
set_property IOSTANDARD LVCMOS33 [get_ports {i2s_bclk i2s_ws i2s_sd led_busy led_rec}]
set_property SLEW SLOW [get_ports {i2s_bclk i2s_ws led_busy led_rec}]
set_property DRIVE 4 [get_ports {i2s_bclk i2s_ws led_busy led_rec}]
# Clock inti dan clock AXI dari IP (PS pl_clk0 -> clk_wiz); SmartConnect menangani penyeberangan clock.
set_false_path -from [get_ports i2s_sd]
set_false_path -to   [get_ports {i2s_bclk i2s_ws led_busy led_rec}]
