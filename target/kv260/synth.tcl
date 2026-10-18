# Sintesis/implementasi Vivado untuk Kria KV260 (K26 SOM, XCK26-SFVC784-2LV-C). Jalankan dari ROOT repo:
#   P=16 PDIR=/data/suaratb/build/synth/P16 OUT=/data/suaratb/build/kv260/P16 MODE=ooc  vivado -mode batch -source target/kv260/synth.tcl
#   P=16 PDIR=... OUT=... MODE=full vivado -mode batch -source target/kv260/synth.tcl     (sampai bitstream)
# MODE=ooc : hanya suaratb_top, tanpa pin dan IP (laporan sumber daya/timing murni, mirip target/artix7/synth.tcl).
# MODE=full: kv260_top + block design (PS pl_clk0 -> MMCM) + kv260.xdc, sampai write_bitstream.
# PDIR berisi cnn_cfg_pkg.sv dan cnn_{wrom,bias,rq}.mem dari target/artix7/prep_synth.py.
# Env: P, PDIR, OUT (wajib); MODE (ooc), CLK_NS (6.782 = 147,456 MHz), PART, BOARD_REPO, IMPL (1), CORE_MHZ (147.456).
set P      $::env(P)
set PDIR   $::env(PDIR)
set OUT    $::env(OUT)
set MODE   [expr {[info exists ::env(MODE)] ? $::env(MODE) : "ooc"}]
set CLK_NS [expr {[info exists ::env(CLK_NS)] ? $::env(CLK_NS) : 6.782}]
set PART   [expr {[info exists ::env(PART)] ? $::env(PART) : "xck26-sfvc784-2LV-c"}]
set IMPL   [expr {[info exists ::env(IMPL)] ? $::env(IMPL) : 1}]
set BOARD_REPO [expr {[info exists ::env(BOARD_REPO)] ? $::env(BOARD_REPO) : "/data/suaratb/ext/xilinx_board_store/repo/boards/Xilinx"}]
file mkdir $OUT
set root [pwd]
set_param general.maxThreads 4

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

set generics [list \
  "INIT_W=\"$PDIR/cnn_wrom.mem\"" "INIT_B=\"$PDIR/cnn_bias.mem\"" "INIT_RQ=\"$PDIR/cnn_rq.mem\"" \
  "INIT_WIN=\"$root/rtl/mem/window_hamming.mem\"" "INIT_COS=\"$root/rtl/mem/twiddle_cos.mem\"" \
  "INIT_SIN=\"$root/rtl/mem/twiddle_sin.mem\"" "INIT_MEL=\"$root/rtl/mem/mel_rom.mem\"" "INIT_LOG=\"$root/rtl/mem/log_lut.mem\""]

if {$MODE eq "ooc"} {
  foreach f $files { read_verilog -sv $f }
  set gargs {}
  foreach g $generics { lappend gargs -generic $g }
  synth_design -top suaratb_top -part $PART -mode out_of_context -flatten_hierarchy rebuilt {*}$gargs
  create_clock -name clk -period $CLK_NS [get_ports clk]
  report_utilization -file $OUT/util_synth.rpt
  report_timing_summary -file $OUT/timing_synth.rpt
  write_checkpoint -force $OUT/synth.dcp
  if {$IMPL} {
    opt_design; place_design; route_design
    report_utilization -file $OUT/util_impl.rpt
    report_utilization -hierarchical -file $OUT/util_impl_hier.rpt
    report_timing_summary -file $OUT/timing_impl.rpt
    report_power -file $OUT/power_impl.rpt
    write_checkpoint -force $OUT/impl.dcp
  }
} else {
  create_project -force kv260 $OUT/proj -part $PART
  if {[file isdirectory $BOARD_REPO]} {
    set_param board.repoPaths $BOARD_REPO
    set bp [get_board_parts -quiet *kv260_som*]
    if {[llength $bp] > 0} { set_property board_part [lindex $bp end] [current_project] }
  }
  add_files -norecurse $files
  add_files -norecurse $root/target/kv260/kv260_top.sv
  set_property file_type SystemVerilog [get_files *.sv]
  source $root/target/kv260/create_bd.tcl
  make_wrapper -files [get_files kv260_clk.bd] -top
  add_files -norecurse [glob $OUT/proj/kv260.gen/sources_1/bd/kv260_clk/hdl/kv260_clk_wrapper.v]
  add_files -fileset constrs_1 -norecurse $root/target/kv260/kv260.xdc
  set_property top kv260_top [current_fileset]
  set_property generic [join $generics " "] [current_fileset]
  update_compile_order -fileset sources_1
  generate_target all [get_files kv260_clk.bd]
  launch_runs synth_1 -jobs 4; wait_on_run synth_1
  open_run synth_1
  report_utilization -file $OUT/util_synth.rpt
  report_timing_summary -file $OUT/timing_synth.rpt
  if {$IMPL} {
    launch_runs impl_1 -to_step write_bitstream -jobs 4; wait_on_run impl_1
    open_run impl_1
    report_utilization -file $OUT/util_impl.rpt
    report_utilization -hierarchical -file $OUT/util_impl_hier.rpt
    report_timing_summary -file $OUT/timing_impl.rpt
    report_power -file $OUT/power_impl.rpt
    report_clock_utilization -file $OUT/clock_util.rpt
    file copy -force [glob $OUT/proj/kv260.runs/impl_1/kv260_top.bit] $OUT/kv260_top_P${P}.bit
  }
}
puts "SELESAI P=$P MODE=$MODE"
