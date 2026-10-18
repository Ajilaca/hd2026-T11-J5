# Constraint KV260 (Kria K26 SOM + carrier). Semua I/O di Pmod 3,3 V (HDA11..HDA18).
# SUMBER PIN: berkas resmi AMD/Xilinx kria-vitis-platforms, kv260/platforms/kv260_bist/xdc/pin.xdc (commit 60c3f54, 2026-07-08):
#   PMOD_GPIO_tri_io[0..7] = HDA11..HDA18 = H12 E10 D10 C11 B10 E12 D11 B11, LVCMOS33.
# BELUM DIVERIFIKASI: korespondensi indeks 0..7 terhadap nomor pin fisik Pmod (diasumsikan 0..3 = pin 1-4, 4..7 = pin 7-10).
# Periksa dengan UG1089 atau multimeter sebelum menyambung INMP441/adaptor UART.

# --- UART (demo utama) ---
set_property PACKAGE_PIN H12 [get_ports uart_rx]
set_property PACKAGE_PIN E10 [get_ports uart_tx]
# --- I2S INMP441 (bonus) ---
set_property PACKAGE_PIN D10 [get_ports i2s_bclk]
set_property PACKAGE_PIN C11 [get_ports i2s_ws]
set_property PACKAGE_PIN B10 [get_ports i2s_sd]
# --- indikator opsional (LED eksternal atau probe) ---
set_property PACKAGE_PIN E12 [get_ports led_busy]
set_property PACKAGE_PIN D11 [get_ports led_rec]

set_property IOSTANDARD LVCMOS33 [get_ports {uart_rx uart_tx i2s_bclk i2s_ws i2s_sd led_busy led_rec}]
set_property SLEW SLOW [get_ports {uart_tx i2s_bclk i2s_ws led_busy led_rec}]
set_property DRIVE 4 [get_ports {uart_tx i2s_bclk i2s_ws led_busy led_rec}]

# Clock inti berasal dari IP (PS pl_clk0 -> clk_wiz): create_clock dan generated clock diturunkan otomatis oleh IP.
# Masukan asinkron sudah melewati sinkronisasi 2-FF di kv260_top; keluaran lambat.
set_false_path -from [get_ports {uart_rx i2s_sd}]
set_false_path -to   [get_ports {uart_tx i2s_bclk i2s_ws led_busy led_rec}]
