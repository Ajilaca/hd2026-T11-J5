# Block design "kv260_axil": PS (M_AXI_HPM0_FPD, pl_clk0) -> SmartConnect (lintas clock) -> suaratb_axil_ip (core_clk), clk_wiz (MMCM), reset.
# Dipanggil dari synth_axil.tcl di dalam project yang berkas RTL-nya (termasuk suaratb_axil_ip.v) sudah ditambahkan.
# Peta alamat PS: suaratb_axil_ip pada 0xA000_0000, 4 KiB. Frekuensi: env CORE_MHZ (300.032), PL0_MHZ (100).
set core_mhz [expr {[info exists ::env(CORE_MHZ)] ? $::env(CORE_MHZ) : 300.032}]
set pl0_mhz  [expr {[info exists ::env(PL0_MHZ)]  ? $::env(PL0_MHZ)  : 100.0}]

create_bd_design kv260_axil
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e zynq_ps]
if {[llength [get_board_parts -quiet *kv260_som*]] > 0} {
  apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset 1} $ps
}
set_property -dict [list \
  CONFIG.PSU__FPGA_PL0_ENABLE 1 \
  CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ $pl0_mhz \
  CONFIG.PSU__USE__M_AXI_GP0 1 CONFIG.PSU__MAXIGP0__DATA_WIDTH 32 \
  CONFIG.PSU__USE__M_AXI_GP1 0 CONFIG.PSU__USE__M_AXI_GP2 0 \
  CONFIG.PSU__USE__S_AXI_GP0 0 CONFIG.PSU__USE__S_AXI_GP1 0 CONFIG.PSU__USE__S_AXI_GP2 0 \
  CONFIG.PSU__USE__S_AXI_GP3 0 CONFIG.PSU__USE__S_AXI_GP4 0 CONFIG.PSU__USE__S_AXI_GP5 0 CONFIG.PSU__USE__S_AXI_GP6 0 \
] $ps

set cw [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz clk_wiz_0]
set pl0_act_mhz [expr {[get_property CONFIG.FREQ_HZ [get_bd_pins $ps/pl_clk0]] / 1e6}]
set_property -dict [list CONFIG.PRIM_IN_FREQ $pl0_act_mhz CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $core_mhz \
  CONFIG.USE_LOCKED true CONFIG.USE_RESET false] $cw

set rs [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset rst_0]
set sc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect sc_0]
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 1 CONFIG.NUM_CLKS 2] $sc
set ip [create_bd_cell -type module -reference suaratb_axil_ip u_ip]

# clock dan reset
connect_bd_net [get_bd_pins $ps/pl_clk0]       [get_bd_pins $cw/clk_in1] [get_bd_pins $ps/maxihpm0_fpd_aclk] [get_bd_pins $sc/aclk]
connect_bd_net [get_bd_pins $cw/clk_out1]      [get_bd_pins $rs/slowest_sync_clk] [get_bd_pins $sc/aclk1] [get_bd_pins $ip/s_axi_aclk]
connect_bd_net [get_bd_pins $cw/locked]        [get_bd_pins $rs/dcm_locked]
connect_bd_net [get_bd_pins $ps/pl_resetn0]    [get_bd_pins $rs/ext_reset_in]
connect_bd_net [get_bd_pins $rs/peripheral_aresetn] [get_bd_pins $sc/aresetn] [get_bd_pins $ip/s_axi_aresetn]
# bus
connect_bd_intf_net [get_bd_intf_pins $ps/M_AXI_HPM0_FPD] [get_bd_intf_pins $sc/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins $sc/M00_AXI]        [get_bd_intf_pins $ip/s_axi]
# pin eksternal
foreach {n d} {i2s_bclk O i2s_ws O led_busy O led_rec O i2s_sd I} {
  create_bd_port -dir $d $n
  if {$d eq "O"} { connect_bd_net [get_bd_pins $ip/$n] [get_bd_ports $n] } else { connect_bd_net [get_bd_ports $n] [get_bd_pins $ip/$n] }
}
# irq tidak dipakai: dibiarkan menggantung (PYNQ memakai polling STATUS)

assign_bd_address -offset 0xA0000000 -range 4K [get_bd_addr_segs u_ip/s_axi/*]
foreach sg [get_bd_addr_segs -of_objects [get_bd_addr_spaces zynq_ps/Data]] { puts "SEGMEN: $sg offset=[get_property OFFSET $sg] range=[get_property RANGE $sg]" }
validate_bd_design
save_bd_design
puts "BD kv260_axil dibuat: core_mhz=$core_mhz pl0_aktual=$pl0_act_mhz core_hz=[get_property CONFIG.FREQ_HZ [get_bd_pins $cw/clk_out1]]"
