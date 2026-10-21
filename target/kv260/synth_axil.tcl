# Sintesis/implementasi/bitstream KV260 untuk varian host AXI4-Lite (tanpa UART). Jalankan dari ROOT repo:
#   P=32 PDIR=/data/suaratb/build/synth/P32_distill OUT=/data/suaratb/build/kv260/axil_P32 vivado -mode batch -source target/kv260/synth_axil.tcl
# Keluaran: $OUT/suaratb_axil_P<P>.bit dan .hwh (nama sama, dipakai PYNQ), laporan util/timing/daya/clock.
# Env: P, PDIR, OUT (wajib); STOP (bd | synth | impl, default impl) menghentikan lebih awal; CORE_MHZ (300.032), PL0_MHZ (100),
#      PART, BOARD_REPO, JOBS (1). PDIR berisi cnn_cfg_pkg.sv dan cnn_{wrom,bias,rq}.mem dari target/artix7/prep_synth.py.
set P      $::env(P)
set PDIR   $::env(PDIR)
set OUT    $::env(OUT)
set STOP   [expr {[info exists ::env(STOP)] ? $::env(STOP) : "impl"}]
set PART   [expr {[info exists ::env(PART)] ? $::env(PART) : "xck26-sfvc784-2LV-c"}]
set CORE_MHZ [expr {[info exists ::env(CORE_MHZ)] ? $::env(CORE_MHZ) : 300.032}]
set BOARD_REPO [expr {[info exists ::env(BOARD_REPO)] ? $::env(BOARD_REPO) : "/data/suaratb/ext/xilinx_board_store/repo/boards/Xilinx"}]
set JOBS [expr {[info exists ::env(JOBS)] ? $::env(JOBS) : 1}]   ;# RAM 7,6 GB: satu job
set_param general.maxThreads [expr {$JOBS > 1 ? 4 : 2}]
set root [pwd]
file mkdir $OUT

# pembungkus IP dari template (jalur .mem absolut, CLK_PER_BCLK = CORE_HZ / 1,024 MHz)
set clk_per_bclk [expr {int(round($CORE_MHZ * 1e6 / 1.024e6))}]
set fh [open $root/target/kv260/axi/suaratb_axil_ip.v.in r]; set tpl [read $fh]; close $fh
set ipv [string map [list \
  @CLK_PER_BCLK@ $clk_per_bclk @INIT_W@ $PDIR/cnn_wrom.mem @INIT_B@ $PDIR/cnn_bias.mem @INIT_RQ@ $PDIR/cnn_rq.mem \
  @INIT_WIN@ $root/rtl/mem/window_hamming.mem @INIT_COS@ $root/rtl/mem/twiddle_cos.mem @INIT_SIN@ $root/rtl/mem/twiddle_sin.mem \
  @INIT_MEL@ $root/rtl/mem/mel_rom.mem @INIT_LOG@ $root/rtl/mem/log_lut.mem] $tpl]
set fh [open $OUT/suaratb_axil_ip.v w]; puts $fh $ipv; close $fh

set files {}
set fh [open rtl/files.f r]
while {[gets $fh line] >= 0} {
  set line [string trim $line]
  if {$line eq "" || [string match "//*" $line]} continue
  if {[string match "*sva_stream.sv" $line]} continue
  if {[string match "*cnn_cfg_pkg.sv" $line]} { lappend files $PDIR/cnn_cfg_pkg.sv; continue }
  lappend files $root/$line
}
close $fh
lappend files $root/target/kv260/axi/axil_ctrl.v $root/target/kv260/axi/suaratb_axil_top.sv

create_project -force kv260 $OUT/proj -part $PART
if {[file isdirectory $BOARD_REPO]} {
  set_param board.repoPaths $BOARD_REPO
  set bp [get_board_parts -quiet *kv260_som*]
  if {[llength $bp] > 0} { set_property board_part [lindex $bp end] [current_project] }
}
add_files -norecurse $files
add_files -norecurse $OUT/suaratb_axil_ip.v
set_property file_type SystemVerilog [get_files -filter {NAME =~ *.sv}]
update_compile_order -fileset sources_1
set ::env(CORE_MHZ) $CORE_MHZ
source $root/target/kv260/create_bd_axil.tcl
make_wrapper -files [get_files kv260_axil.bd] -top
add_files -norecurse [glob $OUT/proj/kv260.gen/sources_1/bd/kv260_axil/hdl/kv260_axil_wrapper.v]
add_files -fileset constrs_1 -norecurse $root/target/kv260/kv260_axil.xdc
set_property top kv260_axil_wrapper [current_fileset]
update_compile_order -fileset sources_1
generate_target all [get_files kv260_axil.bd]
puts "PORT BD: [get_bd_ports]  INTF: [get_bd_intf_ports]"
if {$STOP eq "bd"} { puts "SELESAI (bd) P=$P"; exit 0 }

launch_runs synth_1 -jobs $JOBS; wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { puts "SINTESIS GAGAL"; exit 1 }
open_run synth_1
report_utilization -file $OUT/util_synth.rpt
report_timing_summary -file $OUT/timing_synth.rpt
if {$STOP eq "synth"} { puts "SELESAI (synth) P=$P"; exit 0 }

launch_runs impl_1 -to_step write_bitstream -jobs $JOBS; wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { puts "IMPLEMENTASI GAGAL"; exit 1 }
open_run impl_1
report_utilization -file $OUT/util_impl.rpt
report_utilization -hierarchical -file $OUT/util_impl_hier.rpt
report_timing_summary -file $OUT/timing_impl.rpt
report_power -file $OUT/power_impl.rpt
report_clock_utilization -file $OUT/clock_util.rpt
set stem suaratb_axil_P${P}
file copy -force [glob $OUT/proj/kv260.runs/impl_1/kv260_axil_wrapper.bit] $OUT/$stem.bit
set hwh [glob -nocomplain $OUT/proj/kv260.gen/sources_1/bd/kv260_axil/hw_handoff/kv260_axil.hwh]
if {[llength $hwh] == 0} { set hwh [glob -nocomplain $OUT/proj/kv260.gen/sources_1/bd/kv260_axil/hw_handoff/*.hwh] }
file copy -force [lindex $hwh 0] $OUT/$stem.hwh
puts "SELESAI P=$P (bitstream $OUT/$stem.bit)"
