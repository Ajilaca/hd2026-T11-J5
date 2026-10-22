# Memprogram PL KV260 dari laptop lewat kabel micro-USB (JTAG pada FT4232H di carrier card) memakai Vivado Hardware Manager.
#   BIT=/data/suaratb/build/kv260/axil_P32/suaratb_axil_P32.bit vivado -mode batch -source target/kv260/axi/flow/program_jtag.tcl
# Prasyarat satu kali (butuh sudo): aturan udev kabel Xilinx
#   sudo /data/tools/Xilinx/2026.1/data/xicom/cable_drivers/lin64/install_script/install_drivers/install_drivers
# lalu cabut dan colok ulang kabel micro-USB. Papan harus menyala dan PS sudah boot (Linux) agar pl_clk0 berjalan; rangkaian
# SuaraTB mengambil clock dari pl_clk0 (PS). Pemrograman JTAG tidak menyalakan pl_clk0 sendiri.
# Env: BIT (wajib), HW_SERVER (default localhost:3121), PROBE (1 = hanya daftar perangkat JTAG, tanpa memprogram).
set bit $::env(BIT)
set srv [expr {[info exists ::env(HW_SERVER)] ? $::env(HW_SERVER) : "localhost:3121"}]
open_hw_manager
connect_hw_server -url $srv
open_hw_target
puts "Perangkat JTAG: [get_hw_devices]"
if {[info exists ::env(PROBE)] && $::env(PROBE) eq "1"} { close_hw_manager; exit 0 }
set pl [lindex [get_hw_devices xck26*] 0]
if {$pl eq ""} { puts "TIDAK ADA perangkat xck26 di rantai JTAG"; exit 1 }
current_hw_device $pl
set_property PROGRAM.FILE $bit $pl
set_property PROBES.FILE {} $pl
program_hw_devices $pl
puts "SELESAI: pemrograman PL tanpa galat (cek 'End of startup status: HIGH' di log)"
close_hw_manager
