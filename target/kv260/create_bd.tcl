# Membuat block design "kv260_clk": zynq_ultra_ps_e (hanya pl_clk0 dan pl_resetn0) -> clk_wiz (MMCM) -> proc_sys_reset.
# Keluaran eksternal: core_clk (target 300,032 MHz) dan core_rst_n (aktif-rendah, sinkron ke core_clk).
# Dipanggil dari synth.tcl (mode full) di dalam project yang part/board-nya sudah diatur. Frekuensi bisa diubah lewat env CORE_MHZ.
set core_mhz [expr {[info exists ::env(CORE_MHZ)] ? $::env(CORE_MHZ) : 300.032}]
set pl0_mhz  [expr {[info exists ::env(PL0_MHZ)]  ? $::env(PL0_MHZ)  : 100.0}]

create_bd_design kv260_clk
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e zynq_ps]
# preset papan (DDR/MIO) bila board part tersedia; tanpa preset PS tetap valid untuk sintesis, tetapi TIDAK untuk dijalankan di papan.
if {[llength [get_board_parts -quiet *kv260_som*]] > 0} {
  apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset 1} $ps
}
set_property -dict [list \
  CONFIG.PSU__FPGA_PL0_ENABLE 1 \
  CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ $pl0_mhz \
  CONFIG.PSU__USE__M_AXI_GP0 0 CONFIG.PSU__USE__M_AXI_GP1 0 CONFIG.PSU__USE__M_AXI_GP2 0 \
  CONFIG.PSU__USE__S_AXI_GP0 0 CONFIG.PSU__USE__S_AXI_GP1 0 CONFIG.PSU__USE__S_AXI_GP2 0 \
  CONFIG.PSU__USE__S_AXI_GP3 0 CONFIG.PSU__USE__S_AXI_GP4 0 CONFIG.PSU__USE__S_AXI_GP5 0 CONFIG.PSU__USE__S_AXI_GP6 0 \
] $ps

set cw [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz clk_wiz_0]
# frekuensi pl_clk0 sebenarnya (PS tidak menghasilkan 100 MHz persis, mis. 99,999001): masukan clk_wiz harus sama
set pl0_act_mhz [expr {[get_property CONFIG.FREQ_HZ [get_bd_pins $ps/pl_clk0]] / 1e6}]
set_property -dict [list \
  CONFIG.PRIM_IN_FREQ $pl0_act_mhz \
  CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $core_mhz \
  CONFIG.USE_LOCKED true CONFIG.USE_RESET false \
] $cw

set rs [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset rst_0]

connect_bd_net [get_bd_pins $ps/pl_clk0]       [get_bd_pins $cw/clk_in1]
connect_bd_net [get_bd_pins $ps/pl_resetn0]    [get_bd_pins $rs/ext_reset_in]
connect_bd_net [get_bd_pins $cw/clk_out1]      [get_bd_pins $rs/slowest_sync_clk]
connect_bd_net [get_bd_pins $cw/locked]        [get_bd_pins $rs/dcm_locked]

create_bd_port -dir O -type clk core_clk
create_bd_port -dir O -type rst core_rst_n
connect_bd_net [get_bd_pins $cw/clk_out1]          [get_bd_ports core_clk]
connect_bd_net [get_bd_pins $rs/peripheral_aresetn] [get_bd_ports core_rst_n]

validate_bd_design
save_bd_design
puts "BD kv260_clk dibuat: core_mhz_diminta=$core_mhz pl0_diminta=$pl0_mhz pl0_aktual=$pl0_act_mhz core_aktual_hz=[get_property CONFIG.FREQ_HZ [get_bd_pins $cw/clk_out1]]"
